// Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on('Process Sheet', {
	refresh: function(frm){
	    if (frm.doc.show_unavailable_rm !== 1 && frm.doc.rm_consumed){
	        var rm = frm.doc.rm_consumed
	        var i = rm.length
	        while (i--){
	            if (rm[i].qty_available === 0){
	                frm.get_field("rm_consumed").grid.grid_rows[i].remove();
	            }
	        }
	        frm.refresh_fields();
	    }
        if (frm.doc.status === "In Progress"){
            me.frm.add_custom_button(__("Stop"), function(){
                frappe.call({
                    method: "rigpl_erpnext.utils.process_sheet_utils.stop_process_sheet",
                    args: {
                        "ps_name": frm.doc.name
                    },
                    callback: function(r){
                        if(!r.exc){
                            /*
                            var op_tbl = frm.doc.operations
                            for ( i = 0 ; i < op_tbl.length ; i++){
                                if (op_tbl[i].status == "In Process" || op_tbl[i].status == "Pending"){
                                    op_tbl[i].status = "Stopped"
                                }
                                frm.refresh_fields("operations");
                            }
                            */
                        }
                    }
                });
            });
        }
        if (frm.doc.status === "Stopped"){
            frm.add_custom_button(__("UnStop"), function(){
                frappe.call({
                    method: "rigpl_erpnext.utils.process_sheet_utils.unstop_process_sheet",
                    args: {
                        "ps_name": frm.doc.name
                    },
                    callback: function(r){
                        if(!r.exc){
                            /*
                            var op_tbl = frm.doc.operations
                            for ( i = 0 ; i < op_tbl.length ; i++){
                                if (op_tbl[i].completed_qty > 0){
                                    op_tbl[i].status = "In Process"
                                } else {
                                    op_tbl[i].status = "Pending"
                                }
                                frm.refresh_fields("operations");
                            }
                            */
                        }
                    }
                });
            });
        }
	    if (frm.doc.docstatus === 0){
            frm.add_custom_button(__('Select BOM Template Manually'),
                function(){
                    var dialog = new frappe.ui.Dialog({
                    title: "Select BOM Template Manually",
                    fields: [
                        {
                            "fieldtype": "Link",
                            "label": __("BOM Template"),
                            "fieldname": "bom_template",
                            "options":'BOM Template RIGPL',
                            "reqd": 1,
                            get_query: function() {
                               var filters = {
                                    it_name: frm.doc.production_item,
                                    so_detail: frm.doc.sales_order_item
                               }
                               return {
                                    query: "rigpl_erpnext.utils.process_sheet_utils.get_bom_template_from_item_name",
                                    filters: filters
                               };
                            },
                        },
                        {
                            "fieldtype": "Button",
                            "label": __("Select"),
                            "fieldname": "select"
                        }
                    ],

                    });
                    dialog.show();
                    var fd = dialog.fields_dict;
                    dialog.fields_dict.select.$input.click(function(){
                        frm.doc.bom_template = fd.bom_template.value
                        frm.doc.bom_template_description = ""
                        frm.doc.fg_warehouse = ""
                        frm.doc.routing = ""
                        frm.doc.operations = []
                        frm.doc.rm_consumed = []
                        frm.doc.item_manufactured = []
                        frm.refresh_fields();
                    });
                }
            )
	    }
	},
	onload: function(frm){
		frm.set_query("production_item", function(doc) {
			return {
				"filters": {
					"disabled": 0,
					"has_variants": 0,
					"include_item_in_manufacturing":1
				}
			};
		});
		frm.set_query("raw_material_source_warehouse", function(doc) {
			return {
				"filters": {
					"disabled": 0,
					"is_group": 0
				}
			};
		});
	},
	raw_material_source_warehouse: function(frm){
	    frm.doc.rm_consumed = []
	    frm.doc.item_manufactured = []
	    frm.refresh_fields();
	},
	show_unavailable_rm: function(frm){
	    frm.doc.rm_consumed = []
	    frm.doc.item_manufactured = []
	    frm.refresh_fields();
	},
	bom_template: function(frm){
	    frm.doc.fg_warehouse = ""
	    frm.doc.bom_template_description = ""
	    frm.doc.operations = []
	    frm.doc.rm_consumed = []
	    frm.doc.item_manufactured = []
	    frm.doc.allow_zero_rol_for_wip = 0
	    frm.refresh_fields();
	},
	production_item: function(frm){
	    frm.doc.bom_template = ""
	    frm.doc.fg_warehouse = ""
	    frm.doc.sales_order = ""
	    frm.doc.sales_order_item = ""
	    frm.doc.sales_order_serial_number = ""
	    frm.doc.quantity = 0
	    frm.doc.update_qty_manually = 0
	    if (frm.doc.production_item){
	        frappe.call({
	            doc: frm.doc,
	            method: "fill_details_from_item",
	            freeze: true,
	            callback: function(r){
	                if (!r.exc){
	                    frm.refresh_fields();
	                }
	            }
	        })
	    }
	    frm.refresh_fields();
	},
	routing: function(frm){
	    frm.doc.operations = []
	    frm.refresh_fields();
	},
	allow_zero_rol_for_wip: function(frm){
	    frm.doc.item_manufactured = []
	    frm.refresh_fields();
	}
});

frappe.ui.form.on('Process Sheet Items', {
    rm_consumed_remove: function(frm){
        frm.doc.item_manufactured = [];
        frm.refresh_fields();
    }
});

frappe.ui.form.on('BOM Operation', {
    create_new_job_card: function(frm, dt, dn) {
        var child = locals[dt][dn];
        if (child.planned_qty > child.completed_qty && child.status !== "Short Closed" &&
                child.status !== "Obsolete" && child.status != "Stopped") {
            frappe.call({
                method: "rigpl_erpnext.utils.job_card_utils.make_jc_from_pro_sheet_row",
                args: {
                    "production_item": frm.doc.production_item,
                    "operation": child.operation,
                    "ps_name": frm.doc.name,
                    "row_no": child.idx,
                    "row_id": child.name,
                    "so_detail": frm.doc.sales_order_item
                },
                callback: function(r){
                    if (!r.exc){
                        if (child.completed_qty > 0){
                            child.status = "In Progress"
                        } else {
                            child.status = "Pending"
                        }
                        frm.refresh_fields();
                    }
                }
            })
        } else if (child.planned_qty <= child.completed_qty){
            frappe.msgprint("For Row# " + child.idx + " No Pending Qty for Operation " + child.operation)
        }
    },
    stop_operation: function(frm, dt, dn){
        var child = locals[dt][dn];
        if (child.planned_qty > child.completed_qty && (child.status === "Pending" || child.status === "In Progress")){
            frappe.call({
                method: "rigpl_erpnext.utils.process_sheet_utils.stop_ps_operation",
                args: {
                    "op_id": child.name,
                    "psd": frm.doc
                },
                callback: function(r){
                    if (!r.exc){
                        child.status = "Stopped"
                        frm.refresh_fields();
                    }
                }
            })
        }
    },
});