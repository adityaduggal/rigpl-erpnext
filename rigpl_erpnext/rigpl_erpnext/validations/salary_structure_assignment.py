# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import flt, getdate, add_days
from erpnext.hr.doctype.payroll_entry.payroll_entry import get_start_end_dates


def validate(doc, method):
    # Validate To Date only should be after the next SSA is created
    ssa = frappe.db.sql("""SELECT name, to_date, from_date FROM `tabSalary Structure Assignment`
        WHERE employee = '%s' AND from_date > '%s' ORDER BY from_date ASC LIMIT 1""" % (doc.employee, doc.from_date), as_dict=1)
    if ssa:
        actual_to_date = add_days(ssa[0].from_date, -1)
        if doc.to_date != actual_to_date:
            frappe.throw(f"For {doc.name} From Date Should be {actual_to_date}")
    else:
        if doc.to_date:
            frappe.throw(f"For {doc.name} there is No Future SSA hence To Date should be Blank")


    date_details = get_start_end_dates("Monthly", doc.from_date)
    doj = frappe.db.get_value("Employee", doc.employee, "date_of_joining")

    if date_details.end_date > doj >= date_details.start_date:
        doc.from_date = doj
    else:
        doc.from_date = date_details.start_date

    if flt(doc.minimum_applicable) > 0:
        if flt(doc.basic_percent) > 0:
            if ((doc.base + flt(doc.variable)) * flt(doc.basic_percent)) / 100 < flt(doc.minimum_applicable):
                frappe.throw("Basic Salary Cannot be Less than Minimum Applicable")


def on_submit(doc, method):
    # On Submit update the to_date in all ssa for an employee
    correct_to_date_for_ssa(doc.employee)


def correct_to_date_for_ssa(emp_id, frm_date=None):
    ssa = frappe.db.sql("""SELECT name, employee, from_date, to_date FROM `tabSalary Structure Assignment`
        WHERE docstatus=1 AND employee= '%s' ORDER BY from_date ASC""" % emp_id, as_dict=1)
    if len(ssa) >= 1:
        for i in range(len(ssa)):
            if i < len(ssa) - 1:
                actual_to_date = add_days(ssa[i+1].from_date, -1)
                if ssa[i].to_date != actual_to_date:
                    frappe.db.set_value("Salary Structure Assignment", ssa[i].name, "to_date", actual_to_date)
                    print(f"For {ssa[i].name} Changed To Date from Current Date: {ssa[i].to_date} To: {actual_to_date}")
            else:
                if ssa[i].to_date:
                    frappe.db.set_value("Salary Structure Assignment", ssa[i].name, "to_date", None)
                    print(f"For {ssa[i].name} Removed To Date as its the Latest Salary Structure")
    else:
        print(f"{emp_id} has No Salary Structure Assignments")
