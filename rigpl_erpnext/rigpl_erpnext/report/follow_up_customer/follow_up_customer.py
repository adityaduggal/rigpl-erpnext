# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import Concat, IfNull, Max
from frappe.utils import escape_html, getdate, nowdate
from ....utils.item_attribute_utils import chunks
from ....utils.report_utils import tree_and_descendants

NO_DATE = "1900-01-01"
NO_DAYS = 36500
HIDDEN_GROUP = "Changed Business"

def execute(filters=None):
	if not filters: filters = {}
	columns = get_columns(filters)
	data = get_data(filters)

	return columns, data

def get_columns(filters):
	if filters.get("details") == 1:
		return [
			"Customer:Link/Customer:150", "Contact:Link/Contact:120", "Mobile #::100", "Email::100",
			"Rating::100", "Territory:Link/Territory:100", "Last Comm Date:Date:100", "Next Date:Date:100", 
			"Medium::60", "Last Comm Details::200", "Link Comm:Link/Communication:120",
			"Comm Owner::120", "Comm Next Contact By::120", "Sales Person:Link/Sales Person:120"
		]
	else:
		return [
			"Customer:Link/Customer:150", "Contact:Link/Contact:120", "Mobile #::100", "Email::100",
			"Rating::100", "Territory:Link/Territory:100", "Requirement:Currency:100", 
			"SO Days:Int:50", "Comm Days:Int:50", "Last Comm Date:Date:100", "Next Date:Date:100", 
			"Sales Person:Link/Sales Person:120"
		]
	
def get_data(filters):
	if filters.get("details") == 1 and not filters.get("customer"):
		frappe.throw("For Detailed Report Customer Selection is Mandatory")
	sales_persons = None
	if filters.get("sales_person"):
		sales_persons = tree_and_descendants("Sales Person", filters["sales_person"])
	customers = get_customers(filters, sales_persons)
	names = [cu.name for cu in customers]
	contacts = get_contacts(names)
	sales_person = get_sales_person(names, sales_persons)

	if filters.get("details") == 1:
		data = []
		for comm in get_comm(filters):
			for cu in customers:
				data.append(customer_cols(cu, contacts) + [comm.communication_date, comm.next_action_date, comm.medium,
					comm.content, comm.name, comm.owner, comm.user, sales_person.get(cu.name, "-")])
		return data

	last_so = get_last_so_days(names)
	comm_days = get_comm_days(names)
	data = []
	for cu in customers:
		comm = comm_days.get(cu.name) or frappe._dict(com_days=NO_DAYS, last=NO_DATE, next=NO_DATE)
		data.append(customer_cols(cu, contacts) + [cu.requirement or 0, last_so.get(cu.name, NO_DAYS), comm.com_days,
			comm.last, comm.next, sales_person.get(cu.name, "-")])
	return data


def customer_cols(cu, contacts):
	con = contacts.get(cu.name)
	if con:
		link = '<a href="/app/contact/{0}">{1}</a>'.format(escape_html(con.name), escape_html(con.full_name or ""))
		cols = [link, con.mobile_no or "-", con.email_id or "-"]
	else:
		cols = ["-", "-", "-"]
	return [cu.name] + cols + [cu.customer_rating or "-", cu.territory or "-"]


def get_customers(filters, sales_persons):
	cu = frappe.qb.DocType("Customer")
	query = frappe.qb.from_(cu).select(cu.name, cu.customer_rating, cu.territory, cu.requirement)
	if sales_persons:
		st = frappe.qb.DocType("Sales Team")
		query = (query.join(st).on((st.parent == cu.name) & (st.parenttype == "Customer"))
			.where(st.sales_person.isin(sales_persons)))
	else:
		query = query.where(cu.docstatus == 0)
	# Disabled, frozen (black listed) and Changed Business customers are not followed up
	query = query.where((cu.disabled == 0) & (cu.is_frozen == 0))
	if frappe.db.exists("Customer Group", HIDDEN_GROUP):
		hidden = tree_and_descendants("Customer Group", HIDDEN_GROUP)
		query = query.where(cu.customer_group.isnull() | cu.customer_group.notin(hidden))
	if filters.get("min_rating"):
		query = query.where(cu.customer_rating >= filters["min_rating"])
	if filters.get("customer"):
		query = query.where(cu.name == filters["customer"])
	if filters.get("territory"):
		query = query.where(cu.territory.isin(tree_and_descendants("Territory", filters["territory"])))
	customers = query.run(as_dict=1)
	if not customers:
		frappe.throw("No Customers in given Criteria")
	return customers


