from __future__ import unicode_literals
import frappe
from frappe.utils import flt, getdate, nowdate

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
		"Competitor::80", "Trial Owner::200"
	]

def get_trial_data(filters):
	conditions = get_conditions(filters)
	
	query = """SELECT tt.name, tt.status, tt.against_sales_order, so.transaction_date, tt.customer,
	tt.item_code, tt.description, tt.qty, tt.base_rate, tt.competitor_name, tt.trial_owner
	FROM `tabTrial Tracking` tt, `tabSales Order` so
	WHERE tt.docstatus != 2 AND so.name = tt.against_sales_order %s
	ORDER BY tt.customer""" %conditions
	
	data = frappe.db.sql(query , as_list=1)

	return data



def get_conditions(filters):

	conditions = ""
	if (filters.get("from_date")):
		if (filters.get("to_date")):
			if getdate(filters.get("to_date")) < getdate(filters.get("from_date")):
				frappe.msgprint("From Date has to be less than To Date", raise_exception=1)
			elif (getdate(filters.get("to_date"))- getdate(filters.get("from_date"))).days>1000:
				frappe.msgprint("Period should be less than 1000 days", raise_exception=1)

		conditions += " and so.transaction_date >= '%s'" % filters["from_date"]

	if filters.get("to_date"):
		conditions += " and so.transaction_date <= '%s'" % filters["to_date"]

	if filters.get("trial_status"):
		conditions += " and tt.status = '%s'" % filters["trial_status"]


	if filters.get("customer"):
		conditions += " and tt.customer = '%s'" % filters["customer"]
		
	if filters.get("trial_owner"):
		conditions += " and tt.trial_owner = '%s'" % filters["trial_owner"]

	return conditions


