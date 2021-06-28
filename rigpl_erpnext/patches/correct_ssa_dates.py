# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from ..rigpl_erpnext.validations.salary_structure_assignment import correct_to_date_for_ssa


def execute():
    emp_list = frappe.db.sql("""SELECT name, employee_name, date_of_joining FROM `tabEmployee` ORDER BY date_of_joining""", as_dict=1)
    for emp in emp_list:
        correct_to_date_for_ssa(emp.name)
