// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt
frappe.ui.form.on('Salary Structure', {
	refresh: function(frm) {
	},
	
	onload: function(frm){
		frm.set_query("salary_component", "earnings", function(doc, cdt, cdn) {
			return {
				"filters": {
					"is_earning": 1,
				}
			};
		});
		frm.set_query("salary_component", "deductions", function(doc, cdt, cdn) {
			return {
				"filters": {
					"is_deduction": 1,
				}
			};
		});
		frm.set_query("salary_component", "contributions", function(doc, cdt, cdn) {
			return {
				"filters": {
					"is_contribution": 1,
				}
			};
		});
	},
});