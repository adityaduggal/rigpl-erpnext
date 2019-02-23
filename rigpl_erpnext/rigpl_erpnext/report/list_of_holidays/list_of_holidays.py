# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_entries(filters)

	return columns, data

def get_columns(filters):
	return [
		"Name:Link/Holiday List:150", "Date:Date:100", "Day::100", 
		"Holiday Name::200", "Weekly Off::50", "Base Holiday List:Link/Holiday List:150"
		]

def get_entries(filters):
	conditions= get_conditions(filters)
	
	list_of_holidays = frappe.db.sql("""SELECT name FROM `tabHoliday List` 
		WHERE base_holiday_list = '%s' """%\
		(filters.get("name")), as_list=1)
	
	data = []
	for hld_list in list_of_holidays:
		query = """SELECT hld.name, hol.holiday_date, 
			DAYNAME(hol.holiday_date), hol.description, 
			IF(hol.description = hld.weekly_off, "Yes", "No"), hld.base_holiday_list 
			FROM `tabHoliday List` hld, `tabHoliday` hol
			WHERE hol.parent = hld.name AND hld.name = '%s' %s
			ORDER BY hol.holiday_date ASC""" % (hld_list[0], conditions)
		t1_data = frappe.db.sql(query, as_list=1)
		if t1_data:
			for d in t1_data:
				data.append(d)
	return data

def get_conditions(filters):
	conditions = ""

	if filters.get("from_date"):
		conditions += " AND hol.holiday_date >='%s'" % filters["from_date"]

	if filters.get("to_date"):
		conditions += " AND hol.holiday_date <='%s'" % filters["to_date"]
		
	return conditions