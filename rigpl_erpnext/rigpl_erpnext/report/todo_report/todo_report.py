# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.desk.reportview import execute as runreport
from frappe.utils import getdate

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	result = get_todo(filters)

	return columns, result

def get_columns(filters):
	if filters.get("summary") <> 1:
		return [
			"ID:Link/ToDo:30", "Priority::80",
			"Due Date:Date:90", "Assignment Date:Date:90",
			"Description::400", "Reference::150", "Owner::150", "Assigned By::150"
		]
	else:
		return [
			"User::200", "Open ToDo:Int:80", "Closed ToDo:Int:80", "User Status::100"
		]

def get_todo(filters):
	conditions = get_conditions(filters)
	
	if filters.get("summary") <> 1:
		query = """SELECT name, priority, date, creation, description, 
			reference_type, reference_name, owner, assigned_by
		FROM `tabToDo` %s
		ORDER BY owner, date""" % conditions
			
		data = frappe.db.sql(query ,as_dict=1)
		result = []
		role = frappe.db.sql("""SELECT role FROM `tabUserRole` 
			WHERE parent = '%s'""" % frappe.session.user, as_list=1)
		for i in role:
			if 'System Manager' in i:
				role = "Allowed"
		for todo in data:
			if todo.owner==frappe.session.user or todo.assigned_by==frappe.session.user or role == 'Allowed':
				if todo.reference_type:
					todo.reference = """<a href="#Form/%s/%s">%s: %s</a>""" % (todo.reference_type,
							todo.reference_name, todo.reference_type, todo.reference_name)
				result.append([todo.name, todo.priority, todo.date, todo.creation,
					todo.description, todo.reference, todo.owner, todo.assigned_by])
	else:

		query = """SELECT td.owner, COUNT(IF(td.status = 'Open', 1, NULL)), 
			COUNT(IF(td.status = 'Closed', 1, NULL)), IF(us.enabled = 1, "Enabled", "Disabled")
			FROM `tabToDo` td, `tabUser` us
			WHERE td.owner = us.name
			GROUP BY td.owner"""
		result = frappe.db.sql(query, as_list=1)

	return result



def get_conditions(filters):

	conditions = ""
	
	if filters.get("status"):
		conditions += "WHERE status = '%s'" % filters["status"]

	if filters.get("owner"):
		conditions += " and owner = '%s'" % filters["owner"]


	if filters.get("assigned_by"):
		conditions += " and assigned_by = '%s'" % filters["assigned_by"]
		
	if filters.get("trial_owner"):
		conditions += " and tt.trial_owner = '%s'" % filters["trial_owner"]
		

	return conditions