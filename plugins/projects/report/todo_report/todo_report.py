# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.widgets.reportview import execute as runreport
from webnotes.utils import getdate

def execute(filters=None):
	#conditions = get_conditions (filters)
	priority_map = {"High": 3, "Medium": 2, "Low": 1}

	todo_list = runreport(doctype="ToDo", fields=["name", "date", "description",
		"priority", "reference_type", "reference_name", "assigned_by", "owner"], 
		filters=[["ToDo", "checked", "!=", 1]])

	todo_list.sort(key=lambda todo: (priority_map.get(todo.priority, 0), 
		todo.date and getdate(todo.date) or getdate("1900-01-01")), reverse=True)

	columns = ["ID:Link/ToDo:120", "Priority::60", "Date:Date", "Description::350",
		"Reference::200", "Assigned To/Owner:Data:120", "Assigned By:Data:120"]

	result = []
	for todo in todo_list:
		if todo.reference_type:
			todo.reference = """<a href="#Form/%s/%s">%s: %s</a>""" % (todo.reference_type, 
				todo.reference_name, todo.reference_type, todo.reference_name)
		else:
			todo.reference = "-"
		
		if todo.date is None:
			todo.date = "1900-01-01"
		
		if todo.assigned_by is None:
			todo.assigned_by = "-"
			
		if todo.description is None:
			todo.description = "-"
		
		result.append([todo.name, todo.priority, todo.date, todo.description,
			todo.reference, todo.owner, todo.assigned_by])

	return columns, result

def get_conditions(filters):
	if filters.get("owner"):
		conditions += " todo.owner == '%s'" % filters["owner"]
	else:
		webnotes.msgprint("Owner Selection is Mandatory", raise_exception=1)
		
	if filters.get("assigned_by"):
		conditions += " and todo.assigned_by == '%s'" % filters["assigned_by"]