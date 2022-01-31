frappe.ui.form.on("Employee", {
    refresh: function(frm){
        frappe.dynamic_link = {doc: frm.doc, fieldname: 'name', doctype: 'Employee'}
        frm.toggle_display(['address_html', 'contact_html'], !frm.doc.__islocal);

        if(!frm.doc.__islocal) {
            frappe.contacts.render_address_and_contact(frm);
        } else {
            frappe.contacts.clear_address_and_contact(frm);
        }
    },
	onload: function(frm){
		frm.set_query("holiday_list", function(doc) {
			return {
				"filters": {
					"is_base_list": 1
				}
			};
		});
	}
});