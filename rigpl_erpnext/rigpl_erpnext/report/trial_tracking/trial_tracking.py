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
		"Trial Status::100", "SO #:Link/Sales Order:100", "SO Date:Date:90", "Customer:Link/Customer:150",
		"Item:Link/Item:120", "Description::350", "Qty:Float/2:60", "PL:Currency:80",
		"Rate:Currency:80", "Amount:Currency:100", "Delivered Qty:Float/2:80", "Sales Person::200"
	]

def get_trial_data(filters):
	conditions = get_conditions(filters)

	data = frappe.db.sql("""select so.trial_status, so.name , so.transaction_date, so.customer,
	soi.item_code, soi.description, soi.qty, soi.ref_rate, soi.export_rate,
	soi.export_amount, soi.delivered_qty, st.sales_person
	from `tabSales Order` so, `tabSales Order Item` soi, `tabSales Team` st
	where so.docstatus = 1 and so.order_type = "Trial Order"
	and soi.parent = so.name and st.parenttype = "Sales Order"
	and st.parent = so.name %s
	order by so.transaction_date""" %conditions , as_list=1)

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
	else:
		frappe.msgprint("Please select From Date", raise_exception = 1)

	if filters.get("to_date"):
		conditions += " and so.transaction_date <= '%s'" % filters["to_date"]

	if filters.get("trial_status"):
		conditions += " and so.trial_status = '%s'" % filters["trial_status"]


	if filters.get("customer"):
		conditions += " and so.customer = '%s'" % filters["customer"]

	return conditions


