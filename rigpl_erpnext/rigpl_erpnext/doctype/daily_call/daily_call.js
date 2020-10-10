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
frappe.ui.form.on('Daily Call Details', "document_name", function(frm, cdt, cdn){
	var d = locals[cdt][cdn]
	if (d.document === 'Lead'){
		frappe.call({
			"method": "frappe.client.get",
			args: {
				doctype: d.document,
				name: d.document_name
			},
			callback: function (data) {
				frappe.model.set_value(cdt, cdn, "lead_organisation_name", data.message.company_name);
				frappe.model.set_value(cdt, cdn, "lead_contact_name", data.message.lead_name);
				frappe.model.set_value(cdt, cdn, "lead_status", data.message.status);
				frappe.model.set_value(cdt, cdn, "contact", "");
			}
		});
	}
});

frappe.ui.form.on('Daily Call Details', "document", function(frm, cdt, cdn){
	var d = locals[cdt][cdn]
	if (d.document === 'Lead' && d.document_name){
		frappe.call({
			"method": "frappe.client.get",
			args: {
				doctype: d.document,
				name: d.document_name
			},
			callback: function (data) {
				frappe.model.set_value(cdt, cdn, "lead_organisation_name", data.message.company_name);
				frappe.model.set_value(cdt, cdn, "lead_contact_name", data.message.lead_name);
				frappe.model.set_value(cdt, cdn, "lead_status", data.message.status);
				frappe.model.set_value(cdt, cdn, "contact", "");
			}
		});
	}
});

frappe.ui.form.on('Daily Call Details', "no_action_required", function(frm, cdt, cdn){
	var d = locals[cdt][cdn]
	if (d.no_action_required !== 1){
		frappe.model.set_value(cdt, cdn, "next_action_date", "");
	}
});

frappe.ui.form.on('Daily Call Details', "contact", function(frm, cdt, cdn){
	var d = locals[cdt][cdn]
	if (d.contact !== '' && d.document === 'Customer'){
		frappe.call({
			"method": "frappe.client.get",
			args: {
				doctype: 'Contact',
				name: d.contact
			},
			callback: function (data) {
				frappe.model.set_value(cdt, cdn, "lead_contact_name", (data.message.first_name + ' ' + data.message.last_name));
			}
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