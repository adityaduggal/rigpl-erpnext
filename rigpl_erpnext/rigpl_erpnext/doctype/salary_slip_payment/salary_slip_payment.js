// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Salary Slip Payment', {
	get_salary_slips: function(frm) {
		return frappe.call({
			method: "get_salary_slips",
			doc: frm.doc,
			callback: function(r, rt) {
				frm.refresh_field("salary_slip_payment_details");
				frm.refresh_fields();
			}
		});
	},
	clear_table: function(frm) {
		return frappe.call({
			method: "clear_table",
			doc: frm.doc,
			callback: function(r, rt) {
				frm.refresh_field("salary_slip_payment_details");
				frm.refresh_fields();
			}
		});
	}
});
