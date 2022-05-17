# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt
from __future__ import division
from __future__ import unicode_literals
import frappe
from frappe.utils import getdate, flt
from math import ceil


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
    Gets entries for the set filters
    """
    data = []
    conditions_emp = get_conditions(filters)[0]

    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    total_days = (getdate(filters.get("to_date")) - getdate(filters.get("from_date"))).days + 1

    query = f"""SELECT emp.name, emp.employee_name, emp.date_of_joining,
        IFNULL(emp.relieving_date,'2099-12-31') as relieving_date, emp.branch, emp.department,
        emp.designation, (DATEDIFF('{to_date}', '{from_date}')+1) as t_days,

        (SELECT count(hol.name) FROM `tabHoliday` hol , `tabHoliday List` hdl
            WHERE hdl.base_holiday_list = emp.holiday_list AND hol.parent = hdl.name
            AND hdl.is_base_list = 0 AND hol.holiday_date <= '{to_date}'
            AND hol.holiday_date >= '{from_date}') as holidays,

        (SELECT count(name) FROM `tabAttendance`
            WHERE employee = emp.name AND docstatus = 1 AND status = 'Present'
            AND attendance_date <= '{to_date}' AND attendance_date >= '{from_date}') as presents,

        (SELECT sum(overtime) FROM `tabAttendance`
            WHERE employee = emp.name AND docstatus = 1 AND attendance_date <= '{to_date}'
            AND attendance_date >= '{from_date}') as overtime,

        (SELECT SUM(total_leave_days) FROM `tabLeave Application`
            WHERE employee = emp.name AND docstatus = 1 AND status = 'Approved'
            AND to_date <= '{to_date}' AND from_date >= '{from_date}') as auth_leaves
        FROM
            `tabEmployee` emp
        WHERE
            IFNULL(emp.relieving_date,'2099-12-31') >= '{from_date}' {conditions_emp}"""

    data_dict = {}
    data_dict = frappe.db.sql(query, as_dict=1)
    row = []
    for row in data_dict:
        # frappe.throw(str(row))
        base_hols = row.holidays
        if row.date_of_joining > from_date:
            act_tot_days = (to_date - row.date_of_joining).days + 1
        elif getdate(row.relieving_date) < to_date:
            act_tot_days = (getdate(row.relieving_date) - from_date).days + 1
        else:
            act_tot_days = total_days
        # No of Holidays is pro-rata based on no of Total Working Days of an Employee
        if act_tot_days != total_days:
            holidays = int(base_hols / total_days * act_tot_days)
        else:
            holidays = base_hols

        base_wd = act_tot_days - holidays
        cal_hols = ceil(holidays * flt(row.presents) / base_wd)
        # No of Holidays also depends on the No of Presents of an Employee
        ual = act_tot_days - cal_hols - flt(row.presents) - flt(row.auth_leaves)
        if ual < 0:
            ual = 0
            cal_hols = act_tot_days - flt(row.presents) - flt(row.auth_leaves)

        absents = act_tot_days - flt(row.presents) - holidays
        working_days = act_tot_days - holidays

        working_days = max(working_days, 1)
        att_per = (row.presents / working_days) * 100
        adj_att_per = ((row.presents - ual) / working_days) * 100

        row = [row.name, row.employee_name, act_tot_days, holidays, row.presents, row.overtime,
        flt(row.auth_leaves), ual, att_per, adj_att_per, absents, row.date_of_joining,
            row.relieving_date, row.branch, row.department, row.designation]
        data.append(row)

    return data


def get_conditions(filters):
    """
    Gets conditions as per the filters
    """
    conditions_emp = ""
    conditions_att = ""

    if filters.get("branch"):
        conditions_emp += " AND emp.branch = '%s'" % filters["branch"]

    if filters.get("department"):
        conditions_emp += " AND emp.department = '%s'" % filters["department"]

    if filters.get("employee"):
        conditions_emp += " AND emp.name = '%s'" % filters["employee"]

    if filters.get("from_date"):
        if filters.get("to_date"):
            if filters.get("from_date") >= filters.get("to_date"):
                frappe.throw("From Date Cannot be Greater than or Equal to To Date")
            else:
                conditions_att += " AND att.attendance_date >='%s'" % filters["from_date"]

    if filters.get("to_date"):
        if filters.get("from_date"):
            if filters.get("from_date") >= filters.get("to_date"):
                frappe.throw("From Date Cannot be Greater than or Equal to To Date")
            else:
                conditions_att += " AND att.attendance_date <='%s'" % filters["to_date"]

    return conditions_emp, conditions_att
