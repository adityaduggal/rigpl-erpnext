// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Roster', {
	refresh: function(frm) {

	}
});

frappe.ui.form.on("Roster Details", "employee", function(frm, cdt, cdn){
	var d = frappe.get_doc(cdt, cdn);
	frappe.model.set_value(cdt, cdn, "from_date", frm.doc.from_date);
	frappe.model.set_value(cdt, cdn, "to_date", frm.doc.to_date);
	cur_frm.refresh_fields();
});