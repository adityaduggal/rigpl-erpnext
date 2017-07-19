// Copyright (c) 2017, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Carrier Tracking', {
	refresh: function(frm) {

	},
	onload: function(frm){
		frm.set_query("carrier_name", function(doc) {
			return {
				"filters": {
					"track_on_shipway": 1
				}
			};
		});
	},
	post_data: function(frm, cdt, cdn) {
		frappe.call({
			method: "rigpl_erpnext.doctype.shipway_settings.pushOrderData",
			args: {
				"track_doc": frappe.get_doc("Carrier Tracking", frm.doc.name)
			},
			callback: function(r) {
				frappe.model.sync(r.message);
				frm.refresh();
			}
		})
	},
});
