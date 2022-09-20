#  Copyright (c) 2022. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
# -*- coding: utf-8 -*-

from datetime import date

import frappe
from erpnext.hr.doctype.leave_allocation.leave_allocation import (
    get_carry_forwarded_leaves,
)
from frappe.utils import flt, formatdate

from .hr_utils import get_attendance_details


def is_leave_applicable_as_per_policy(ltyp, emp_nm):
    """
    Returns boolean if leave policy applicable for a leave type name string and
    employee name string
    """
    applicable = 0
    lvs_to_allocate = 0
    lpold = get_app_leave_policy(emp_nm)
    if lpold:
        for leaves in lpold.leave_policy_details:
            if leaves.leave_type == ltyp:
                applicable = 1
                lvs_to_allocate = leaves.annual_allocation
    return applicable, lvs_to_allocate


def get_app_leave_policy(emp_name):
    """
    Returns a Leave Policy Doc for an Employee Name
    """
    emp_doc = frappe.get_doc("Employee", emp_name)
    emp_desk = frappe.get_desk_link("Employee", emp_name)
    if not emp_doc.grade:
        frappe.throw(
            f"{emp_desk} is Not Linked to an Employee Grade. <br>First Link it to an\
         Employee Grade before allocating it any Leaves"
        )
    else:
        grd_doc = frappe.get_doc("Employee Grade", emp_doc.grade)
        grd_desk = frappe.get_desk_link("Employee Grade", emp_doc.grade)
        if not grd_doc.default_leave_policy:
            frappe.throw(f"{grd_desk} does not have a Default Leave Policy defined")
        else:
            lpd = frappe.get_doc("Leave Policy", grd_doc.default_leave_policy)
            lp_desk = frappe.get_desk_link("Leave Policy", lpd.name)
            if lpd.docstatus != 1:
                frappe.throw(
                    f"{lp_desk} linked to {grd_desk} which in turn is linked to \
                    {emp_desk} is not Submitted"
                )
    return lpd


def get_new_leaves_for_ltyp_in_period(emp, ltyp, lpd):
    """
    Returns the new leave for an emp name string and ltype string for leave type and
    lpd is the leave period dictionary with lpd.name, lpd.from_date, lpd.to_date defined
    """
    new_leaves, calc2dt, used_atts = 0, 0, []
    already_allocated = get_leave_allocation_for_period(
        emp=emp, ltyp=ltyp, frm_dt=lpd.from_date, to_dt=lpd.to_date
    )
    cfd_lvs = get_carry_forwarded_leaves(
        employee=emp, leave_type=ltyp, date=lpd.from_date
    )
    ltd = frappe.get_doc("Leave Type", ltyp)
    lvs_to_allocate = is_leave_applicable_as_per_policy(ltyp, emp)[1]
    lt_dsk = frappe.get_desk_link(ltd.doctype, ltd.name)
    emp_dsk = frappe.get_desk_link("Employee", emp)
    ft_frm_dt = formatdate(lpd.from_date)
    ft_to_dt = formatdate(lpd.to_date)
    if ltd.is_lwp != 1:
        if ltd.is_earned_leave != 1:
            # Below condition is being used since Casual Leaves and Sick Leaves are
            # Generally credited in one shot only.
            att_smm = get_attendance_details(
                emp_name=emp, frm_date=lpd.from_date, to_date=lpd.to_date
            )
            if already_allocated == 0:
                if ltd.applicable_after <= att_smm.tot_pres:
                    balance_days = ltd.applicable_after
                    # We can allocate leaves if not already allocated.
                    for att in att_smm.attendances:
                        if att.status == "Present":
                            used_atts.append(att.name)
                            balance_days -= 1
                            if balance_days == 0:
                                calc2dt = att.attendance_date
                                new_leaves = lvs_to_allocate
                                break
                else:
                    frappe.throw(
                        f"""For {lt_dsk} minimum Attendance Needed for Credit of 
                        Leaves is {ltd.applicable_after} but {emp_dsk} only has {
                            att_smm.tot_pres} no of Presents in the Period {ft_frm_dt} to {ft_to_dt}"""
                    )
        else:
            # Case of Earned leaves here the already allocated leaves cannot be equal to the
            # total leaves to be credited in a year once they are equal the period is taken care of
            # Also need to check if the Earned leaves are applicable or not till date as the no of
            # Days in Earned Leaves are counted from the Date of Joining
            appl_date = get_earned_lvs_applicable_dt(emp=emp, ltype=ltyp)
            if appl_date:
                if appl_date > lpd.from_date and appl_date < lpd.to_date:
                    att_smm = get_earned_att_details(emp_name=emp, frm_date=appl_date, 
                                                     to_date=lpd.to_date, no_of_days= ltd.)

    return new_leaves, calc2dt, used_atts

