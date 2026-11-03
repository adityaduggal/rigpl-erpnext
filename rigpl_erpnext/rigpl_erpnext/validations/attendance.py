# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import division
import frappe
from frappe.query_builder import Order
from frappe.utils import getdate, add_days, get_datetime, time_diff_in_seconds
from datetime import datetime, timedelta

from rigpl_erpnext.hr_rigpl.utils.hr_utils import get_half_day_fraction


def on_update(doc, method):
    # ERPNext makes the leave attendance with ignore_validate; do not check it again here
    if doc.flags.ignore_validate:
        return
    validate(doc, method)


def validate(doc, method):
    attendance_date = getdate(doc.attendance_date)
    if doc.status not in ("Present", "Half Day", "On Leave"):
        frappe.throw("Only Present or Half Day or On Leave Attendance is Allowed Check {0}".format(doc.name))
    doc.department = frappe.get_value("Employee", doc.employee, "department")
    check_employee(doc, attendance_date)
    shft = get_shift(doc, attendance_date)
    if doc.status != "On Leave" and shft.in_out_required:
        calculate_overtime(doc, shft, attendance_date)


def check_employee(doc, attendance_date):
    """Attendance only between the joining date and the relieving date"""
    emp = frappe.db.get_value("Employee", doc.employee, ["status", "employee_name", "relieving_date",
        "date_of_joining"], as_dict=1)
    if emp.status == "Left":
        if emp.relieving_date < attendance_date:
            frappe.throw("Cannot create attendance for {0} as he/she has left on {1}".
                         format(emp.employee_name, emp.relieving_date))
    else:
        if emp.date_of_joining > attendance_date:
            frappe.throw("Cannot create attendance for {0} as he/she has joined on {1}".
                         format(emp.employee_name, emp.date_of_joining))


def get_shift(doc, attendance_date):
    """Sets the shift from the Shift Assignment. On a holiday with no assignment, the day before is used."""
    shift_type = get_assigned_shift(doc.employee, attendance_date)
    if not shift_type:
        if is_holiday(doc.employee, attendance_date):
            shift_type = get_assigned_shift(doc.employee, add_days(attendance_date, -1))
            if not shift_type:
                frappe.throw("No Shift Assignment defined for {0} for date {1} which is a Holiday and its "
                             "Previous Day".format(doc.employee, doc.attendance_date))
        else:
            frappe.throw("No Shift Assignment defined for {0} for date {1}".format(doc.employee,
                doc.attendance_date))
    doc.shift = shift_type
    return frappe.get_doc("Shift Type", shift_type)


def get_assigned_shift(employee, for_date):
    """Shift Type of the submitted, active Shift Assignment whose date range has `for_date`"""
    sa = frappe.qb.DocType("Shift Assignment")
    rows = (
        frappe.qb.from_(sa)
        .select(sa.shift_type)
        .where((sa.employee == employee) & (sa.docstatus == 1) & (sa.status == "Active")
            & (sa.start_date <= for_date) & ((sa.end_date >= for_date) | sa.end_date.isnull()))
        .orderby(sa.start_date, order=Order.desc)
        .limit(1)
    ).run()
    return rows[0][0] if rows else None


def is_holiday(employee, for_date):
    holiday_list = frappe.get_value("Employee", employee, "holiday_list")
    return bool(holiday_list and frappe.db.exists("Holiday", {"parent": holiday_list, "holiday_date": for_date}))


def calculate_overtime(doc, shft, attendance_date):
    doc.overtime = 0
    if doc.status == "Half Day" and doc.leave_application and not doc.get("attendance_time"):
        # Made by a half-day Leave Application; the punches can be added later
        return

    rules = validate_time_with_shift(doc, shft, attendance_date)
    pu_data = check_punch_data(doc, rules.margin)

    tt_in = 0
    for i in range(len(pu_data) - 1):
        if pu_data[i][1] == 'In Time':
            tt_in += time_diff_in_seconds(pu_data[i + 1][2], pu_data[i][2])

    shft_hrs = rules.hours
    if doc.status == "Half Day":
        shft_hrs = shft_hrs * get_half_day_fraction()
    doc.overtime = ((tt_in - shft_hrs + rules.margin) - ((tt_in + rules.margin - shft_hrs) % rules.rounding)) / 3600


def validate_time_with_shift(doc, shft, attendance_date):
    """Checks the first punch against the shift entry window. Returns the shift hours, rounding and margin."""
    if not doc.get("attendance_time"):
        frappe.throw("For Shift " + shft.name + " In and Out Punch are required")

    rules = frappe._dict(hours=shft.hours_required_per_day.seconds, rounding=shft.time_rounding.seconds,
        margin=shft.time_margin.seconds)
    if rules.rounding <= 0 or rules.margin <= 0:
        frappe.throw("Shift Rounding or Shift Margin cannot be Zero")

    if shft.start_time > shft.end_time and shft.next_day != 1:
        # Night shift that starts on the day before
        shft_indate = datetime.combine(add_days(attendance_date, -1), datetime.min.time())
    else:
        shft_indate = datetime.combine(attendance_date, datetime.min.time())

    shft_intime = shft_indate + timedelta(0, shft.start_time.seconds)
    shft_intime_max = shft_intime + timedelta(0, shft.delayed_entry_allowed_time.seconds)
    shft_intime_min = shft_intime - timedelta(0, shft.early_entry_allowed_time.seconds)

    for d in doc.get("attendance_time"):
        if d.idx == 1:
            d.date_time = get_datetime(d.date_time)
            if not shft_intime_min <= d.date_time <= shft_intime_max:
                frappe.throw("Time {0} in row#1 is not allowed for Shift# {1} for {2}.Check early and "
                             "delayed entry settings in Shift Master".format(d.date_time, doc.shift, doc.name))
    return rules


def check_punch_data(doc, shft_marg):
    pu_data = []

    for d in doc.get("attendance_time"):
        if d.idx == 1 and d.time_type != 'In Time':
            frappe.throw("First Punch Data should be In Time for {0}".format(doc.name))
        pu_data.append([d.idx, d.time_type, d.date_time])

    for i in range(len(pu_data) - 1):
        # Checks if In and Out are alternating
        if pu_data[i][1] == pu_data[i + 1][1]:
            frappe.throw("{1} should not be Followed by {1} for {2} check row # {3} & {4}".
                         format(pu_data[i][1], pu_data[i][1], doc.name, pu_data[i][0], pu_data[i + 1][0]))
        # Checks if Time Data is following the minimum time difference rule in shift
        if time_diff_in_seconds(pu_data[i + 1][2], pu_data[i][2]) <= shft_marg:
            frappe.throw("Difference between 2 punch data cannot be less than {0} mins check row# {1} and {2} for {3}".
                         format(shft_marg / 60, pu_data[i][0], pu_data[i + 1][0], doc.name))

    return pu_data
