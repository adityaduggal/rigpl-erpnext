// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt
cur_frm.add_fetch("lead", "custom_status", "status_of_lead");
cur_frm.toggle_display("create_communication", false);
frappe.ui.form.on('Sales Call Tool', {
	create_communication: function(frm) {
		frappe.call({
			doc: frm.doc,
			method: "create_communication",
			callback: function(r) {
				refresh_field("document");
			}
		});
	},
	
	refresh: function(frm) {

	},
	onload: function(frm){
		frm.set_query("contact", function(doc) {
			return {
				"filters": {
					"customer": doc.customer
				}
			};
		});
	},
});

cur_frm.cscript.no_action_required = function(doc, cdt, cdn) {
	if (cur_frm.doc.no_action_required == 1){
		cur_frm.toggle_reqd("next_action_date", false);
	}
	else{
		cur_frm.toggle_reqd("next_action_date", true);
	}
};

cur_frm.cscript.document = function(doc, cdt, cdn) {
	cur_frm.doc.customer = ""
	cur_frm.doc.contact = ""
	cur_frm.doc.type_of_communication = ""
	cur_frm.doc.date_of_communication = ""
	cur_frm.doc.next_action_date = ""
	cur_frm.doc.details = ""
	cur_frm.doc.lead_contact_name = ""
	cur_frm.doc.lead_organisation_name = ""
	refresh_field("customer");
	refresh_field("contact");
	refresh_field("type_of_communication");
	refresh_field("date_of_communication");
	refresh_field("next_action_date");
	refresh_field("details");
	refresh_field("lead_contact_name");
	refresh_field("lead_organisation_name");
	
	if (cur_frm.doc.document == "Customer"){
		cur_frm.toggle_reqd("customer", true);
		cur_frm.toggle_reqd("contact", true);
		cur_frm.toggle_reqd("type_of_communication", true);
		cur_frm.toggle_reqd("date_of_communication", true);
		cur_frm.toggle_reqd("next_action_date", true);
		cur_frm.toggle_reqd("lead", false);	
		cur_frm.toggle_display("create_communication", true);
		cur_frm.toggle_reqd("created_by", true);
		cur_frm.toggle_reqd("next_action_by", true);
		cur_frm.toggle_display("created_by", true);
		cur_frm.toggle_display("next_action_by", true);
	}
	else if (cur_frm.doc.document == "Lead"){
		cur_frm.toggle_reqd("customer", false);
		cur_frm.toggle_reqd("contact", false);
		cur_frm.toggle_reqd("type_of_communication", true);
		cur_frm.toggle_reqd("date_of_communication", true);
		cur_frm.toggle_reqd("next_action_date", true);
		cur_frm.toggle_reqd("lead", true);
		cur_frm.toggle_display("lead_contact_name", true);
		cur_frm.toggle_display("lead_organisation_name", true);
		cur_frm.toggle_display("create_communication", true);
		cur_frm.toggle_reqd("created_by", true);
		cur_frm.toggle_reqd("next_action_by", true);
		cur_frm.toggle_display("created_by", true);
		cur_frm.toggle_display("next_action_by", true);
	}
	else{
		cur_frm.toggle_reqd("customer", false);
		cur_frm.toggle_reqd("contact", false);
		cur_frm.toggle_reqd("type_of_communication", false);
		cur_frm.toggle_reqd("date_of_communication", false);
		cur_frm.toggle_reqd("next_action_date", false);
		cur_frm.toggle_reqd("lead", false);
		cur_frm.toggle_display("create_communication", false);
		cur_frm.toggle_reqd("created_by", false);
		cur_frm.toggle_reqd("next_action_by", false);
		cur_frm.toggle_display("created_by", false);
		cur_frm.toggle_display("next_action_by", false);
		cur_frm.toggle_display("lead_contact_name", false);
		cur_frm.toggle_display("lead_organisation_name", false);
	}
};

cur_frm.cscript.customer = function(doc, cdt, cdn) {
	cur_frm.doc.contact = ""
	refresh_field("contact");
};

cur_frm.cscript.refresh = function(doc) {
	cur_frm.disable_save();
}
