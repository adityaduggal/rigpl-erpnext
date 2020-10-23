frappe.ui.form.on("Purchase Order Item", {
	schedule_date: function(frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (row.schedule_date < now()) {
			if(!frm.doc.schedule_date) {
				erpnext.utils.copy_value_in_all_rows(frm.doc, cdt, cdn, "items", "schedule_date");
			} else {
				set_schedule_date(frm);
			}
		}
	}
});

frappe.ui.form.on("Purchase Order Item", "item_code", function(frm, cdt, cdn){
    var d = locals[cdt][cdn];
    description = get_description();
    d.description = description;
    frm.refresh_fields();
});

cur_frm.cscript.is_subcontracting = function(doc, cdt, cdn) {
    cur_frm.set_query("item_code", "items", function(){
        if (cur_frm.doc.is_subcontracting == 1){
            return{
                query: "erpnext.controllers.queries.item_query",
                filters:{ 'is_job_work': 1 }
            }
        }
        else {
            return{
                query: "erpnext.controllers.queries.item_query",
                filters:{'is_purchase_item':1}
            }
        }
    });
    cur_frm.set_query("subcontracted_item", "items", function(){
        if (cur_frm.doc.is_subcontracting == 1){
            return{
                query: "erpnext.controllers.queries.item_query",
                filters:{ 'is_job_work': 1 }
            }
        }
        else {
            return{
                query: "erpnext.controllers.queries.item_query",
                filters:{'is_purchase_item':1}
            }
        }
    });
};
frappe.ui.form.on("Purchase Order", "refresh", function(frm) {

// Get Items from Work Order
cur_frm.add_custom_button(__('Job Card'),
    function() {
        var dialog = new frappe.ui.Dialog({
        title: "Get Items from Job Card",
        fields: [
            {"fieldtype": "Link", "label": __("Job Card"), "fieldname": "job_card","options":'Process Job Card RIGPL',"reqd": 1,
                get_query: function() { return {query: "rigpl_erpnext.rigpl_erpnext.validations.purchase_order.get_pending_jc"}},
            },
            {"fieldtype": "Button", "label": __("Get"), "fieldname": "get"},
            {"fieldtype": "HTML", "fieldname": "production_order_items_details"},
        ],
    });
    dialog.show();
    var fd = dialog.fields_dict;
    dialog.fields_dict.get.$input.click(function() {
        var value = dialog.get_values();

    frappe.call({    
        method: "frappe.client.get_list",
           args: {
            doctype: "Process Job Card RIGPL",
               fields: ["production_item", "description", "qty_available","s_warehouse","name",
               "sales_order_item", "uom"],
               filters: { "name" : value.job_card
                },
            },
            callback: function(res){
            if(res && res.message){
                    console.log(res.message[0])
                    var row = frappe.model.add_child(cur_frm.doc, "Purchase Order Item", "items");
                    row.qty = res.message[0]['qty_available'];
                    if (cur_frm.doc.is_subcontracting == 1){
                        row.subcontracted_item = res.message[0]['production_item'];
                    } else{
                        row.item_code = res.message[0]['production_item'];
                    }
                    row.reference_dt = "Process Job Card RIGPL"
                    row.reference_dn = res.message[0]['name'];
                    row.description = res.message[0]['description'];
                    row.from_warehouse = res.message[0]['s_warehouse']
                    row.so_detail = res.message[0]['sales_order_item'];
                    row.uom = res.message[0]['uom'];
                    row.stock_uom = res.message[0]['uom'];
                    row.conversion_factor = 1;
                refresh_field("items");
            }
        }
    });


    });

    var add_production_order_items_to_stock = function(){
        var items_to_add = []
        var value = dialog.get_values();
        $.each($(fd.production_order_items_details.wrapper).find(".select:checked"), function(name, item){
            items_to_add.push($(item).val());
        });
        if(items_to_add.length > 0){
            for(i=0;i<items_to_add.length;i++){
                add_production_order_items(items_to_add,i)
            }
            dialog.hide()
        }    
        else{
            msgprint("Select Item Before Add")
        }
    }
}, __("Get items from"));
cur_frm.add_custom_button(__('Work Order'),
    function() {
        var dialog = new frappe.ui.Dialog({
        title: "Get Items from Work Order",
        fields: [
            {"fieldtype": "Link", "label": __("Work Order"), "fieldname": "production_order","options":'Work Order',"reqd": 1,
                get_query: function() { return {query: "rigpl_erpnext.rigpl_erpnext.validations.purchase_order.get_pending_prd"}},
            },
            {"fieldtype": "Button", "label": __("Get"), "fieldname": "get"},
            {"fieldtype": "HTML", "fieldname": "production_order_items_details"},
        ],
    });
    dialog.show();
    var fd = dialog.fields_dict;
    dialog.fields_dict.get.$input.click(function() {
        var value = dialog.get_values();

    frappe.call({
        method: "frappe.client.get_list",
           args: {
            doctype: "Work Order",
               fields: ["production_item", "item_description ", "sales_order", "so_detail", "qty","fg_warehouse","stock_uom","name"],
               filters: { "name" : value.production_order
                },
            },
            callback: function(res){
            if(res && res.message){
                    var row = frappe.model.add_child(cur_frm.doc, "Purchase Order Item", "items");
                    row.qty = res.message[0]['qty'];
                    if (cur_frm.doc.is_subcontracting == 1){
                        row.subcontracted_item = res.message[0]['production_item'];
                    } else{
                        row.item_code = res.message[0]['production_item'];
                    }
                    row.reference_dt = "Work Order"
                    row.reference_dn = value.production_order
                    row.description = res.message[0]['item_description'];
                    row.so_detail = res.message[0]['so_detail'];
                    row.uom = res.message[0]['stock_uom'];
                    row.stock_uom = res.message[0]['stock_uom'];
                    row.conversion_factor = 1;
                refresh_field("items");
            }
        }
    });


    });

    var add_production_order_items_to_stock = function(){
        var items_to_add = []
        var value = dialog.get_values();
        $.each($(fd.production_order_items_details.wrapper).find(".select:checked"), function(name, item){
            items_to_add.push($(item).val());
        });
        if(items_to_add.length > 0){
            for(i=0;i<items_to_add.length;i++){
                add_production_order_items(items_to_add,i)
            }
            dialog.hide()
        }
        else{
            msgprint("Select Item Before Add")
        }
    }
}, __("Get items from"));
});