# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, getdate
from frappe import msgprint, _
from calendar import monthrange

def execute(filters=None):
	if not filters: filters = {}

	conditions, filters, conditions_hol, conditions_la, conditions_emp = get_conditions(filters)
	columns = get_columns(filters)
	att_map = get_attendance_list(conditions, filters)
	emp_map = get_employee_details(conditions_emp)
	hol_map = get_holiday_list(conditions_hol)
	la_map = get_leave_application(conditions_la, filters)

	data = []
	for emp in sorted(att_map):
		emp_det = emp_map.get(emp)
		if not emp_det:
			continue

		row = [emp, emp_det.employee_name]

		total_p = total_a = 0.0
		for day in range(filters["total_days_in_month"]):
			status = att_map.get(emp).get(day + 1, "None")
			status_map = {"Present": "P", "Absent": "A", "Half Day": "H", 
				"None": "", "Holiday": "HO", "Unauthorized Leave": "X", "Authorized Leave": "L"}
			if hol_map.get(emp):
				hol = hol_map.get(emp).get(day + 1, "None")
			else:
				hol = "None"
			
			if la_map.get(emp):
				la = la_map.get(emp).get(day + 1, "None")
			else:
				la = "None"
			
			if status == "None":
				#Check if its in HOLIDAY
				if hol == "None":
					#Now since the day is not in Holidays now check if its in LEAVE APP
					if la == "None":
						row.append(status_map["Unauthorized Leave"])
					else:
						row.append(status_map["Authorized Leave"])
				else:
					row.append(status_map["Holiday"])
			else:
				row.append(status_map[status])

			if status == "Present":
				total_p += 1
			elif status == "Absent":
				total_a += 1
			elif status == "Half Day":
				total_p += 0.5
				total_a += 0.5

		row += [total_p, total_a]
		data.append(row)

	return columns, data

def get_columns(filters):
	columns = [
		_("Employee") + ":Link/Employee:120", _("Employee Name") + "::140"
	]

	for day in range(filters["total_days_in_month"]):
		columns.append(cstr(day+1) +"::20")

	columns += [_("Total Present") + "::80", _("Total Absent") + "::80"]
	return columns

def get_attendance_list(conditions, filters):
	attendance_list = frappe.db.sql("""select at.employee, day(at.attendance_date) as day_of_month,
		at.status
		FROM tabAttendance at
		WHERE at.docstatus = 1 %s 
		ORDER BY at.employee, at.attendance_date""" %
		conditions, filters, as_dict=1)

	att_map = {}
	
	for d in attendance_list:
		att_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
		att_map[d.employee][d.day_of_month] = d.status		
	return att_map

def get_holiday_list(conditions_hol):
	hol_map = frappe._dict()
	query = """SELECT emp.name as employee , day(ho.holiday_date)  as day_of_month, ho.description
		FROM `tabEmployee` emp, `tabHoliday List` hol, `tabHoliday` ho
		WHERE emp.holiday_list = hol.name AND ho.parent = hol.name %s""" %(conditions_hol)
	holidays = frappe.db.sql(query, as_dict=1)
	for d in holidays:
		hol_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
		hol_map[d.employee][d.day_of_month] = d.description

	return hol_map

def get_conditions(filters):
	
	conditions_la = ""
	conditions_hol = ""
	conditions_emp = ""
	
	if not (filters.get("month") and filters.get("year")):
		msgprint(_("Please select month and year"), raise_exception=1)

	filters["month"] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
		"Dec"].index(filters.month) + 1

	filters["total_days_in_month"] = monthrange(cint(filters.year), filters.month)[1]
	
	from_date = str(filters["year"]) + "-" + str(filters["month"]) + "-" + str(1)
	to_date = str(filters["year"]) + "-" + str(filters["month"]) + "-" + str(filters["total_days_in_month"])

	conditions = " and month(at.attendance_date) = %(month)s and year(at.attendance_date) = %(year)s"
	
	conditions_hol = "AND ho.holiday_date >= '%s' AND ho.holiday_date <= '%s'" %(from_date, to_date)
	
	if filters.get("employee"):
		conditions += " and at.employee = %(employee)s"
		conditions_hol += " AND emp.name = '%s'" %filters["employee"]
		conditions_la += " AND emp.name = '%s'" %filters["employee"]
		conditions_emp += " AND emp.name = '%s'" %filters["employee"]
	
	if filters.get("branch"):
		conditions_hol += " AND emp.branch = '%s'" %filters["branch"]
		conditions_la += " AND emp.branch = '%s'" %filters["branch"]
		conditions_emp += " AND emp.branch = '%s'" %filters["branch"]
		
	if filters.get("department"):
		conditions_hol += " AND emp.department = '%s'" %filters["department"]
		conditions_la += " AND emp.department = '%s'" %filters["department"]
		conditions_emp += " AND emp.department = '%s'" %filters["department"]
		
	if filters.get("designation"):
		conditions_hol += " AND emp.designation = '%s'" %filters["designation"]
		conditions_la += " AND emp.designation = '%s'" %filters["designation"]
		conditions_emp += " AND emp.designation = '%s'" %filters["designation"]

	return conditions, filters, conditions_hol, conditions_la, conditions_emp

def get_leave_application(conditions_la, filters):
	la_map = frappe._dict()
	la = []

	for day in range(filters["total_days_in_month"]):
		date = str(filters["year"]) + "-" + str(filters["month"]) + "-" + str(day+1)
	
		query = """SELECT emp.name as employee, %s as day_of_month, la.leave_type
			FROM `tabLeave Application` la, `tabEmployee` emp
			WHERE la.employee = emp.name AND la.status = 'Approved' 
				AND la.docstatus = 1 AND la.from_date <= '%s' 
				AND la.to_date >= '%s' %s""" %((day+1), date, date, conditions_la)
		la2 = (frappe.db.sql(query, as_dict=1))
		if la2:
			for d in la2:
				la.append(d)
	for d in la:
		la_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
		la_map[d.employee][d.day_of_month] = d.leave_type

	return la_map
	
def get_employee_details(conditions_emp):
	emp_map = frappe._dict()
	for d in frappe.db.sql("""select emp.name, emp.employee_name, emp.designation,
		emp.department, emp.branch, emp.company
		from tabEmployee emp
		WHERE emp.docstatus = 0 %s"""% conditions_emp, as_dict=1):
		emp_map.setdefault(d.name, d)

	return emp_map
