// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt
frappe.ui.form.on('Salary Component', {
	refresh: function(frm) {
	},
	
	onload: function(frm){
		frm.set_query("account", function() {
			return {
				"filters": {
					"is_group": 0,
					"freeze_account": "No",
				}
			};
		});
		frm.set_query("earning", function() {
			return {
				"filters": {
					"is_earning": 1,
					"only_for_deductions": 1,
				}
			};
		});
		frm.set_query("salary_component", "deduction_contribution_formula", function(doc, cdt, cdn) {
			return {
				"filters": {
					"is_earning": 0,
				}
			};
		});
	},
});
cur_frm.add_fetch("salary_component", "is_deduction", "is_deduction");
cur_frm.add_fetch("salary_component", "is_contribution", "is_contribution");