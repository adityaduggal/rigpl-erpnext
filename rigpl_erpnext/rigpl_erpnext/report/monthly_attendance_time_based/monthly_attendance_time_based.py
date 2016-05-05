# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, getdate
from frappe import msgprint, _
from calendar import monthrange
from datetime import datetime

def execute(filters=None):
	if not filters: filters = {}

	conditions, filters = get_conditions(filters)
	columns = get_columns(filters)
	att_map, time_map, ot_map, attendance_list = get_attendance_list(conditions, filters)
	emp_map = get_employee_details()
	

	data = []
	for emp in sorted(att_map):
		nos = sum(1 for i in attendance_list if i['day_of_month']==1)
	
	for emp in sorted(att_map):
		emp_det = emp_map.get(emp)
		if not emp_det:
			continue
		row0 = [emp, emp_det.employee_name, "In Time"]
		row2 = [emp, emp_det.employee_name, "Out Time"]
		row3 = [emp, emp_det.employee_name, "Over Time"]
		
		rows = {}
		for i in range(nos+1):
			if i <> nos:
				if is_odd(i):
					rows["row{0}".format(i)] = row2[:]
				else:
					rows["row{0}".format(i)] = row0[:]
			else:
				rows["row{0}".format(i)] = row3[:]

		for day in range(filters["total_days_in_month"]):
			for np in range(nos+1):
				row_no = "row" + `np`
				tt = rows[row_no][2]
				if np < nos:
					if time_map.get(emp).get(day+1,"None") <> "None":
						if time_map.get(emp).get(day+1, "None").get(np + 1, "None") <> "None":
							timing = time_map.get(emp).get(day + 1, "None").get(np + 1, "None")		
							timing_hrs = timing[tt].time().isoformat()
							timing_hrs = timing[tt].strftime("%H:%M")
							rows[row_no].append(timing_hrs)
						else:
							rows[row_no].append("")
					else:
						rows[row_no].append("")
				else:
					if ot_map.get(emp).get(day+1, "None") <> "None":
						ot = ot_map.get(emp).get(day+1, "")
						rows[row_no].append(ot)
					else:
						rows[row_no].append("")
		for d in rows:
			data.append(rows[d])

	return columns, data

def get_columns(filters):
	columns = [
		_("Employee") + ":Link/Employee:120", _("Employee Name") + "::140", _("Time Type") + "::80"
	]

	for day in range(filters["total_days_in_month"]):
		columns.append(cstr(day+1) +"::60")
		
	return columns

def get_attendance_list(conditions, filters):
	attendance_list = frappe.db.sql("""select at.employee, day(at.att_date) as day_of_month,
		at.status, att.time_type, att.date_time, att.idx, at.overtime
		FROM tabAttendance at, `tabAttendance Time Table` att
		WHERE at.docstatus = 1 AND att.parent = at.name %s 
		ORDER BY at.employee, at.att_date""" %
		conditions, filters, as_dict=1)
	att_map = {}
	time_map = {}
	ot_map = {}
	
	for d in attendance_list:
		att_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
		att_map[d.employee][d.day_of_month] = d.status
		
		time_map.setdefault(d.employee, frappe._dict()).\
			setdefault(d.day_of_month, frappe._dict()).\
			setdefault(d.idx, frappe._dict()).setdefault(d.time_type, "")
		time_map[d.employee][d.day_of_month][d.idx][d.time_type] = d.date_time
		
		ot_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
		ot_map[d.employee][d.day_of_month] = d.overtime
	
	#frappe.msgprint(time_map)
	return att_map, time_map, ot_map, attendance_list

def get_conditions(filters):
	if not (filters.get("month") and filters.get("year")):
		msgprint(_("Please select month and year"), raise_exception=1)

	filters["month"] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
		"Dec"].index(filters.month) + 1

	filters["total_days_in_month"] = monthrange(cint(filters.year), filters.month)[1]

	conditions = " and month(at.att_date) = %(month)s and year(at.att_date) = %(year)s"

	if filters.get("company"): conditions += " and company = %(company)s"
	if filters.get("employee"): conditions += " and at.employee = %(employee)s"

	return conditions, filters

def get_employee_details():
	emp_map = frappe._dict()
	for d in frappe.db.sql("""select name, employee_name, designation,
		department, branch, company
		from tabEmployee""", as_dict=1):
		emp_map.setdefault(d.name, d)

	return emp_map

@frappe.whitelist()
def get_attendance_years():
	year_list = frappe.db.sql_list("""select distinct YEAR(at.att_date) from tabAttendance at 
		ORDER BY YEAR(at.att_date) DESC""")
	if not year_list:
		year_list = [getdate().year]

	return "\n".join(str(year) for year in year_list)
	
def is_odd(a):
	return bool(a - ((a>>1)<<1))