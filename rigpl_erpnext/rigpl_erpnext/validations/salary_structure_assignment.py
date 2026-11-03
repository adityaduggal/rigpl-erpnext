# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import flt, getdate, add_days
from erpnext.payroll.doctype.payroll_entry.payroll_entry import get_start_end_dates


def validate(doc, method):
    set_from_date(doc)
    validate_to_date(doc)

    if flt(doc.minimum_applicable) > 0:
        if flt(doc.basic_percent) > 0:
            if ((doc.base + flt(doc.variable)) * flt(doc.basic_percent)) / 100 < flt(doc.minimum_applicable):
                frappe.throw("Basic Salary Cannot be Less than Minimum Applicable")


def on_submit(doc, method):
    # On Submit update the to_date in all ssa for an employee
    correct_to_date_for_ssa(doc.employee)


def set_from_date(doc):
    """SSA starts on the month start, or on the joining date if the employee joined in that month"""
    date_details = get_start_end_dates("Monthly", doc.from_date)
    doj = frappe.db.get_value("Employee", doc.employee, "date_of_joining")

    if date_details.end_date > doj >= date_details.start_date:
        doc.from_date = doj
    else:
        doc.from_date = date_details.start_date


def validate_to_date(doc):
    """To Date is the day before the next submitted SSA, or blank for the latest SSA"""
    next_from = frappe.get_all("Salary Structure Assignment", filters={"employee": doc.employee,
        "from_date": (">", doc.from_date), "docstatus": 1, "name": ("!=", doc.name or "")},
        pluck="from_date", order_by="from_date asc", limit=1)
    if next_from:
        actual_to_date = add_days(next_from[0], -1)
        if not doc.to_date or getdate(doc.to_date) != actual_to_date:
            frappe.throw(f"For {doc.name} To Date should be {actual_to_date}")
    elif doc.to_date:
        frappe.throw(f"For {doc.name} there is No Future SSA hence To Date should be Blank")


def correct_to_date_for_ssa(emp_id, frm_date=None):
    ssa = frappe.get_all("Salary Structure Assignment", filters={"docstatus": 1, "employee": emp_id},
        fields=["name", "from_date", "to_date"], order_by="from_date asc")
    for i, row in enumerate(ssa):
        actual_to_date = add_days(ssa[i + 1].from_date, -1) if i < len(ssa) - 1 else None
        if row.to_date != actual_to_date:
            frappe.db.set_value("Salary Structure Assignment", row.name, "to_date", actual_to_date)
