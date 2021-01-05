frappe.ui.form.on("Employee", "company_email", function(frm, cdt, cdn){
	var d = locals[cdt][cdn]
	frappe.model.set_value(cdt, cdn, "company_email_validated", 0);
	cur_frm.refresh_fields();
});

frappe.ui.form.on("Employee", "personal_email", function(frm, cdt, cdn){
	var d = locals[cdt][cdn]
	frappe.model.set_value(cdt, cdn, "personal_email_validated", 0);
	cur_frm.refresh_fields();
});