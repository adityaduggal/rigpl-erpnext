// Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on('Made to Order Item Attributes', {
	onload: function(frm){
		frm.set_query("reference_item_code", function(doc) {
			return {
				"filters": {
					"disabled": 0,
					"has_variants": 0,
					"include_item_in_manufacturing":1,
					"is_sales_item":1
				}
			};
		});
		frm.set_query("reference_spl", function(doc) {
			return {
                filters: [
                    ['name', '!=', doc.name],
                    ['docstatus', '!=', 0]
                ]
			};
		});
	},
	copy_attributes_from_item: function(frm) {
		frappe.call({
			doc: frm.doc,
			method: "copy_attributes_from_item",
			callback: function(r) {
				refresh_field("attributes");
			}
		});
	},
	copy_attributes_from_another_spl: function(frm) {
		frappe.call({
			doc: frm.doc,
			method: "copy_attributes_from_another_spl",
			callback: function(r) {
				refresh_field("attributes");
			}
		});
	}
});
