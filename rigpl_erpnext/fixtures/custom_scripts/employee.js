frappe.ui.form.on("Employee", {
    refresh: function(frm){

    },
	onload: function(frm){
		frm.set_query("holiday_list", function(doc) {
			return {
				"filters": {
					"is_base_list": 1
				}
			};
		});
	},
    company_email: function(frm, cdt, cdn){
        var d = locals[cdt][cdn]
        frappe.model.set_value(cdt, cdn, "company_email_validated", 0);
        cur_frm.refresh_fields();
    },

    personal_email: function(frm, cdt, cdn){
        var d = locals[cdt][cdn]
        frappe.model.set_value(cdt, cdn, "personal_email_validated", 0);
        cur_frm.refresh_fields();
    }
});