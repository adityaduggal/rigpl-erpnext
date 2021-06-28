# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils import flt, cstr
from erpnext.hr.doctype.salary_slip.salary_slip import SalarySlip


def execute(filters=None):
    data = []
    columns = get_columns(filters)
    emp_lst = get_employee(filters)
    for emp in emp_lst:
        ssa = get_salary_str(filters, emp.name)
        if filters.get("without_salary_structure") != 1 and ssa:
            for ss in ssa:
                row = [ss.name, ss.from_date, ss.to_date, emp.name, emp.employee_name, emp.branch, emp.department,
                emp.designation, emp.date_of_joining, emp.relieving_date, ss.base, ss.variable, ss.basic_percent,
                ss.minimum_applicable, ss.salary_structure]
                data.append(row)
        elif filters.get("without_salary_structure") == 1 and not ssa:
            row = [emp.name, emp.employee_name, emp.branch, emp.department, emp.designation, emp.date_of_joining,
            emp.relieving_date]
            data.append(row)
    return columns, data


def get_salary_str(filters, employee_id):
    ss = frappe._dict({})
    salary_str = []
    conditions_emp, conditions_ss, filters = get_conditions(filters)
    if filters.get("latest_salary") == "All":
        LIMIT_KEY = " ASC"
    elif filters.get("latest_salary") == "Latest":
        LIMIT_KEY = " DESC LIMIT 1"
    elif filters.get("latest_salary") == "Earliest":
        LIMIT_KEY = " ASC LIMIT 1"

    salary_str = frappe.db.sql("""SELECT ss.name, ss.from_date, IFNULL(ss.to_date, '2099-12-31') as to_date,
        ss.employee, ss.base, ss.variable, ss.basic_percent, ss.salary_structure, ss.minimum_applicable
        FROM `tabSalary Structure Assignment` ss
        WHERE ss.docstatus = 1 AND ss.employee = '%s' %s
        ORDER BY ss.from_date %s""" % (employee_id, conditions_ss, LIMIT_KEY), as_dict=1)
    return salary_str


def get_employee(filters):
    conditions_emp, conditions_ss, filters = get_conditions(filters)
    if filters.get("show_left_employees") != 1:
        emp_stat = " AND emp.status = 'Active'"
    else:
        emp_stat = " AND emp.status = 'Left'"

    query = """SELECT emp.name, emp.employee_name, emp.date_of_joining, emp.status, emp.department, emp.designation,
    emp.branch, IFNULL(emp.relieving_date, '2099-12-31') as relieving_date
    FROM `tabEmployee` emp WHERE emp.docstatus =0 %s %s ORDER BY emp.date_of_joining""" % (conditions_emp, emp_stat)
    emp_lst = frappe.db.sql(query, as_dict=1)
    if emp_lst:
        pass
    else:
        frappe.throw("No Employees in the Given Criterion")
    return emp_lst


def get_columns(filters):
    if filters.get("without_salary_structure")!=1:
        columns = [
                "SSA:Link/Salary Structure Assignment:60", "From Date:Date:80",
                "To Date:Date:80", "Employee:Link/Employee:80", "Employee Name::150",
                "Branch::80", "Department::120", "Designation::100", "Joining Date:Date:80",
                "Relieving Date:Date:80", "Base:Currency:100", "Variable:Currency:100",
                "Basic Percent:Percent:80", "Min App:Currency:80",
                "Salary Structure:Link/Salary Structure:120"
        ]
    else:
        columns = [
                "Employee ID:Link/Employee:100", "Employee Name::200", "Branch::80", "Department::120",
                "Designation::100", "Joining Date:Date:80", "Relieving Date:Date:80"
                ]
    return columns


def get_conditions(filters):
    conditions_emp = ""
    conditions_ss = ""

    if filters.get("branch"):
        conditions_emp += " AND emp.branch = '%s'" % filters["branch"]

    if filters.get("department"):
        conditions_emp += " AND emp.department = '%s'" % filters["department"]

    if filters.get("designation"):
        conditions_emp += " AND emp.designation = '%s'" % filters["designation"]

    if filters.get("employee"):
        conditions_emp += " AND emp.name = '%s'" % filters["employee"]

    if filters.get("from_date") and filters.get("to_date"):
        if filters["from_date"] > filters["to_date"]:
            frappe.throw("From Date cannot be after To Date")
        else:
            if filters.get("show_left_employees") == 1:
                conditions_emp += " AND emp.date_of_joining <= '%s' AND emp.relieving_date BETWEEN '%s' AND '%s'" % \
                    (filters["to_date"], filters["from_date"], filters["to_date"])
            else:
                conditions_emp += " AND emp.date_of_joining <= '%s' AND emp.status = 'Active'" % filters["to_date"]

            conditions_ss += " AND ((ss.from_date <='%s' AND IFNULL(ss.to_date, '2099-12-31') <= '%s' AND \
                IFNULL(ss.to_date, '2099-12-31') >= '%s') OR (ss.from_date <= '%s' AND IFNULL(ss.to_date, '2099-12-31') >= '%s'))" % \
                    (filters["from_date"], filters["to_date"], filters["from_date"],
                    filters["to_date"], filters["from_date"])
    return conditions_emp, conditions_ss, filters
