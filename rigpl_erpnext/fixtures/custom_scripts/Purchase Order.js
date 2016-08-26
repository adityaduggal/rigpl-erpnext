cur_frm.cscript.is_subcontracting = function(doc, cdt, cdn) {
	cur_frm.set_query("item_code", "items", function(){
		if (cur_frm.doc.is_subcontracting == 1){
			return{
				query: "erpnext.controllers.queries.item_query",
				filters:{ 'is_sub_contracted_item': 1 }
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

// Get Items from Production Order
// Get Items from Production Order
cur_frm.add_custom_button(__('Production Order'),
    function() {
    var me = this;
    this.dialog = new frappe.ui.Dialog({
        title: "Get Items from Production Order",
        fields: [
            {"fieldtype": "Link", "label": __("Production Order"), "fieldname": "production_order","options":'Production Order',"reqd": 1, 
                get_query: function() { return {query: "rigpl_erpnext.rigpl_erpnext.validations.purchase_order.get_pending_prd"}},
            },
            {"fieldtype": "Button", "label": __("Get"), "fieldname": "get"},
            {"fieldtype": "HTML", "fieldname": "production_order_items_details"},
        ],
    });
    me.dialog.show();
    fd = this.dialog.fields_dict;
    this.dialog.fields_dict.get.$input.click(function() {
        value = me.dialog.get_values();

    frappe.call({    
        method: "frappe.client.get_list",
           args: {
            doctype: "Production Order",
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

    add_production_order_items_to_stock = function(){
        var items_to_add = []
        value = me.dialog.get_values();
        $.each($(fd.production_order_items_details.wrapper).find(".select:checked"), function(name, item){
            items_to_add.push($(item).val());
        });
        if(items_to_add.length > 0){
            for(i=0;i<items_to_add.length;i++){
                add_production_order_items(items_to_add,i)
            }
            me.dialog.hide()
        }    
        else{
            msgprint("Select Item Before Add")
        }
    }
}, __("Add items from"));

});