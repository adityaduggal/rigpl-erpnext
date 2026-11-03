# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt
from __future__ import division
from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import IfNull, Sum
from pypika.terms import Case
from frappe.utils import getdate, flt
from math import ceil
from ....hr_rigpl.utils.hr_utils import get_base_list_holiday_counts
from ....utils.item_attribute_utils import chunks


def execute(filters=None):
    """
    Executes the report
    """
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_entries(filters)

    return columns, data


def get_columns():
    """
    Returns Columns for Report
    """
    return [
        "Employee#:Link/Employee:100", "Employee Name::150", "TD:Int:50",
        "Hol:Int:50", "Pres:Int:50", "OT:Float:50",
        "Auth Lea:Int:50", "UnAuth Lea:Int:50", "Att%:Float:100", "Adj Att%:Float:100",
        "Absents:Int:50", "DoJ:Date:80", "DoR:Date:80", "Branch::80", "Department::80",
        "Designation::80"
    ]


def get_entries(filters):
    """
    Gets entries for the set filters. The holidays, presents, overtime and approved leaves of all
    employees come from 4 grouped queries, in place of 4 subqueries for each employee.
    """
    from_date, to_date = check_dates(filters)
    total_days = (to_date - from_date).days + 1
    employees = get_employees(filters, from_date)
    names = [emp.name for emp in employees]
    holiday_counts = get_base_list_holiday_counts({emp.holiday_list for emp in employees if emp.holiday_list},
        from_date, to_date)
    presents, overtime = get_attendance_totals(names, from_date, to_date)
    auth_leaves = get_leave_totals(names, from_date, to_date)

    data = []
    for emp in employees:
        base_hols = holiday_counts.get(emp.holiday_list, 0)
        present = presents.get(emp.name, 0)
        auth = flt(auth_leaves.get(emp.name))
        if emp.date_of_joining > from_date:
            act_tot_days = (to_date - emp.date_of_joining).days + 1
        elif getdate(emp.relieving_date) < to_date:
            act_tot_days = (getdate(emp.relieving_date) - from_date).days + 1
        else:
            act_tot_days = total_days
        # No of Holidays is pro-rata based on no of Total Working Days of an Employee
        if act_tot_days != total_days:
            holidays = int(base_hols / total_days * act_tot_days)
        else:
            holidays = base_hols

        base_wd = act_tot_days - holidays
        # No of Holidays also depends on the No of Presents of an Employee
        cal_hols = ceil(holidays * present / base_wd) if base_wd else holidays
        ual = act_tot_days - cal_hols - present - auth
        if ual < 0:
            ual = 0

        absents = act_tot_days - present - holidays
        working_days = max(act_tot_days - holidays, 1)
        att_per = (present / working_days) * 100
        adj_att_per = ((present - ual) / working_days) * 100

        data.append([emp.name, emp.employee_name, act_tot_days, holidays, present, overtime.get(emp.name),
            auth, ual, att_per, adj_att_per, absents, emp.date_of_joining, emp.relieving_date, emp.branch,
            emp.department, emp.designation])
    return data


def check_dates(filters):
    from_date, to_date = getdate(filters.get("from_date")), getdate(filters.get("to_date"))
    if from_date >= to_date:
        frappe.throw("From Date Cannot be Greater than or Equal to To Date", title="Wrong Period")
    return from_date, to_date


def get_employees(filters, from_date):
    """The employees not relieved before from_date, by name."""
    emp = frappe.qb.DocType("Employee")
    query = (
        frappe.qb.from_(emp)
        .select(emp.name, emp.employee_name, emp.date_of_joining,
            IfNull(emp.relieving_date, "2099-12-31").as_("relieving_date"), emp.branch, emp.department,
            emp.designation, emp.holiday_list)
        .where(IfNull(emp.relieving_date, "2099-12-31") >= from_date)
        .orderby(emp.name)
    )
    for key, field in (("branch", "branch"), ("department", "department"), ("employee", "name")):
        if filters.get(key):
            query = query.where(emp[field] == filters[key])
    return query.run(as_dict=1)


def get_attendance_totals(employees, from_date, to_date):
    """({employee: presents}, {employee: overtime}) of the submitted Attendance of the period."""
    at = frappe.qb.DocType("Attendance")
    present = Sum(Case().when(at.status == "Present", 1).else_(0))
    presents, overtime = {}, {}
    for chunk in chunks(employees):
        rows = (
            frappe.qb.from_(at)
            .select(at.employee, present, Sum(at.overtime))
            .where((at.docstatus == 1) & at.employee.isin(chunk) & at.attendance_date[from_date:to_date])
            .groupby(at.employee)
            .run()
        )
        for employee, count, ot in rows:
            presents[employee] = int(count or 0)
            overtime[employee] = ot
    return presents, overtime


def get_leave_totals(employees, from_date, to_date):
    """{employee: approved leave days} of the Leave Applications that are inside the period."""
    la = frappe.qb.DocType("Leave Application")
    totals = {}
    for chunk in chunks(employees):
        rows = (
            frappe.qb.from_(la)
            .select(la.employee, Sum(la.total_leave_days))
            .where((la.docstatus == 1) & (la.status == "Approved") & la.employee.isin(chunk))
            .where((la.to_date <= to_date) & (la.from_date >= from_date))
            .groupby(la.employee)
            .run()
        )
        totals.update(dict(rows))
    return totals
