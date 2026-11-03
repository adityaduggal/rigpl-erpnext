from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import IfNull
from frappe.utils import getdate, nowdate

DOCSTATUS = {"Draft": 0, "Submitted": 1, "Cancelled": 2}


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_trial_data(filters)

	return columns, data


def get_columns():
	return [
		"ID:Link/Trial Tracking:100", "Trial Status::100", "SO #:Link/Sales Order:100",
		"Date:Date:100", "Customer:Link/Customer:150",
		"Item:Link/Item:120", "Description::350", "Qty:Float:60", "Indicated Price:Currency:80",
		"Competitor::80", "Trial Owner::200", "Invoice No:Link/Sales Invoice:100","Days:Int:80"
	]


def get_trial_data(filters):
	check_dates(filters)
	tt = frappe.qb.DocType("Trial Tracking")
	so = frappe.qb.DocType("Sales Order")
	query = (
		frappe.qb.from_(tt)
		.join(so).on(so.name == tt.against_sales_order)
		.select(tt.name, tt.status, tt.against_sales_order, so.transaction_date, tt.customer, tt.item_code,
			tt.description, tt.qty, tt.base_rate, tt.competitor_name, tt.trial_owner,
			IfNull(tt.invoice_no, "Not Invoiced"))
		.orderby(tt.customer)
	)
	if filters.get("from_date"):
		query = query.where(so.transaction_date >= filters["from_date"])
	if filters.get("to_date"):
		query = query.where(so.transaction_date <= filters["to_date"])
	if filters.get("trial_status"):
		query = query.where(tt.status == filters["trial_status"])
	if filters.get("customer"):
		query = query.where(tt.customer == filters["customer"])
	if filters.get("trial_owner"):
		query = query.where(tt.trial_owner == filters["trial_owner"])
	if filters.get("status") in DOCSTATUS:
		query = query.where(tt.docstatus == DOCSTATUS[filters["status"]])
	else:
		query = query.where(tt.docstatus != 2)
	today = getdate(nowdate())
	return [list(row) + [(today - getdate(row[3])).days] for row in query.run(as_list=1)]


def check_dates(filters):
	if filters.get("from_date") and filters.get("to_date"):
		days = (getdate(filters["to_date"]) - getdate(filters["from_date"])).days
		if days < 0:
			frappe.throw("From Date has to be less than To Date")
		elif days > 1000:
			frappe.throw("Period should be less than 1000 days")
