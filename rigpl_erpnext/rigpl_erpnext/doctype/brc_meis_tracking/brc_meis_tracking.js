// Copyright (c) 2017, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('BRC MEIS Tracking', {
	refresh: function(frm) {

	},
	onload: function(frm){
		frm.set_query("reference_doctype", function(doc) {
			return {
				"filters": [
					['name', 'in', ['Sales Invoice', 'Purchase Invoice']]
				]
			};
		});
		frm.set_query("reference_name", function(doc) {
			return {
				"filters": {
					"docstatus": 1
				}
			};
		});
		frm.set_query("customer_or_supplier", function(doc) {
			return {
				"filters": [
					['name', 'in', ['Customer', 'Supplier']]
				]
			};
		});
	},
});
