"""
Leave credit from attendance (#202). Each day, each earned leave type (Leave Type is_earned_leave = 1) gets
the share of its Leave Policy annual allocation that the employee has earned by worked days:

    earned = worked days x annual allocation / working days of the Leave Period

Example: EL 20 a year and 300 working days give 1 EL for each 15 worked days. Worked days: Present and
Work From Home 1, Half Day 0.5 (1 if the other half is a paid leave), On Leave with a paid leave type 1.

The credit goes into the Leave Ledger the ERPNext way (erpnext/hr/utils.py, update_previous_leave_allocation),
so Leave Application and the Employee Leave Balance report use it with no change. The ERPNext job
allocate_earned_leaves (annual / 12 each month) is stopped by patches/v13/stop_time_based_earned_leave.py.
"""

import math
from typing import Dict, List

import frappe
from erpnext.hr.utils import create_additional_leave_ledger_entry, get_leave_period
from frappe.utils import add_days, date_diff, flt, formatdate, getdate

ROUNDING_STEP = {"0.25": 0.25, "0.5": 0.5, "1.0": 1.0}


def credit_leaves_from_attendance(date=None):
    """Cron (daily_long). Credits the attendance up to the day before date (default today)"""
    upto = add_days(getdate(date or frappe.flags.current_date or getdate()), -1)
    leave_types = get_earned_leave_types()
    allocations = get_open_allocations(upto, list(leave_types))
    if not allocations:
        return

    worked = get_worked_days(allocations, upto)
    working = get_working_days(allocations)
    annual = get_annual_allocations(allocations)
    credited = get_credited_leaves([row.name for row in allocations])
    for row in allocations:
        ltype = leave_types[row.leave_type]
        earned = get_earned_leaves(worked.get(row.name, 0), annual.get(row.name, 0), working.get(row.name, 0),
            ltype.rounding)
        credit = flt(earned - credited.get(row.name, 0), 2)
        if ltype.max_leaves_allowed and flt(row.total_leaves_allocated) + credit > ltype.max_leaves_allowed:
            credit = flt(ltype.max_leaves_allowed - flt(row.total_leaves_allocated), 2)
        if credit > 0:
            post_credit(row.name, credit, worked.get(row.name, 0), upto)


def get_earned_leaves(worked_days, annual_allocation, working_days, rounding):
    """Leaves earned by worked_days, rounded down to the Leave Type rounding step, at most annual_allocation"""
    if not working_days or not annual_allocation:
        return 0
    earned = min(flt(worked_days) * flt(annual_allocation) / flt(working_days), flt(annual_allocation))
    step = ROUNDING_STEP.get(rounding or "", 0.01)
    return flt(math.floor(round(earned / step, 6)) * step, 2)


def post_credit(allocation_name, credit, worked_days, upto):
    allocation = frappe.get_doc("Leave Allocation", allocation_name)
    # The ledger entry runs from its date to the allocation end, so the last credit is dated on the last day
    ledger_date = min(add_days(upto, 1), getdate(allocation.to_date))
    allocation.db_set("total_leaves_allocated", flt(allocation.total_leaves_allocated) + credit,
        update_modified=False)
    create_additional_leave_ledger_entry(allocation, credit, ledger_date)
    allocation.add_comment(comment_type="Info", text="Credited {0} leave(s) for {1} worked days from {2} to {3}".format(
        frappe.bold(credit), worked_days, formatdate(allocation.from_date), formatdate(upto)))


def get_earned_leave_types() -> Dict[str, frappe._dict]:
    rows = frappe.get_all("Leave Type", filters={"is_earned_leave": 1, "is_lwp": 0},
        fields=["name", "rounding", "max_leaves_allowed"])
    return {row.name: row for row in rows}


def get_open_allocations(upto, leave_types: List[str]) -> List[frappe._dict]:
    """Submitted allocations of the types that cover upto and come from a Leave Policy"""
    if not leave_types:
        return []
    return frappe.get_all("Leave Allocation", filters={"docstatus": 1, "leave_type": ("in", leave_types),
        "from_date": ("<=", upto), "to_date": (">=", upto)},
        or_filters={"leave_policy": ("is", "set"), "leave_policy_assignment": ("is", "set")},
        fields=["name", "employee", "leave_type", "from_date", "to_date", "company", "leave_policy",
            "leave_policy_assignment", "total_leaves_allocated"])


