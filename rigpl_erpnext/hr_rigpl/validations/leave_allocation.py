#  Copyright (c) 2022. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
# -*- coding: utf-8 -*-


import frappe
from erpnext.hr.doctype.leave_allocation.leave_allocation import get_unused_leaves
from erpnext.hr.utils import get_leave_period
from frappe.utils import formatdate

from ...hr_rigpl.utils.leave_utils import (
    get_app_leave_period_for_emp,
    get_new_leaves_for_ltyp_in_period,
    is_leave_applicable_as_per_policy,
)
from ..utils.hr_utils import get_attendance_details

"""
Leave Allocation is done the following ways without Leave Policy Assignment
1. Check applicable leave policy for Employee
2. Automatically fill the start date for that leave if policy applicable (Based on Rules in Leave Type)
3. Automatically fill the end date for that leave if policy applicable (Based on Rules in Leave Type)
4. 

"""


def validate(doc, method):
    """
    Adding Validations which are missing in ERPNext to Leave Allocation
    1. Applicable after working days would check presents in that leave period.
    2.
    """
    lv_pol_app = is_leave_applicable_as_per_policy(doc.leave_type, doc.employee)[0]
    empd = frappe.get_doc("Employee", doc.employee)
    ltd = frappe.get_doc("Leave Type", doc.leave_type)
    lv_dsk = frappe.get_desk_link(ltd.doctype, ltd.name)
    lal_dsk = frappe.get_desk_link(doc.doctype, doc.name)
    emp_dsk = frappe.get_desk_link(empd.doctype, empd.name)
    if lv_pol_app == 1:
        lpdict = get_app_leave_period_for_emp(empd.name)
        for lpd in lpdict:
            new_lvs, upto_date, atts_used = get_new_leaves_for_ltyp_in_period(
                emp=empd.name, ltyp=ltd.name, lpd=lpd
            )
            if new_lvs > 0:
                doc.from_date = lpd.from_date
                doc.to_date = upto_date
                doc.new_leaves_allocated = new_lvs
                doc.carry_forward = ltd.is_carry_forward
                if not doc.linked_attendances:
                    att_dt = {}
                    for att in atts_used:
                        att_dt["valid_attendance"] = att
                        doc.append("linked_attendances", att_dt.copy())
                break
    else:
        frappe.throw(
            f"{lv_dsk} is not defined in any policy for {emp_dsk} in {lal_dsk}"
        )


def get_one_leave_period_for_leave_allocation(lald):
    """
    lald = Leave Allocation Document
    Returns single leave period for a Leave Allocation
    If more than one or NO leave period then returns an error
    """
    lpd = get_leave_period(lald.from_date, lald.to_date, lald.company)
    ft_frm_dt = frappe.format(lald.from_date, dict(fieldtype="Date"))
    ft_to_dt = frappe.format(lald.to_date, dict(fieldtype="Date"))
    dt_link = frappe.get_desk_link(lald.doctype, lald.name)
    act_lpd = frappe.get_list(
        "Leave Period",
        fields=["name", "from_date", "to_date"],
        filters={"is_active": 1},
        order_by="from_date",
    )
    act_lpd_txt = ""
    for lprd in act_lpd:
        lplnk = frappe.get_desk_link("Leave Period", lprd.name)
        lp_fmt_frm_dt = frappe.format(lprd.from_date, dict(fieldtype="Date"))
        lp_fmt_to_dt = frappe.format(lprd.to_date, dict(fieldtype="Date"))
        act_lpd_txt += f"<br>{act_lpd.index(lprd) + 1}. {lplnk} From: {lp_fmt_frm_dt} To: {lp_fmt_to_dt}"
    if len(lpd) == 1:
        return lpd[0].name
    else:
        frappe.throw(
            f"""There are {len(lpd)} number of Active Leave Periods for 
            {ft_frm_dt} and {ft_to_dt}.<br>Kindly select Proper From and 
            To Dates in {dt_link} so that they are within One Leave Period<br>
            Currently active Leave Periods are {act_lpd_txt}"""
        )


def check_leave_after_days_rule(ltype, emp, frm_dt, to_dt=None):
    """
    ltype = String Leave Type Name, emp = String Employee Name, frm_dt=From Date, to_dt=Only needed if Leave
    type is not Earned then system checks in every Period
    If Leave Type is Earned then Check if the Employee has completed the Total Presents
    before allocation or upto From Date
    """
    dsk_lt = frappe.get_desk_link("Leave Type", ltype)
    ltd = frappe.get_doc("Leave Type", ltype)
    if ltd.is_earned_leave == 1:
        empd = frappe.get_doc("Employee", emp)
        dsk_emp = frappe.get_desk_link("Employee", emp)
        att_dict = get_attendance_details(emp_name=emp, frm_date=frm_dt, to_date=to_dt)

        frappe.throw(f"EL ATT = {att_dict}")
    else:
        if not to_dt:
            frappe.throw(f"Since {dsk_lt} is Not Earned Leave To Date is Mandatory")
        else:
            att_dict = get_attendance_details(
                emp_name=emp, frm_date=frm_dt, to_date=to_dt
            )
            frappe.throw(f"{att_dict}")


def validate_leave_period(rng_frm_dt, rng_to_dt):
    """
    Following Validations on Leave Period
    1. From Date and To Date should be within a valid Leave Period
    2. Range should not be in multiple Leave Periods.
    """
    frappe.msgprint("TODO Leave Period Overlap Check")
    ft_frm_dt = frappe.format(rng_frm_dt, dict(fieldtype="Date"))
    ft_to_dt = frappe.format(rng_to_dt, dict(fieldtype="Date"))


def get_allocated_leaves(leave_type, frm_date, to_date):
    """
    Gets the already allocated leaves for a Leave Type in a Period
    Also would return if carried forward from previous period
    """
    frappe.msgprint("Hello")
