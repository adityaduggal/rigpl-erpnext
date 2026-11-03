#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
"""
Shared reads of the monthly attendance reports (Employee Attendance, Monthly Attendance Time
Based). Each function does a fixed number of queries for any number of employees (#187).
"""
from calendar import monthrange
from datetime import date, timedelta
from typing import Dict, Iterable

import frappe
from frappe.utils import cint, getdate

from rigpl_erpnext.utils.item_attribute_utils import chunks

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
# filter: Employee field
EMPLOYEE_FILTERS = {"employee": "name", "branch": "branch", "department": "department", "designation": "designation"}


def get_month(filters) -> frappe._dict:
    """{month, year, days, from_date, to_date} of the Month (Jan..Dec) and Year filters."""
    if filters.get("month") not in MONTHS or not cint(filters.get("year")):
        frappe.throw("Select a Month (Jan to Dec) and a Year", title="Month and Year Needed")
    month, year = MONTHS.index(filters["month"]) + 1, cint(filters["year"])
    days = monthrange(year, month)[1]
    return frappe._dict(month=month, year=year, days=days, from_date=date(year, month, 1),
        to_date=date(year, month, days))


def get_employees(filters) -> Dict[str, frappe._dict]:
    """{employee: {name, employee_name, holiday_list}} of the employees that pass the filters and that
    the user can read (#206). The reports show Attendance only for these employees."""
    emp_filters = {"docstatus": 0}
    emp_filters.update({field: filters[key] for key, field in EMPLOYEE_FILTERS.items() if filters.get(key)})
    rows = frappe.get_list("Employee", filters=emp_filters, fields=["name", "employee_name", "holiday_list"],
        limit_page_length=0)
    return {row.name: row for row in rows}


def get_holidays_by_day(employees: Dict[str, frappe._dict], from_date, to_date) -> Dict[str, Dict[int, str]]:
    """{employee: {day of month: holiday description}} from the Holiday List of each employee."""
    lists = {row.holiday_list for row in employees.values() if row.holiday_list}
    by_list: Dict[str, Dict[int, str]] = {}
    hol = frappe.qb.DocType("Holiday")
    for chunk in chunks(lists):
        rows = (
            frappe.qb.from_(hol)
            .select(hol.parent, hol.holiday_date, hol.description)
            .where((hol.parenttype == "Holiday List") & hol.parent.isin(chunk))
            .where(hol.holiday_date[getdate(from_date):getdate(to_date)])
            .run(as_dict=1)
        )
        for row in rows:
            by_list.setdefault(row.parent, {})[row.holiday_date.day] = row.description
    return {name: by_list[row.holiday_list] for name, row in employees.items() if row.holiday_list in by_list}


def get_leaves_by_day(employees: Iterable[str], from_date, to_date) -> Dict[str, Dict[int, str]]:
    """
    {employee: {day of month: leave type}} of the approved, submitted Leave Applications in the
    period. 1 query for each chunk, in place of 1 query for each day.
    """
    from_date, to_date = getdate(from_date), getdate(to_date)
    la = frappe.qb.DocType("Leave Application")
    leaves: Dict[str, Dict[int, str]] = {}
    for chunk in chunks(employees):
        rows = (
            frappe.qb.from_(la)
            .select(la.employee, la.from_date, la.to_date, la.leave_type)
            .where((la.status == "Approved") & (la.docstatus == 1) & la.employee.isin(chunk))
            .where((la.from_date <= to_date) & (la.to_date >= from_date))
            .orderby(la.from_date)
            .run(as_dict=1)
        )
        for row in rows:
            day = max(row.from_date, from_date)
            while day <= min(row.to_date, to_date):
                leaves.setdefault(row.employee, {})[day.day] = row.leave_type
                day += timedelta(days=1)
    return leaves
