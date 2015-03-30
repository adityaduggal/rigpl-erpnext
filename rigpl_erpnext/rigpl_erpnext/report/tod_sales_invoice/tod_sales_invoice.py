from __future__ import unicode_literals
import frappe
import datetime
import math
from frappe.utils import flt

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_si_entries(filters)

	return columns, data


def exceil(x,s):
	return s * math.ceil(float(x)/s)
	
def get_columns(filters):
	if filters.get("summary"):
		return ["Customer:Link/Customer:200","Net Total:Currency:120", "PL Item::60"]
	else:
		return ["Invoice#:Link/Sales Invoice:120", "Date:Date:80", "Customer:Link/Customer:200",
		"Item Code:Link/Item:150", "Description::200", "Qty:Float:80", 
		"List Price:Currency:80", "Discount:Float:40", 
		"Net Price:Currency:120", "Net Total:Currency:120", "TOD App::60", "PL Item::60"]

def get_si_entries(filters):
	conditions = get_conditions(filters)
	
	if filters.get("summary"):
		query = """select si.customer, sum(sid.base_amount), it.pl_item
			FROM `tabSales Invoice` si, `tabSales Invoice Item` sid, `tabItem` it
			WHERE sid.parent = si.name AND sid.item_code = it.name AND
			si.docstatus = 1 %s 
			GROUP BY si.customer, it.pl_item""" % conditions
	
	else:
		query = """select si.name, si.posting_date, si.customer, sid.item_code,
			sid.description, sid.qty, sid.base_price_list_rate, sid.discount_percentage, 
			sid.base_rate, sid.base_amount, it.stock_maintained, it.pl_item
			FROM `tabSales Invoice` si, `tabSales Invoice Item` sid, `tabItem` it
			WHERE sid.parent = si.name AND sid.item_code = it.name AND
			si.docstatus = 1 %s 
			ORDER BY si.customer, si.posting_date, si.name, sid.item_code""" % conditions
	
	si = frappe.db.sql(query, as_list=1)
	return si

def get_conditions(filters):
	conditions = ""
	if filters.get("fiscal_year"):
		conditions += "and si.fiscal_year = '%s'" % filters["fiscal_year"]
	else:
		frappe.msgprint("Please Select Fiscal Year First", raise_exception=1)


	if filters.get("customer"):
		conditions += "and si.customer = '%s'" % filters["customer"]

	if filters.get("to_date"):
		conditions += "and si.posting_date <= '%s'" % filters["to_date"]

	if filters.get("from_date"):
		conditions += "and si.posting_date >= '%s'" % filters["from_date"]

	if filters.get("letter_head"):
		conditions += "and si.letter_head = '%s'" % filters["letter_head"]

	return conditions