def get_contacts(customers):
	"""{customer: its first Contact by name}"""
	co = frappe.qb.DocType("Contact")
	contacts = {}
	for chunk in chunks(customers):
		rows = (
			frappe.qb.from_(co)
			.select(co.name, Concat(co.first_name, " ", IfNull(co.last_name, "")).as_("full_name"), co.mobile_no,
				co.email_id, co.customer)
			.where(co.customer.isin(chunk))
			.orderby(co.name)
			.run(as_dict=1)
		)
		for row in rows:
			contacts.setdefault(row.customer, row)
	return contacts


def get_last_so_days(customers):
	"""{customer: days since its last Sales Order that is not cancelled}"""
	so = frappe.qb.DocType("Sales Order")
	today = getdate(nowdate())
	days = {}
	for chunk in chunks(customers):
		rows = (
			frappe.qb.from_(so)
			.select(so.customer, Max(so.transaction_date))
			.where((so.docstatus != 2) & (so.transaction_date <= today) & so.customer.isin(chunk))
			.groupby(so.customer)
			.run()
		)
		days.update({customer: (today - getdate(last)).days for customer, last in rows})
	return days


def get_comm_days(customers):
	"""
	{customer: (com_days, last, next)} of its Communications. The rows linked by timeline_name (v12
	data) replace the reference_name rows when their last date is later.
	"""
	result = {}
	for field in ("reference", "timeline"):
		for customer, row in get_comm_summary(customers, field).items():
			old = result.get(customer)
			if not old or getdate(row.last) > getdate(old.last):
				result[customer] = row
	return result


def get_comm_summary(customers, field):
	co = frappe.qb.DocType("Communication")
	name_field, doctype_field = co[field + "_name"], co[field + "_doctype"]
	today = getdate(nowdate())
	summary = {}
	for chunk in chunks(customers):
		rows = (
			frappe.qb.from_(co)
			.select(name_field.as_("customer"), Max(co.communication_date).as_("last"),
				Max(IfNull(co.next_action_date, NO_DATE)).as_("next"))
			.where((co.communication_type == "Communication") & (doctype_field == "Customer"))
			.where(name_field.isin(chunk))
			.groupby(name_field)
			.run(as_dict=1)
		)
		for row in rows:
			row.com_days = (today - getdate(row.last)).days
			summary[row.customer] = row
	return summary


def get_comm(filters):
	co = frappe.qb.DocType("Communication")
	cust = filters["customer"]
	query = (
		frappe.qb.from_(co)
		.select(co.communication_date, co.next_action_date, IfNull(co.communication_medium, "Comment").as_("medium"),
			co.content, co.name, co.owner, co.user)
		.where(
			((co.communication_type == "Communication")
				& ((co.reference_doctype == "Customer") | (co.timeline_doctype == "Customer"))
				& ((co.reference_name == cust) | (co.timeline_name == cust)))
			| ((co.communication_type == "Comment") & (co.reference_doctype == "Customer")
				& (co.reference_name == cust) & (co.comment_type == "Comment"))
		)
		.orderby(co.communication_date, order=frappe.qb.desc)
	)
	if filters.get("from_date"):
		query = query.where(co.communication_date >= filters["from_date"])
	return query.run(as_dict=1)


def get_sales_person(customers, sales_persons):
	"""{customer: its first Sales Team person}, only the persons of the filter when it is set"""
	st = frappe.qb.DocType("Sales Team")
	result = {}
	for chunk in chunks(customers):
		query = (
			frappe.qb.from_(st)
			.select(st.parent, st.sales_person)
			.where((st.parenttype == "Customer") & st.parent.isin(chunk))
			.orderby(st.idx)
		)
		if sales_persons:
			query = query.where(st.sales_person.isin(sales_persons))
		for parent, person in query.run():
			result.setdefault(parent, person)
	return result
