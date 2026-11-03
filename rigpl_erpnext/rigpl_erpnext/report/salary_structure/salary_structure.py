# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt
# -*- coding: utf-8 -*-

import frappe
from frappe.query_builder.functions import IfNull
from frappe.utils import getdate

from rigpl_erpnext.utils.item_attribute_utils import chunks
from rigpl_erpnext.utils.report_utils import blank_zeros, permitted_names

WITHOUT_SSA = "Employees without SSA"
NO_END = "2099-12-31"


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw("From Date cannot be after To Date")
    employees = get_employees(filters)
    assignments = get_assignments(filters, [emp.name for emp in employees])
    if filters.get("show") == WITHOUT_SSA:
        data = [[emp.name, emp.employee_name, emp.branch, emp.department, emp.designation, emp.date_of_joining,
            emp.relieving_date] for emp in employees if emp.name not in assignments]
        return without_ssa_columns(), data

    data = []
    for emp in employees:
        for ssa in pick_assignments(assignments.get(emp.name, []), filters.get("latest_salary")):
            data.append(blank_zeros([ssa.name, ssa.from_date, ssa.to_date, emp.name, emp.employee_name, emp.branch,
                emp.department, emp.designation, emp.date_of_joining, emp.relieving_date, ssa.base, ssa.variable,
                ssa.basic_percent, ssa.minimum_applicable, ssa.salary_structure]))
    return assignment_columns(), data


def pick_assignments(rows, latest_salary):
    """rows are in from_date order"""
    if latest_salary == "Latest":
        return rows[-1:]
    if latest_salary == "Earliest":
        return rows[:1]
    return rows


def assignment_columns():
    return ["SSA:Link/Salary Structure Assignment:60", "From Date:Date:80", "To Date:Date:80",
        "Employee:Link/Employee:80", "Employee Name::150", "Branch::80", "Department::120", "Designation::100",
        "Joining Date:Date:80", "Relieving Date:Date:80", "Base:Currency:100", "Variable:Currency:100",
        "Basic Percent:Percent:80", "Min App:Currency:80", "Salary Structure:Link/Salary Structure:120"]


def without_ssa_columns():
    return ["Employee ID:Link/Employee:100", "Employee Name::200", "Branch::80", "Department::120",
        "Designation::100", "Joining Date:Date:80", "Relieving Date:Date:80"]


def get_employees(filters):
    emp = frappe.qb.DocType("Employee")
    active = (emp.status == "Active") & (emp.date_of_joining <= filters.to_date)
    left = ((emp.status == "Left") & (emp.date_of_joining <= filters.to_date)
        & emp.relieving_date.between(filters.from_date, filters.to_date))
    status = filters.get("employee_status")
    query = (
        frappe.qb.from_(emp)
        .select(emp.name, emp.employee_name, emp.date_of_joining, emp.department, emp.designation, emp.branch,
            IfNull(emp.relieving_date, NO_END).as_("relieving_date"))
        .where((emp.docstatus == 0) & (active if status == "Active" else left if status == "Left" else active | left))
        .orderby(emp.date_of_joining)
    )
    for field in ("branch", "department", "designation"):
        if filters.get(field):
            query = query.where(emp[field] == filters[field])
    if filters.get("employee"):
        query = query.where(emp.name == filters.employee)
    allowed = permitted_names("Employee")
    employees = [row for row in query.run(as_dict=True) if row.name in allowed]
    if not employees:
        frappe.throw("No Employees in the Given Criterion")
    return employees


def get_assignments(filters, employees):
    """Submitted SSAs that overlap the dates and that the user can read (#206), by employee, in from_date
    order"""
    ssa = frappe.qb.DocType("Salary Structure Assignment")
    by_employee = {}
    for names in chunks(employees):
        rows = (
            frappe.qb.from_(ssa)
            .select(ssa.name, ssa.employee, ssa.from_date, IfNull(ssa.to_date, NO_END).as_("to_date"), ssa.base,
                ssa.variable, ssa.basic_percent, ssa.salary_structure, ssa.minimum_applicable)
            .where((ssa.docstatus == 1) & ssa.employee.isin(names) & (ssa.from_date <= filters.to_date)
                & (IfNull(ssa.to_date, NO_END) >= filters.from_date))
            .orderby(ssa.from_date)
        ).run(as_dict=True)
        allowed = permitted_names("Salary Structure Assignment", {"name": ["in", [row.name for row in rows]]})
        for row in rows:
            if row.name in allowed:
                by_employee.setdefault(row.employee, []).append(row)
    return by_employee