def get_earned_lvs_applicable_dt(emp, ltype):
    """
    Returns the date from which the earned leave is going to be applied after that no of attendances at present
    would apply everytime attendance is submitted
    """
    appl_date = ""
    empd = frappe.get_doc("Employee", emp)
    ltd = frappe.get_doc("Leave Type", ltype)
    emp_dsk = frappe.get_desk_link(empd.doctype, empd.name)
    ltd_dsk = frappe.get_desk_link(ltd.doctype, ltd.name)
    attr = frappe.db.sql(
        f"""SELECT name, attendance_date, status FROM `tabAttendance` 
        WHERE docstatus=1 AND employee = '{emp}' AND status = 'Present' 
        ORDER BY attendance_date ASC LIMIT {ltd.applicable_after}""",
        as_dict=1,
    )
    if len(attr) == ltd.applicable_after:
        appl_date = attr[ltd.applicable_after - 1].attendance_date
    else:
        frappe.throw(
            f"""{emp_dsk} cannot get {ltd_dsk} as Total Working Days needed for Credit of Such 
                     Leaves is {ltd.applicable_after} whereas Total Presents till date are only
                     {len(attr)}"""
        )
    return appl_date


def get_leave_allocation_for_period(emp, ltyp, frm_dt, to_dt):
    """
    Returns integer for the already allocated leaves for the period
    """
    query = f"""SELECT SUM(total_leaves_allocated) as leaves_allocated FROM `tabLeave Allocation` 
    WHERE docstatus = 1 AND leave_type = '{ltyp}' AND employee = '{emp}' 
    AND (from_date BETWEEN '{frm_dt}' AND '{to_dt}') AND to_date <= '{to_dt}'"""
    allocated_lvs = flt(frappe.db.sql(query, as_dict=1)[0].leaves_allocated)
    return allocated_lvs


def get_app_leave_period_for_emp(emp):
    """
    Returns dictionary of leave period applicable for an employee based on its joining date and relieving date
    If employee is Gone then check if the Reliveing date should be between from and to date to be included
    If employee is new then joining date should be between the from and to date also change the dates
    accordingly
    """
    join_dt = frappe.get_value("Employee", emp, "date_of_joining")
    rel_dt = frappe.get_value("Employee", emp, "relieving_date")
    active_lp = frappe.db.sql(
        f"""SELECT name, from_date, to_date FROM `tabLeave Period`
                              WHERE is_active = 1 ORDER BY from_date""",
        as_dict=1,
    )
    app_lp = []
    for lpd in active_lp:
        if rel_dt:
            if lpd.from_date < rel_dt < lpd.to_date:
                lpd["to_date"] = rel_dt
                app_lp.append(lpd)
                continue
        else:
            if lpd.from_date <= date.today() < lpd.to_date:
                lpd["to_date"] = date.today()
                app_lp.append(lpd)
                continue

        if lpd.from_date <= join_dt <= lpd.to_date:
            lpd["from_date"] = join_dt
            app_lp.append(lpd)
            continue
        elif join_dt <= lpd.from_date and lpd.from_date <= date.today():
            app_lp.append(lpd)
            continue
    return app_lp
