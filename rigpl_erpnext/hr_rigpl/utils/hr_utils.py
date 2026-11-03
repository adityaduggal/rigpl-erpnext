#  Copyright (c) 2022. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
# -*- coding: utf-8 -*-
from typing import Dict, Iterable, List, Optional

import frappe
from frappe.query_builder.functions import Count
from frappe.utils import flt, getdate

from rigpl_erpnext.utils.item_attribute_utils import chunks


def get_base_list_holiday_counts(base_lists: Iterable[str], frm_date, to_date) -> Dict[str, int]:
    """
    {base holiday list: number of holidays from frm_date to to_date} in the holiday lists made from
    each base list (is_base_list = 0). 1 query for each chunk.
    """
    hol = frappe.qb.DocType("Holiday")
    hl = frappe.qb.DocType("Holiday List")
    counts: Dict[str, int] = {}
    for chunk in chunks(base_lists):
        rows = (
            frappe.qb.from_(hol)
            .join(hl).on(hl.name == hol.parent)
            .select(hl.base_holiday_list, Count(hol.name))
            .where((hl.is_base_list == 0) & (hol.parenttype == "Holiday List") & hl.base_holiday_list.isin(chunk))
            .where(hol.holiday_date[getdate(frm_date):getdate(to_date)])
            .groupby(hl.base_holiday_list)
            .run()
        )
        counts.update(dict(rows))
    return counts


# Aadhaar rules (#194). They apply when the Country of the Employee's Branch has aadhaar_applicable.
# An Employee is blocked when another Active Employee has the same Aadhaar Number and a System
# Manager has not ticked allow_duplicate_aadhaar. A blocked Employee gets no Attendance and no
# Salary Slip.
BYPASS_LABEL = "Allow Duplicate Aadhaar"


def get_branch_country(branch: Optional[str]) -> Optional[str]:
    return frappe.get_cached_value("Branch", branch, "country") if branch else None


def is_aadhaar_applicable(country: Optional[str]) -> bool:
    return bool(country) and frappe.get_cached_value("Country", country, "aadhaar_applicable") == 1


def get_active_duplicates(aadhaar_numbers: Iterable[str]) -> Dict[str, List[str]]:
    """Returns {aadhaar_number: [Active Employees with it]}"""
    found = {}
    for chunk in chunks([num for num in aadhaar_numbers if num]):
        for row in frappe.get_all("Employee", filters={"aadhaar_number": ("in", chunk), "status": "Active"},
                fields=["name", "aadhaar_number"], order_by="name asc"):
            found.setdefault(row.aadhaar_number, []).append(row.name)
    return found


def get_aadhaar_blocked(employees: Iterable[str]) -> Dict[str, List[str]]:
    """Returns {Active employee: [other Active Employees with the same Aadhaar]} for the blocked employees"""
    rows = []
    for chunk in chunks(employees):
        rows += frappe.get_all("Employee", filters={"name": ("in", chunk), "status": "Active",
            "allow_duplicate_aadhaar": 0},
            fields=["name", "branch", "aadhaar_number"])
    rows = [row for row in rows if row.aadhaar_number and row.branch]
    if not rows:
        return {}
    branch_country = {}
    for chunk in chunks([row.branch for row in rows]):
        branch_country.update(frappe.get_all("Branch", filters={"name": ("in", chunk)},
            fields=["name", "country"], as_list=1))
    countries = list({country for country in branch_country.values() if country})
    applicable = set(frappe.get_all("Country", filters={"name": ("in", countries), "aadhaar_applicable": 1},
        pluck="name")) if countries else set()
    rows = [row for row in rows if branch_country.get(row.branch) in applicable]
    duplicates = get_active_duplicates([row.aadhaar_number for row in rows])
    blocked = {}
    for row in rows:
        others = [name for name in duplicates.get(row.aadhaar_number, []) if name != row.name]
        if others:
            blocked[row.name] = others
    return blocked


def block_message(employee: str, others: List[str], action: str) -> str:
    return "{} has the same Aadhaar Number as Active {}. A System Manager must tick {} in the Employee " \
        "before {}.".format(frappe.get_desk_link("Employee", employee),
            ", ".join(frappe.get_desk_link("Employee", other) for other in others), BYPASS_LABEL, action)


def check_aadhaar_block(employee: str, action: str):
    others = get_aadhaar_blocked([employee]).get(employee)
    if others:
        frappe.throw(block_message(employee, others, action), title="Duplicate Aadhaar")


def validate_attendance(doc, method):
    check_aadhaar_block(doc.employee, "any Attendance")


def validate_salary_slip(doc, method):
    check_aadhaar_block(doc.employee, "any Salary Slip")


def validate_payroll_entry(doc, method):
    """Removes the blocked employees, so the Salary Slips of the others are still made"""
    blocked = get_aadhaar_blocked([row.employee for row in doc.get("employees")])
    if not blocked:
        return
    doc.set("employees", [row for row in doc.get("employees") if row.employee not in blocked])
    for idx, row in enumerate(doc.employees, start=1):
        row.idx = idx
    doc.number_of_employees = len(doc.employees)
    frappe.msgprint("<br>".join(block_message(emp, others, "a Salary Slip is made. Removed from this Payroll Entry")
        for emp, others in blocked.items()), title="Duplicate Aadhaar", indicator="orange")


def get_half_day_fraction() -> float:
    """Part of a day that a Half Day counts as worked (Payroll Settings, 0.5 when blank)"""
    return flt(frappe.db.get_single_value("Payroll Settings", "daily_wages_fraction_for_half_day")) or 0.5
