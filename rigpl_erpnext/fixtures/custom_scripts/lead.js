frappe.ui.form.on("Lead", "refresh", function(frm) {
    frm.add_custom_button(__("Sales Call"), function() {
        // When this button is clicked, do this
			frappe.set_route("Form", "Sales Call Tool",
			{"document": "Lead",
			 "lead": frm.doc.name,
			 "date_of_communication": Date()});
			 
    },  __("Add Communication for"));
});