// Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on('Employee Advance Tool', {
	setup: function(frm) {
		frm.set_query('advance_account', () => ({filters: {company: frm.doc.company, is_group: 0, account_type: 'Receivable'}}));
		frm.set_query('payment_account', () => ({filters: {company: frm.doc.company, is_group: 0, account_type: ['in', ['Bank', 'Cash']]}}));
	},

	refresh: function(frm) {
		frm.disable_save();
		if (!frm.doc.company) {
			frm.set_value('company', frappe.defaults.get_user_default('Company'));
		}
		frm.page.set_primary_action(__('Create Advances'), () => {
			frm.call('create_advances').then((r) => {
				if (!r.exc && r.message) {
					frappe.msgprint(__('Loans are paid with Journal Entry {0}', [frappe.utils.get_form_link('Journal Entry', r.message, true)]));
					frm.reload_doc();
				}
			});
		});
	}
});

// Same rule as validations/employee_advance.py: EMI is a multiple of 100 and not above the amount
frappe.ui.form.on('Employee Loan Detail', {
	loan_amount: function(frm, cdt, cdn) {
		if (frm.doctype === 'Employee Advance Tool') rigpl_loan_row(cdt, cdn);
	},
	emi: function(frm, cdt, cdn) {
		if (frm.doctype === 'Employee Advance Tool') rigpl_loan_row(cdt, cdn);
	}
});

function rigpl_loan_row(cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!(row.loan_amount > 0) || !(row.emi > 0)) return;
	const emi = Math.min(Math.ceil(row.emi / 100) * 100, row.loan_amount);
	frappe.model.set_value(cdt, cdn, 'emi', emi);
	frappe.model.set_value(cdt, cdn, 'repayment_period', Math.ceil(row.loan_amount / emi));
}
