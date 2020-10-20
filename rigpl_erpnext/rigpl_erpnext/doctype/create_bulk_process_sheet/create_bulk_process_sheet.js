// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Create Bulk Process Sheet', {
	onload: function(frm){
	    frm.set_query("sales_order", function(doc){
	        return{
	            query: "rigpl_erpnext.rigpl_erpnext.doctype.create_bulk_process_sheet.create_bulk_process_sheet.get_so_pending_for_process_sheet"
	        }
	    });
		frm.set_query("item", function(doc) {
			return {
				"filters": {
					"disabled": 0,
					"has_variants": 0,
					"include_item_in_manufacturing":1,
					"made_to_order": 1,
					"is_sales_item":1
				}
			};
		});
	},
	get_sales_orders: function(frm) {
		frappe.call({
			doc: frm.doc,
			method: "get_open_sales_orders",
			callback: function(r) {
				refresh_field("sales_orders");
				refresh_field("items");
			}
		});
	},
	create_process_sheet: function(frm) {
		frappe.call({
			doc: frm.doc,
			method: "raise_process_sheet"
		});
		cur_frm.clear_table("items");
		cur_frm.refresh_fields();
	},
});

cur_frm.cscript.refresh = function(doc) {
	cur_frm.disable_save();
}