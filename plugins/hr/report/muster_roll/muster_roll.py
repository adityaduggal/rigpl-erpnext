# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

#What is Muster Roll
#Muster Roll is actually the Register of Employee Data which is usually kept in the Factory or Establishment. It usually consist of the following:
#(i) Name of Employee
#(ii) Age
#(iii) Sex
#(iv) Date of Joining
#(v) Roll/Employee number
#(vi) Type of employment: Regular/Contract/Casual/Badli etc
#(vii) Category(Designation): Management/Supervisor/Skilled/Semi Skilled/Unskilled
#(viii) Rate of Pay
#(ix) Shift (if applicable)
#(x) Attendance

# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.utils import cstr, cint
from webnotes import msgprint, _

def execute(filters=None):
	if not filters: filters = {}

	conditions, filters = get_conditions(filters)
	columns = get_columns(filters)
	holidays = get_holidays(filters)
	att_map = get_attendance_list(conditions, filters)
	emp_map = get_employee_details()

	data = []
	for emp in sorted(att_map):
		emp_det = emp_map.get(emp)
		if emp_det:
			row = [emp, emp_det.employee_name]

			total_p = total_l = total_x = total_h = 0.0
			for day in range(filters["total_days_in_month"]):
				custom_status = att_map.get(emp).get(day + 1)
				status_map = {"P =Present": "P", "X =Unauthorized Leave": "X", "L =Leave": "L", None:None}
				row.append(status_map[custom_status])

				if custom_status == "P =Present":
					total_p += 1
				elif custom_status == "X =Unauthorized Leave":
					total_x += 1
				elif custom_status == "L =Leave":
					total_l += 1
				elif custom_status is None:
					total_h +=1

			row += [total_p, total_x, total_l, total_h]

			data.append(row)

	return columns, data

def get_columns(filters):
	columns = [
		"Employee:Link/Employee:120", "Employee Name::140"
	]

	for day in range(filters["total_days_in_month"]):
		columns.append(cstr(day+1) +"::35")

	columns += ["Total P:Float:80", "Total X:Float:80", "Total L:Float:80","Holidays:Float:80"]
	return columns

def get_attendance_list(conditions, filters):
	attendance_list = webnotes.conn.sql("""select employee, day(att_date) as day_of_month, 
		custom_status from tabAttendance where docstatus = 1 %s order by employee, att_date""" % 
		conditions, filters, as_dict=1)

	att_map = {}
	for d in attendance_list:
		att_map.setdefault(d.employee, webnotes._dict()).setdefault(d.day_of_month, "")
		att_map[d.employee][d.day_of_month] = d.custom_status

	return att_map

def get_holidays(filters):
	holidays = webnotes.conn.sql("""
		SELECT h.holiday_date, h.description, hl.fiscal_year
		FROM tabHoliday h, `tabHoliday List` hl
		WHERE h.parent=hl.name 
		AND hl.fiscal_year = '%s'
		ORDER BY h.holiday_date""" %filters.get("fiscal_year"))
	
	return holidays

def get_conditions(filters):	
	if not (filters.get("month") and filters.get("fiscal_year")):
		msgprint(_("Please select month and year"), raise_exception=1)

	filters["month"] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", 
		"Dec"].index(filters["month"]) + 1

	from calendar import monthrange	
	filters["total_days_in_month"] = monthrange(cint(filters["fiscal_year"].split("-")[-1]), 
		filters["month"])[1]

	conditions = " and month(att_date) = %(month)s and fiscal_year = %(fiscal_year)s"

	if filters.get("employee"): conditions += " and employee = %(employee)s"

	return conditions, filters

def get_employee_details():
	emp_map = webnotes._dict()
	for d in webnotes.conn.sql("""select name, employee_name, designation, department, 
		branch, company from tabEmployee where docstatus < 2 and status = 'Active'""", as_dict=1):
			emp_map.setdefault(d.name, d)

	return emp_map