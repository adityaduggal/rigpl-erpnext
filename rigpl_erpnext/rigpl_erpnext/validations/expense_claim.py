# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt


def validate(doc, method):
    doc.department = frappe.get_value("Employee", doc.employee, "department")
    remove_loan_advances(doc)


def remove_loan_advances(doc):
    """
    A loan (Employee Advance with Repay Unclaimed Amount from Salary, #236) is paid back from the Salary Slip,
    not by a claim. ERPNext Get Advances adds every paid advance, so drop the loan rows and stop an allocated one.
    """
    names = [row.employee_advance for row in doc.get("advances") if row.employee_advance]
    if not names:
        return
    loans = set(frappe.get_all("Employee Advance",
        filters={"name": ("in", names), "repay_unclaimed_amount_from_salary": 1}, pluck="name"))
    if not loans:
        return
    for row in doc.advances:
        if row.employee_advance in loans and flt(row.allocated_amount):
            frappe.throw(_("Row {0}: Employee Advance {1} is a loan and is paid back from the Salary Slip. "
                "Set its Allocated Amount {2} to 0").format(row.idx, row.employee_advance, row.allocated_amount),
                title=_("Loan in Expense Claim"))
    doc.set("advances", [row for row in doc.advances if row.employee_advance not in loans])
    for idx, row in enumerate(doc.advances, 1):
        row.idx = idx
