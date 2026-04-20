# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from frappe.utils import formatdate, getdate
import frappe
from frappe.model.document import Document
from frappe.utils import flt
from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries
from erpnext.accounts.utils import get_fiscal_years
import math


class EmployeeAdvanceRIGPL(Document):
    def validate(self):
        self.total_loan = 0

        all_employee = []

        for i in self.employee_loan_detail:
            # Populate Employee Name
            emp_doc = frappe.get_doc("Employee", i.employee)
            i.employee_name = emp_doc.employee_name

            loan_amount = i.loan_amount or 0
            emi = i.emi or 0
            repayment_period = i.repayment_period or 0

            # Validate required financial values
            if loan_amount <= 0:
                frappe.throw("Loan Amount must be greater than ZERO")

            if emi <= 0:
                frappe.throw("EMI must be greater than ZERO")

            # Round EMI to nearest 10
            if emi % 10 != 0:
                emi = int(math.ceil(emi / 10)) * 10
                i.emi = emi

            # Calculate repayment period safely
            expected_total = emi * repayment_period
            if expected_total != loan_amount:
                i.repayment_period = int(math.ceil(loan_amount / emi))

            # Check negative values
            if loan_amount < 0 or emi < 0 or i.repayment_period < 0:
                frappe.throw(
                    "Loan Amount, EMI and Repayment Period should be greater than ZERO"
                )

            # Duplicate employee check
            all_employee.append(i.employee)
            if all_employee.count(i.employee) > 1:
                frappe.throw(
                    f"{i.employee_name} is entered multiple times"
                )

            # Active employee check
            pd = getdate(self.posting_date)
            rd = getdate(emp_doc.relieving_date)

            if emp_doc.status != "Active" and rd and rd < pd:
                frappe.throw(
                    f"{i.employee_name} left on {rd} hence cannot give advance on {pd}"
                )

            self.total_loan += loan_amount

    def on_update(self):
        pass

    def on_submit(self):
        gl_map = []
        fiscal_years = get_fiscal_years(self.posting_date, company='RIGPL')
        if len(fiscal_years) > 1:
            frappe.throw(_("Multiple fiscal years exist for the date {0}. \
				Please set company in Fiscal Year").format(formatdate(self.posting_date)))
        else:
            fiscal_year = fiscal_years[0][0]

        for emp in self.employee_loan_detail:
            if emp.loan_amount:
                gl_dict = frappe._dict({
                    'company': 'RIGPL',
                    'posting_date': self.posting_date,
                    'fiscal_year': fiscal_year,
                    'voucher_type': 'Employee Advance RIGPL',
                    'voucher_no': self.name,
                    'account': self.debit_account,
                    'debit': flt(emp.loan_amount),
                    'debit_in_account_currency': flt(emp.loan_amount),
                    'party_type': 'Employee',
                    'party': emp.employee,
                    'against': self.credit_account
                })
                gl_map.append(gl_dict)
        if gl_map:
            gl_dict = frappe._dict({
                'company': 'RIGPL',
                'posting_date': self.posting_date,
                'fiscal_year': fiscal_year,
                'voucher_type': 'Employee Advance RIGPL',
                'voucher_no': self.name,
                'account': self.credit_account,
                'debit': 0,
                'credit': flt(self.total_loan),
                'credit_in_account_currency': flt(self.total_loan),
                'debit_in_account_currency': 0,
                'against': self.debit_account
            })
            gl_map.append(gl_dict)
            make_gl_entries(gl_map, cancel=0, adv_adj=0)

    def on_cancel(self):
        make_reverse_gl_entries(None, 'Employee Advance RIGPL', self.name)
