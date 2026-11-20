# -*- coding: utf-8 -*-
"""
Loan fields on the ERPNext Employee Advance (#228). A loan is an advance with deduction_type set. The
Salary Slip deducts its EMI (validations/salary_slip.py).
"""
import math
from typing import Tuple

import frappe
from frappe import _
from frappe.utils import flt


def validate(doc, method):
    if not doc.deduction_type:
        if flt(doc.emi):
            frappe.throw(_("EMI {0} needs a Deduction Type. Set the Deduction Type or clear the EMI").format(
                doc.emi), title=_("Loan Without Deduction Type"))
        doc.repayment_period = 0
        return
    doc.emi, doc.repayment_period = get_emi_and_period(doc.advance_amount, doc.emi, doc.repayment_period)
    validate_loan_amounts(doc.advance_amount, doc.emi, doc.repayment_period)


def get_emi_and_period(amount, emi, period) -> Tuple[float, float]:
    """v12 rule: when amount != EMI x period, round the EMI up to a multiple of 10 and set the period"""
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
