// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Create Bulk Production Orders', {
	get_sales_orders: function(frm) {
		frappe.call({
			doc: frm.doc,
			method: "get_open_sales_orders",
			callback: function(r) {
				refresh_field("sales_orders");
			}
		});
	},
	get_items: function(frm) {
		frappe.call({
			doc: frm.doc,
			method: "get_items",
			callback: function(r) {
				refresh_field("items");
			}
		});
	},
	create_production_orders: function(frm) {
		frappe.call({
			doc: frm.doc,
			method: "raise_production_orders"
		});
		cur_frm.clear_table("items");
		cur_frm.refresh_fields();
	},
});

cur_frm.cscript.refresh = function(doc) {
	cur_frm.disable_save();
}