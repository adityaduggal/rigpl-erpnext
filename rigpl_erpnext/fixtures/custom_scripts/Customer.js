cur_frm.add_fetch('charge','letter_head','letter_head');
frappe.ui.form.on("Customer", "refresh", function(frm) {
    frm.add_custom_button(__("Sales Call"), function() {
        // When this button is clicked, do this
			frappe.set_route("Form", "Sales Call Tool",
			{"document": "Customer",
			 "customer": frm.doc.name,
			 "date_of_communication": Date()});

    },  __("Add Communication for"));
});