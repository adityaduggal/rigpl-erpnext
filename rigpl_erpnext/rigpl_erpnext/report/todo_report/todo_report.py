# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import Count
from pypika.terms import Case


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	result = get_summary() if filters.get("summary") == 1 else get_todo(filters)

	return columns, result


def get_columns(filters):
	if filters.get("summary") != 1:
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
	"""A System Manager sees all ToDos; other users only the ToDos they own or assigned."""
	td = frappe.qb.DocType("ToDo")
	query = (
		frappe.qb.from_(td)
		.select(td.name, td.priority, td.date, td.creation, td.description, td.reference_type,
			td.reference_name, td.owner, td.assigned_by)
		.orderby(td.owner)
		.orderby(td.date)
	)
	for field in ("status", "owner", "assigned_by"):
		if filters.get(field):
			query = query.where(td[field] == filters[field])
	user = frappe.session.user
	if "System Manager" not in frappe.get_roles(user):
		query = query.where((td.owner == user) | (td.assigned_by == user))
	result = []
	for todo in query.run(as_dict=1):
		reference = None
		if todo.reference_type:
			reference = frappe.get_desk_link(todo.reference_type, todo.reference_name)
		result.append([todo.name, todo.priority, todo.date, todo.creation, todo.description, reference,
			todo.owner, todo.assigned_by])
	return result


def get_summary():
	td = frappe.qb.DocType("ToDo")
	us = frappe.qb.DocType("User")
	return (
		frappe.qb.from_(td)
		.join(us).on(us.name == td.owner)
		.select(td.owner, Count(Case().when(td.status == "Open", 1)), Count(Case().when(td.status == "Closed", 1)),
			Case().when(us.enabled == 1, "Enabled").else_("Disabled"))
		.groupby(td.owner)
		.run(as_list=1)
	)
