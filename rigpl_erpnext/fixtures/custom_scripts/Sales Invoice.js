frappe.ui.form.on("Sales Invoice", "refresh", function(frm) {
	if (!frm.doc.__islocal && frm.doc.docstatus == 0){
		frm.add_custom_button(__("Book Shipment"), function() {
		// When this button is clicked, do this
			frappe.route_options = {
				"shipment_forwarder": frm.doc.transporters,
				"reference_doctype": frm.doc.doctype,
				"reference_docname": frm.doc.name,
				"amount": frm.doc.grand_total,
				"currency": frm.doc.currency,
				"to_address": frm.doc.shipping_address_name,
				"contact_person": frm.doc.contact_person
			};
			frappe.new_doc("Book Shipment");
	    });
	}
});