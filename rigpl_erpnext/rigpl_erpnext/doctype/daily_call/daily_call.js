// Copyright (c) 2018, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Daily Call', {
	refresh: function(frm) {

	},
	onload: function(frm){
		frm.set_query("document", "call_details", function(doc, cdt, cdn) {
			return {
				"filters": [
					['name', 'in', ['Customer', 'Lead']]
				]
			};
		});
		frm.set_query("contact", "call_details", function(doc, cdt, cdn) {
		    var d = locals[cdt][cdn]
			return {
				query: 'frappe.contacts.doctype.contact.contact.contact_query',
				filters: {
					link_doctype: d.document,
					link_name: d.document_name
				}
			};
		});
	},
});
function set_lead_details(cdt, cdn) {
	const d = locals[cdt][cdn];
	if (d.document !== 'Lead' || !d.document_name) return;
	frappe.db.get_value('Lead', d.document_name, ['company_name', 'lead_name', 'status'], (lead) => {
		frappe.model.set_value(cdt, cdn, "lead_organisation_name", lead.company_name);
		frappe.model.set_value(cdt, cdn, "lead_contact_name", lead.lead_name);
		frappe.model.set_value(cdt, cdn, "lead_status", lead.status);
		frappe.model.set_value(cdt, cdn, "contact", "");
	});
}

frappe.ui.form.on('Daily Call Details', "document_name", function(frm, cdt, cdn){
	set_lead_details(cdt, cdn);
});

frappe.ui.form.on('Daily Call Details', "document", function(frm, cdt, cdn){
	set_lead_details(cdt, cdn);
});

frappe.ui.form.on('Daily Call Details', "contact", function(frm, cdt, cdn){
	const d = locals[cdt][cdn];
	if (d.contact && d.document === 'Customer'){
		frappe.db.get_value('Contact', d.contact, ['first_name', 'last_name'], (contact) => {
			frappe.model.set_value(cdt, cdn, "lead_contact_name",
				[contact.first_name, contact.last_name].filter(Boolean).join(' '));
		});
	}
});

frappe.ui.form.on('Daily Call Details', "type_of_communication", function(frm, cdt, cdn){
	var d = locals[cdt][cdn]
	if (d.type_of_communication === 'Visit'){
		frappe.model.set_value(cdt, cdn, "duration", 60);
	} else if (d.type_of_communication === 'Phone'){
		frappe.model.set_value(cdt, cdn, "duration", 5);
	} else if (d.type_of_communication === 'Trial Conducted'){
		frappe.model.set_value(cdt, cdn, "duration", 120);
	}
});