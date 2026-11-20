# -*- coding: utf-8 -*-
"""
Loans on the ERPNext Employee Advance (#228, #236). A loan is an advance with the vanilla field
Repay Unclaimed Amount from Salary ticked. The Salary Slip deducts its EMI (validations/salary_slip.py).
"""
import math
from typing import Tuple

import frappe
from frappe import _
from frappe.utils import cint, flt

DEFAULT_LOAN_COMPONENT = "Loan Deduction"


def validate(doc, method):
    if not doc.advance_account and doc.company:
        doc.advance_account = frappe.get_cached_value("Company", doc.company, "default_employee_advance_account")
    if not is_loan(doc):
        if flt(doc.emi):
            frappe.throw(_("EMI {0} is only for a loan. Tick Repay Unclaimed Amount from Salary, or clear the EMI")
                .format(doc.emi), title=_("EMI Without Loan"))
        doc.deduction_type = None
        doc.repayment_period = 0
        return
    doc.deduction_type = doc.deduction_type or get_loan_component()
    doc.emi, doc.repayment_period = get_whole_month_emi(doc.advance_amount, doc.emi)


def validate_additional_salary(doc, method):
    """
    The vanilla button Deduction from Salary makes an Additional Salary for the advance. The rigpl Salary Slip
    ignores Additional Salary, but its submit changes the advance's return_amount, so a loan would go wrong.
    """
    if doc.ref_doctype != "Employee Advance" or not doc.ref_docname:
        return
    if cint(frappe.db.get_value("Employee Advance", doc.ref_docname, "repay_unclaimed_amount_from_salary")):
        frappe.throw(_("Employee Advance {0} is a loan. The Salary Slip deducts its EMI, so do not make an "
            "Additional Salary for it").format(doc.ref_docname), title=_("Loan in Additional Salary"))


def is_loan(doc) -> bool:
    return bool(cint(doc.repay_unclaimed_amount_from_salary))


def get_loan_component() -> str:
    return frappe.db.get_single_value("RIGPL Settings", "loan_deduction_component") or DEFAULT_LOAN_COMPONENT


def get_whole_month_emi(amount, emi) -> Tuple[float, int]:
    """
    EMI rounded up to a multiple of 100 (not above the amount), and the period in whole months.
    The last Salary Slip deducts the rest: 20000 with EMI 3500 is 6 months, the last one 2500.
    """
    amount, emi = flt(amount), flt(emi)
    if amount <= 0 or amount % 1:
        frappe.throw(_("Advance Amount {0} of a loan should be a whole number greater than ZERO").format(amount))
    if emi <= 0 or emi % 1:
        frappe.throw(_("EMI {0} should be a whole number greater than ZERO").format(emi))
    emi = min(math.ceil(emi / 100) * 100, amount)
    return emi, math.ceil(amount / emi)


def get_emi_and_period(amount, emi, period) -> Tuple[float, float]:
    """v12 rule of Employee Advance RIGPL (until #235): EMI rounded up to 10, the period can be a fraction"""
    amount, emi, period = flt(amount), flt(emi), flt(period)
    if emi <= 0 or amount == emi * period:
        return emi, period
    if emi % 10:
        emi = math.ceil(emi / 10) * 10
    return emi, amount / emi


def validate_loan_amounts(amount, emi, period):
    if flt(amount) % 1 or flt(emi) % 1:
        frappe.throw(_("Loan Amount and EMI should be multiples of 1"))
    if flt(amount) < 0 or flt(emi) <= 0 or flt(period) < 0:
        frappe.throw(_("Loan Amount, EMI and Repayment Period should be greater than ZERO"))
