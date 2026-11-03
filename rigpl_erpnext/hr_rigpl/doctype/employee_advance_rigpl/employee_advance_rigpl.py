# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt
"""
Employee loans (#199). One entry gives loans to many employees. Salary Slips deduct the EMI
(validations/salary_slip.py, get_loan_deduction). Renamed from Employee Advance, which is also an
ERPNext DocType. The move to the Lending app is planned for v16 (#200).
"""

import math
from collections import Counter

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, formatdate, getdate
from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries
from erpnext.accounts.utils import get_fiscal_years


class EmployeeAdvanceRIGPL(Document):
    def validate(self):
        employees = get_employees([row.employee for row in self.employee_loan_detail])
        duplicates = [emp for emp, count in Counter(row.employee for row in self.employee_loan_detail).items()
            if count > 1]
        if duplicates:
            frappe.throw(_("{0} is entered multiple times").format(employees[duplicates[0]].employee_name))

        posting_date = getdate(self.posting_date)
        self.total_loan = 0
        for row in self.employee_loan_detail:
            emp = employees[row.employee]
            row.employee_name = emp.employee_name
            set_emi_and_period(row)
            validate_amounts(row)
            if emp.status != "Active" and emp.relieving_date and getdate(emp.relieving_date) < posting_date:
                frappe.throw(_("{0} left on {1} hence cannot give advance on {2}").format(
                    emp.employee_name, formatdate(emp.relieving_date), formatdate(posting_date)))
            self.total_loan += flt(row.loan_amount)

    def on_submit(self):
        gl_map = self.get_gl_map()
        if gl_map:
            make_gl_entries(gl_map, cancel=0, adv_adj=0)

    def on_cancel(self):
        self.ignore_linked_doctypes = ("GL Entry",)
        make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)

    def get_gl_map(self):
        company = frappe.get_cached_value("Account", self.debit_account, "company")
        common = dict(company=company, posting_date=self.posting_date, fiscal_year=self.get_fiscal_year(company),
            voucher_type=self.doctype, voucher_no=self.name)
        gl_map = [frappe._dict(common, account=self.debit_account, debit=flt(row.loan_amount),
            debit_in_account_currency=flt(row.loan_amount), party_type="Employee", party=row.employee,
            against=self.credit_account) for row in self.employee_loan_detail if flt(row.loan_amount)]
        if gl_map:
            gl_map.append(frappe._dict(common, account=self.credit_account, debit=0, credit=flt(self.total_loan),
                credit_in_account_currency=flt(self.total_loan), debit_in_account_currency=0,
                against=self.debit_account))
        return gl_map

    def get_fiscal_year(self, company):
        fiscal_years = get_fiscal_years(self.posting_date, company=company)
        if len(fiscal_years) > 1:
            frappe.throw(_("Multiple fiscal years exist for the date {0}. Please set company in Fiscal Year").format(
                formatdate(self.posting_date)))
        return fiscal_years[0][0]


def get_employees(names):
    rows = frappe.get_all("Employee", filters={"name": ("in", list(set(names)) or [""])},
        fields=["name", "employee_name", "status", "relieving_date"])
    return {row.name: row for row in rows}


def set_emi_and_period(row):
    """v12 rule: when loan != EMI x period, round the EMI up to a multiple of 10 and set the period"""
    if flt(row.emi) <= 0 or flt(row.loan_amount) == flt(row.emi) * flt(row.repayment_period):
        return
    if flt(row.emi) % 10:
        row.emi = int(math.ceil(flt(row.emi) / 10)) * 10
    row.repayment_period = flt(row.loan_amount) / flt(row.emi)


def validate_amounts(row):
    if flt(row.loan_amount) % 1 or flt(row.emi) % 1:
        frappe.throw(_("Loan Amount and EMI should be multiples of 1"))
    if flt(row.loan_amount) < 0 or flt(row.emi) <= 0 or flt(row.repayment_period) < 0:
        frappe.throw(_("Loan Amount, EMI and Repayment Period should be greater than ZERO"))
