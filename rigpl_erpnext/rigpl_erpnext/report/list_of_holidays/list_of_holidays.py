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
		"Name:Link/Holiday List:100", "Date:Date:100", "Day::100", 
		"Holiday Name::200"
		]

def get_entries(filters):
	conditions = get_conditions(filters)
	
	
	query = """SELECT hld.name, hol.holiday_date, DAYNAME(hol.holiday_date), hol.description 
		FROM `tabHoliday List` hld, `tabHoliday` hol
		WHERE hol.parent = hld.name %s
		ORDER BY hol.holiday_date ASC""" % conditions
		
		
	data = frappe.db.sql(query, as_list=1)
	for i in range(len(data)):
		pass
	
	return data

def get_conditions(filters):
	conditions = ""
	
	if filters.get("name"):
		conditions += " AND hld.name = '%s'" % filters["name"]
		
	if filters.get("from_date"):
		conditions += " AND hol.holiday_date >='%s'" % filters["from_date"]

	if filters.get("to_date"):
		conditions += " AND hol.holiday_date <='%s'" % filters["to_date"]
		
		
	return conditions