def get_worked_days(allocations, upto) -> Dict[str, float]:
    """{allocation: worked days from its from_date to upto}, in one query"""
    lwp = frappe.get_all("Leave Type", filters={"is_lwp": 1}, pluck="name") or [""]
    rows = frappe.db.sql("""
        SELECT la.name, SUM(CASE
            WHEN att.status IN ('Present', 'Work From Home') THEN 1
            WHEN att.status = 'Half Day' THEN
                IF(IFNULL(att.leave_type, '') != '' AND att.leave_type NOT IN %(lwp)s, 1, 0.5)
            WHEN att.status = 'On Leave' AND IFNULL(att.leave_type, '') != '' AND att.leave_type NOT IN %(lwp)s
                THEN 1
            ELSE 0 END)
        FROM `tabLeave Allocation` la
        JOIN `tabAttendance` att ON att.employee = la.employee AND att.docstatus = 1
            AND att.attendance_date BETWEEN la.from_date AND LEAST(la.to_date, %(upto)s)
        WHERE la.name IN %(names)s
        GROUP BY la.name""", {"lwp": lwp, "upto": upto, "names": [row.name for row in allocations]})
    return {name: flt(days) for name, days in rows}


def get_working_days(allocations) -> Dict[str, int]:
    """{allocation: days of its Leave Period minus the holidays of the employee's holiday list}"""
    periods = {}
    for row in allocations:
        key = (row.from_date, row.to_date, row.company)
        if key not in periods:
            found = get_leave_period(row.from_date, row.to_date, row.company) or []
            period = [p for p in found if p.from_date <= row.to_date and p.to_date >= row.from_date]
            periods[key] = (period[0].from_date, period[0].to_date) if period else (row.from_date, row.to_date)

    lists = get_holiday_lists({row.employee for row in allocations})
    starts = [p[0] for p in periods.values()]
    ends = [p[1] for p in periods.values()]
    holidays = {}
    for parent, holiday_date in frappe.get_all("Holiday", filters={"parent": ("in", list(set(lists.values())) or [""]),
            "holiday_date": ("between", [min(starts), max(ends)])}, fields=["parent", "holiday_date"], as_list=True):
        holidays.setdefault(parent, []).append(getdate(holiday_date))

    working = {}
    for row in allocations:
        start, end = periods[(row.from_date, row.to_date, row.company)]
        off = sum(1 for day in holidays.get(lists.get(row.employee), []) if getdate(start) <= day <= getdate(end))
        working[row.name] = date_diff(end, start) + 1 - off
    return working


def get_holiday_lists(employees) -> Dict[str, str]:
    """{employee: holiday list}, the company default list when the employee has none (as get_holiday_list_for_employee)"""
    rows = frappe.get_all("Employee", filters={"name": ("in", list(employees))}, fields=["name", "holiday_list", "company"])
    defaults = {company: frappe.get_cached_value("Company", company, "default_holiday_list")
        for company in {row.company for row in rows}}
    return {row.name: row.holiday_list or defaults.get(row.company) for row in rows}


def get_annual_allocations(allocations) -> Dict[str, float]:
    """{allocation: annual allocation of its leave type in its Leave Policy}"""
    lpa_policy = dict(frappe.get_all("Leave Policy Assignment", filters={"name": ("in",
        [row.leave_policy_assignment for row in allocations if row.leave_policy_assignment] or [""])},
        fields=["name", "leave_policy"], as_list=True))
    policies = {row.name: row.leave_policy or lpa_policy.get(row.leave_policy_assignment) for row in allocations}
    details = frappe.get_all("Leave Policy Detail", filters={"parent": ("in", list(set(policies.values())) or [""])},
        fields=["parent", "leave_type", "annual_allocation"])
    annual = {(row.parent, row.leave_type): flt(row.annual_allocation) for row in details}
    return {row.name: annual.get((policies[row.name], row.leave_type), 0) for row in allocations}


def get_credited_leaves(names) -> Dict[str, float]:
    """{allocation: leaves credited without carry forward}. Grouped form of LeaveAllocation.get_existing_leave_count"""
    rows = frappe.get_all("Leave Ledger Entry", filters={"transaction_type": "Leave Allocation",
        "transaction_name": ("in", names), "is_carry_forward": 0, "docstatus": 1},
        fields=["transaction_name", "sum(leaves) as leaves"], group_by="transaction_name")
    return {row.transaction_name: flt(row.leaves) for row in rows}


def zero_time_based_credit(doc, method=None):
    """
    Leave Allocation before_validate. A Leave Policy Assignment pre-credits an earned leave type by the months
    passed (annual / 12 each). Here the credit comes from attendance, so it starts at 0 and the daily job
    credits the attendance since from_date.
    """
    if doc.is_new() and doc.leave_policy_assignment and frappe.get_cached_value("Leave Type", doc.leave_type,
            "is_earned_leave"):
        doc.new_leaves_allocated = 0
