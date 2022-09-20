#  Copyright (c) 2022. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
# -*- coding: utf-8 -*-
import frappe
from frappe.utils import getdate


def get_attendance_details(emp_name, frm_date, to_date):
    """
    Returns the attendance details dictionary for employee for given dates
    emp_name = Name of the Employee (Employee ID)
    frm_date = From Date in txt or datetime
    to_date = To Date in txt or datetime
    dictionary has the following keys:
    tot_days = Total Days integer, tot_wday = Total Working Days integer,
    tot_hols = Total Holidays integer, tot_pres = Total Presents int,
    tot_abs = Total Absents int
    """
    att_det_dict = frappe._dict({})
    att_list = frappe.db.sql(
        f"""SELECT att.name, att.attendance_date, att.status, att.leave_type FROM `tabAttendance` att
                             WHERE att.docstatus = 1 AND att.attendance_date >= '{frm_date}' 
                             AND att.attendance_date <= '{to_date}' AND att.employee = '{emp_name}'
                             ORDER BY att.attendance_date ASC""",
        as_dict=1,
    )
    tot_dys, holidys = get_employee_holidays(
        emp_name=emp_name, frm_date=frm_date, to_date=to_date
    )
    present, absent = 0, 0
    for att in att_list:
        if att.status == "Present":
            present += 1
        elif att.status == "Half Day":
            present += 0.5
            absent += 0.5
        else:
            absent += 1
    att_det_dict["tot_days"] = tot_dys
    att_det_dict["tot_hols"] = holidys
    att_det_dict["tot_abs"] = tot_dys - holidys - present
    att_det_dict["tot_pres"] = present
    att_det_dict["tot_wday"] = tot_dys - holidys
    att_det_dict["attendances"] = att_list

    return att_det_dict


def get_employee_holidays(emp_name, frm_date, to_date):
    """
    Returns the holidays and working dates for employee in given date
    Emp_name = Employee Name
    From Date and To Date are Datetime objects
    """
    bs_hd_list = frappe.get_value("Employee", emp_name, "holiday_list")
    tot_days = (getdate(to_date) - getdate(frm_date)).days + 1
    hols = frappe.db.sql(
        f"""SELECT hol.parent, hol.holiday_date, hol.description, hol.weekly_off
                         FROM `tabHoliday` hol, `tabHoliday List` hl WHERE hl.is_base_list=0 
                         AND hol.parent = hl.name AND hol.parenttype = 'Holiday List'
                         AND hl.base_holiday_list = '{bs_hd_list}' AND hol.holiday_date >= '{frm_date}'
                         AND hol.holiday_date <= '{to_date}'""",
        as_list=1,
    )
    holidays = len(hols)
    return tot_days, holidays
