# -*- coding: utf-8 -*-
# Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt
"""
One sheet to give loans to many employees (#231). The Single keeps no batch document: Create Advances makes
one draft Employee Advance per row and one draft Journal Entry that pays them, so the user can still change
them. The user submits the advances, then the Journal Entry. The Journal Entry is the batch record: on submit,
ERPNext sets the paid amount and the status Paid of each advance from it.
"""
from collections import Counter

import erpnext
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, formatdate, getdate

from rigpl_erpnext.rigpl_erpnext.validations.employee_advance import get_loan_component, validate_loan_amounts

SAVEPOINT = "employee_advance_tool"
VOUCHER_TYPES = {"Bank": "Bank Entry", "Cash": "Cash Entry"}


class EmployeeAdvanceTool(Document):
    @frappe.whitelist()
    def create_advances(self):
        """One transaction: any error undoes the advances and the Journal Entry. Returns the Journal Entry name."""
        self.check_permission("write")
        employees = self.validate_rows()
        frappe.db.savepoint(SAVEPOINT)
        try:
            advances = [self.make_advance(row, employees[row.employee]) for row in self.employee_loan_detail]
            journal = self.make_journal_entry(advances)
        except Exception:
            frappe.db.rollback(save_point=SAVEPOINT)
            raise
        self.set("employee_loan_detail", [])
        self.reference_no = self.reference_date = None
        self.save()
        return journal.name

    def validate_rows(self):
        """Checks every row before anything is made. Returns {employee: Employee row}."""
        if not self.employee_loan_detail:
            frappe.throw(_("Add at least one employee"))
        employees = get_employees([row.employee for row in self.employee_loan_detail])
        duplicates = [emp for emp, count in Counter(row.employee for row in self.employee_loan_detail).items()
            if count > 1]
        if duplicates:
            frappe.throw(_("{0} is entered multiple times").format(employees[duplicates[0]].employee_name))
        if self.get_voucher_type() == "Bank Entry" and not (self.reference_no and self.reference_date):
            frappe.throw(_("Reference No and Reference Date are required when the Payment Account is a Bank account"))
        posting_date = getdate(self.posting_date)
        for row in self.employee_loan_detail:
            emp = employees[row.employee]
            validate_loan_amounts(row.loan_amount, row.emi, row.repayment_period)
            if emp.status != "Active" and emp.relieving_date and getdate(emp.relieving_date) < posting_date:
                frappe.throw(_("{0} left on {1} hence cannot give advance on {2}").format(
                    emp.employee_name, formatdate(emp.relieving_date), formatdate(posting_date)))
        return employees

    def get_voucher_type(self):
        return VOUCHER_TYPES.get(frappe.get_cached_value("Account", self.payment_account, "account_type"),
            "Journal Entry")

    def make_advance(self, row, employee):
        """A draft loan. Its validate (validations/employee_advance.py) makes the EMI whole months."""
        advance = frappe.get_doc(dict(doctype="Employee Advance", employee=row.employee,
            employee_name=employee.employee_name, posting_date=self.posting_date, company=self.company,
            purpose=self.purpose or _("Employee Loan"), advance_amount=row.loan_amount,
            advance_account=self.advance_account, currency=erpnext.get_company_currency(self.company),
            exchange_rate=1, repay_unclaimed_amount_from_salary=1, emi=row.emi,
            deduction_type=self.deduction_type or get_loan_component()))
        advance.insert()
        return advance

    def make_journal_entry(self, advances):
        """A draft that debits the advance account per employee and credits the payment account. is_advance makes
        ERPNext update the paid amount and the status of each advance when it is submitted and cancelled."""
        cost_center = erpnext.get_default_cost_center(self.company)
        journal = frappe.new_doc("Journal Entry")
        journal.update(dict(voucher_type=self.get_voucher_type(), company=self.company,
            posting_date=self.posting_date, cheque_no=self.reference_no, cheque_date=self.reference_date,
            user_remark=_("Employee Loans: {0}").format(
                self.purpose or ", ".join(advance.name for advance in advances))))
        for advance in advances:
            journal.append("accounts", dict(account=self.advance_account, party_type="Employee",
                party=advance.employee, debit_in_account_currency=advance.advance_amount,
                reference_type="Employee Advance", reference_name=advance.name, is_advance="Yes",
                cost_center=cost_center))
        journal.append("accounts", dict(account=self.payment_account, cost_center=cost_center,
            credit_in_account_currency=sum(flt(advance.advance_amount) for advance in advances)))
        journal.insert()
        return journal


def get_employees(names):
    rows = frappe.get_all("Employee", filters={"name": ("in", list(set(names)) or [""])},
        fields=["name", "employee_name", "status", "relieving_date"])
    return {row.name: row for row in rows}
