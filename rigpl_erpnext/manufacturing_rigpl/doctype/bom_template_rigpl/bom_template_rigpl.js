// Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt


frappe.ui.form.on('BOM Template RIGPL', {
	onload: function(frm){
		frm.set_query("item_template", function(doc) {
			return {
				"filters": {
					"has_variants": 1,
					"disabled": 0,
					"include_item_in_manufacturing": 1
				}
			};
		});
	},
});