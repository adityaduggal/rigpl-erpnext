# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import IfNull
from frappe.utils import getdate, nowdate
from ....utils.item_attribute_utils import chunks
from ....utils.report_utils import tree_and_descendants

NO_DATE = "1900-01-01"
# Not followed up when no Status filter is set. Lead Lost and Converted Through Dealer are v12 values.
CLOSED_STATUSES = ("Converted", "Converted Through Dealer", "Do Not Contact", "Lead Lost", "Lost Quotation")

def execute(filters=None):

	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_data(filters)

	return columns, data

def get_columns(filters):
	if filters.get("details") == 1:
		return [
			"Lead:Link/Lead:100", "Company::250", "Contact::120", "Mobile #::100", 
			"Email::100", "Status::100", "Requirement:Currency:100", 
			"Territory:Link/Territory:100", "Last Date:Date:100", "Next Date:Date:100",
			"Medium::60", "Last Comm Details::200", "Link Comm:Link/Communication:80", 
			"Comm Owner::120", "Comm Next Contact By::120"
		]
	else:
		return [
			"Lead:Link/Lead:100", "Company::250", "Contact::120", "Mobile #::100", 
			"Email::100", "Status::100", "Requirement:Currency:100", 
			"Territory:Link/Territory:100", "Days Since:Int:60",
			"Last Date:Date:100", "Next Date:Date:100",
			"Last Comm Details::200", "Link Comm:Link/Communication:80", 
			"Lead Owner::120", "Next Contact By::120"
		]
	
def get_data(filters):
	if filters.get("details") == 1:
		if not filters.get("lead"):
			frappe.throw("For Detailed Report Lead Selection is Mandatory")
		return get_details(filters)

	ld = frappe.qb.DocType("Lead")
	query = (
		frappe.qb.from_(ld)
		.select(ld.name, ld.company_name, ld.lead_name, IfNull(ld.mobile_no, "-"), IfNull(ld.email_id, "-"),
			ld.status, ld.requirement, IfNull(ld.territory, "-"), IfNull(ld.lead_owner, "-"),
			IfNull(ld.contact_by, "-"))
		.where(ld.docstatus == 0)
		.orderby(ld.name)
	)
	leads = add_lead_filters(query, ld, filters).run(as_list=1)
	last = get_last_comms([lead[0] for lead in leads])
	today = getdate(nowdate())
	data = []
	for lead in leads:
		comm = last.get(lead[0])
		if comm:
			last_date = comm.communication_date or NO_DATE
			comm_cols = [last_date, comm.next_action_date or NO_DATE, comm.content or "-", comm.name]
		else:
			last_date = NO_DATE
			comm_cols = [NO_DATE, NO_DATE, "-", "-"]
		data.append(lead[:8] + [(today - getdate(last_date)).days] + comm_cols + lead[8:])
	return data


def get_details(filters):
	ld = frappe.qb.DocType("Lead")
	co = frappe.qb.DocType("Communication")
	query = (
		frappe.qb.from_(ld)
		.join(co).on((co.reference_doctype == "Lead") & (co.reference_name == ld.name))
		.select(ld.name, ld.company_name, ld.lead_name, IfNull(ld.mobile_no, "-"), IfNull(ld.email_id, "-"),
			ld.status, ld.requirement, IfNull(ld.territory, "-"), co.communication_date,
			co.next_action_date, co.communication_medium, co.content, co.name, co.owner, co.user)
		.where(co.communication_type == "Communication")
		.orderby(ld.name)
		.orderby(co.communication_date, order=frappe.qb.desc)
		.orderby(co.creation, order=frappe.qb.desc)
	)
	return add_lead_filters(query, ld, filters).run(as_list=1)


def add_lead_filters(query, ld, filters):
	if filters.get("status"):
		query = query.where(ld.status == filters["status"])
	else:
		query = query.where(ld.status.isnull() | ld.status.notin(CLOSED_STATUSES))
	if filters.get("lead"):
		query = query.where(ld.name == filters["lead"])
	if filters.get("territory"):
		query = query.where(ld.territory.isin(tree_and_descendants("Territory", filters["territory"])))
	if filters.get("owner"):
		query = query.where(ld.lead_owner == filters["owner"])
	if filters.get("next_contact"):
		query = query.where(ld.contact_by == filters["next_contact"])
	return query


def get_last_comms(leads):
	"""{lead: its latest Communication}, 1 query for each chunk of leads."""
	co = frappe.qb.DocType("Communication")
	last = {}
	for chunk in chunks(leads):
		rows = (
			frappe.qb.from_(co)
			.select(co.reference_name, co.name, co.communication_date, co.next_action_date, co.content)
			.where((co.communication_type == "Communication") & (co.reference_doctype == "Lead"))
			.where(co.reference_name.isin(chunk))
			.orderby(co.communication_date, order=frappe.qb.desc)
			.run(as_dict=1)
		)
		for row in rows:
			last.setdefault(row.reference_name, row)
	return last
