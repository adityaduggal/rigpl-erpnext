
frappe.ui.form.on('Delivery Note', {
	refresh: function(frm) {
	},

	onload: function(frm){
		frm.set_query("company_address", function(doc) {
            return {
                query: 'frappe.contacts.doctype.address.address.address_query',
                filters: {
                    link_doctype: "Company",
                    link_name: "RIGPL"
                }
            };
		});
	},
});