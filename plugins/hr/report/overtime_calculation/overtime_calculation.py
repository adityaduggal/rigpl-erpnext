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
import datetime
import math
from webnotes.utils import cstr, cint
from webnotes import msgprint, _

def execute(filters=None):
	conditions, filters, last_day = get_conditions(filters)
	columns = get_columns(filters)
	att_map = get_attendance_list(conditions, filters)
	emp_map = get_employee_details()
	holidays_num, working_days = get_working_days(conditions,filters)
	
	data = []

	for emp in sorted(att_map):
		emp_det = emp_map.get(emp)
		if emp_det:
			for count in (0,1):
				if count == 0:
					timetype = 'In Time'
					#t_present = 0
				elif count == 1:
					timetype = 'Out Time'
				row = [emp, emp_det.employee_name, timetype]

				for day in range(filters["total_days_in_month"]):
					attendance = att_map.get(emp).get(day + 1)
					if attendance:
						row.append(attendance[count+1])
						#if attendance[0]== "P =Present" and count==0:
							#t_present += 1
					else:
						row.append(['NA','H','H'][count+1])
				#row += [t_present]
				data.append(row)
			
			#Get the Over Time:
			row = [emp, emp_det.employee_name, "OT"]
			data.append(row)
	if data:
		for i in range(0,len(data),3):
			t_ot = t_abs = t_pres = t_leav = ot_rate = 0
			basic_sal = ot_amt = sal_amt = ded = net_sal = 0
			#webnotes.msgprint(i)
			for j in range(last_day):
				if data[i][j+3] <> 'H':
					#webnotes.msgprint(j)
					intime =datetime.datetime.strptime(data[i][j+3],"%H:%M:%S")
					outtime = datetime.datetime.strptime(data[i+1][j+3],"%H:%M:%S")
					if intime <> outtime:
						ot = outtime - intime - datetime.timedelta(hours=8) #deduct the 8 hours of normal working hours
						ot = ot - datetime.timedelta(minutes=30) #deduct lunch time
						ot = ot.total_seconds()
						ot = round(ot/3600,2)
						ot = round_down (ot,2,0.5)
						t_pres += 1
					else:
						attendance = att_map.get(data[i][0]).get(j+1)
						if attendance[0] == 'X =Unauthorized Leave':
							ot = -8
							t_abs += 1
						elif attendance[0] == 'L =Leave':
							ot = 0
							t_leav += 1
					#webnotes.msgprint(j)
					t_ot += ot
						
				else:
					ot = 'H'
				data[i+2].insert(j+3, ot)
			data[i] +=(['{0}{1}'.format('T Working Days= ', working_days), '{0}{1}'.format('T Present= ', t_pres), 
				'{0}{1}'.format('Total OT= ', t_ot), '{0}{1}'.format('Total X= ', t_abs)])
			
			data[i+1] +=(['{0}{1}'.format('T Leave= ', t_leav), '{0}{1}'.format('OT Rate= ', ot_rate), 
				'{0}{1}'.format('Basic Salary= ', basic_sal)])
			
			
			data[i+2] +=(['{0}{1}'.format('OT Amt= ', ot_amt), '{0}{1}'.format('Salary Amt= ', sal_amt), 
				'{0}{1}'.format('Deductions= ', ded), '{0}{1}'.format('Net Salary= ', net_sal)])
			#if j == last_day-1:
				#webnotes.msgprint(data[i+2])


	return columns, data

def get_working_days(conditions, filters):
	from calendar import monthrange	
	filters["total_days_in_month"] = monthrange(cint(filters["fiscal_year"].split("-")[-1]), 
		filters["month"])[1]
	
	last_day = monthrange(cint(filters["fiscal_year"].split("-")[-1]), 
		filters["month"])[1]
	
	month_num = filters["month"]
	if month_num<4:
		year_4 = cint(filters["fiscal_year"].split("-")[-1])
	else:
		year_4 = cint(filters["fiscal_year"].split("-")[0])

	if month_num >=1 and month_num <10:
		month_num = '{0}{1}'.format("0",month_num)

	first_day_of_month = '{0}{1}{2}{3}{4}{5}'.format("'",year_4,"-", month_num,  "-01", "'")
	last_day_of_month = '{0}{1}{2}{3}{4}{5}{6}'.format("'",year_4,"-", month_num, "-", last_day,"'")
	
	holidays = webnotes.conn.sql ("""select h.holiday_date from tabHoliday h
		WHERE h.holiday_date >= %s AND h.holiday_date <= %s""" 
		%(first_day_of_month, last_day_of_month))
	
	
	holidays = set(holidays)
	holidays_num = len(holidays)
	working_days = last_day - holidays_num

	return holidays_num, working_days

def get_employee_details():
	emp_map = webnotes._dict()
	for d in webnotes.conn.sql("""select name, employee_name 
		from tabEmployee where docstatus < 2 and status = 'Active'""", as_dict=1):
			emp_map.setdefault(d.name, d)

	return emp_map	

def get_attendance_list(conditions, filters):
	attendance_list = webnotes.conn.sql("""SELECT employee, day(att_date) as day_of_month, 
		custom_status, in_time, out_time from tabAttendance where docstatus = 1 %s order by employee, att_date""" % 
		conditions, filters, as_dict=1)

	att_map = {}
	for d in attendance_list:
		att_map.setdefault(d.employee, webnotes._dict()).setdefault(d.day_of_month, "")
		att_map[d.employee][d.day_of_month] = d.custom_status, d.in_time, d.out_time
	return att_map
	
def get_columns(filters):
	columns = [
		"Employee:Link/Employee:120", "Employee Name::140", "Time Type::100"
	]

	for day in range(filters["total_days_in_month"]):
		columns.append(cstr(day+1) +":Time:70")

	columns += ["A::120", "B::120", "C::120", "D::120"]
	return columns


def get_conditions(filters):	
	if not (filters.get("month") and filters.get("fiscal_year")):
		msgprint(_("Please select month and year"), raise_exception=1)

	filters["month"] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", 
		"Dec"].index(filters["month"]) + 1

	from calendar import monthrange	
	filters["total_days_in_month"] = monthrange(cint(filters["fiscal_year"].split("-")[-1]), 
		filters["month"])[1]
	
	last_day = monthrange(cint(filters["fiscal_year"].split("-")[-1]), 
		filters["month"])[1]

	conditions = " and month(att_date) = %(month)s and fiscal_year = %(fiscal_year)s"

	if filters.get("employee"): conditions += " and employee = %(employee)s"

	return conditions, filters, last_day
	
def round_down(num, prec,divisor):
	return float(math.floor(num/divisor)) * divisor
