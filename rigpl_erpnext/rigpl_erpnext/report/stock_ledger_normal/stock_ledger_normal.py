from __future__ import unicode_literals
import frappe
from frappe.utils import flt

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_sl_entries(filters)

	return columns, data

def get_columns():


	return [
		"Date:Date:80", "Time:Time:70" ,"Item:Link/Item:130", "Description::250",
		"Qty:Float:60", "Balance:Float:90", "Warehouse::120", "Voucher No:Dynamic Link/Voucher Type:130", 
		"Voucher Type::140","Name::100"
	]

def get_sl_entries(filters):
	conditions = get_conditions(filters)
	conditions_item = get_conditions_item(filters)

	data = frappe.db.sql("""select posting_date, posting_time, item_code,
		actual_qty, qty_after_transaction, warehouse, voucher_no, voucher_type,
		name from `tabStock Ledger Entry` where is_cancelled = "No" %s
		order by posting_date desc, posting_time desc, name desc"""
		% conditions, as_list=1)

	desc = frappe.db.sql("""select it.name, it.description FROM `tabItem` it WHERE %s"""
		%conditions_item, as_list=1)

	#frappe.msgprint(desc)
	for i in range(0,len(data)):
		data[i].insert(3, desc[0][1])

	return data

def get_conditions(filters):
	conditions = ""
	if filters.get("item"):
		conditions += " and item_code = '%s'" % filters["item"]
	else:
		frappe.msgprint("Please select an Item Code first", raise_exception=1)

	if filters.get("warehouse"):
		conditions += " and warehouse = '%s'" % filters["warehouse"]

	if filters.get("from_date"):
		conditions += " and posting_date >= '%s'" % filters["from_date"]

	if filters.get("to_date"):
		conditions += " and posting_date <= '%s'" % filters["to_date"]

	return conditions

def get_conditions_item(filters):
	conditions_item = ""
	if filters.get("item"):
		conditions_item += " it.name = '%s'" % filters["item"]
	else:
		frappe.msgprint("Please select an Item Code first", raise_exception=1)

	return conditions_item
