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
		if filters.get("separated_tod"):
			return ["Customer:Link/Customer:200","Net Total:Currency:120", "TOD Applicable::60"]
		else:
			return ["Customer:Link/Customer:200","Net Total:Currency:120"]
	else:
		return ["Invoice#:Link/Sales Invoice:120", "Date:Date:80", "Customer:Link/Customer:200",
		"Item Code:Link/Item:150", "Description::200", "Qty:Float:80", 
		"List Price:Currency:80", "Discount:Float:40", 
		"Net Price:Currency:120", "Net Total:Currency:120", "TOD App::60", "PL Item::60"]

def get_si_entries(filters):
	conditions = get_conditions(filters)
	
	if filters.get("summary"):
		if filters.get("separated_tod"):
			query = """select si.customer, sum(sid.base_net_amount), it.stock_maintained
				FROM `tabSales Invoice` si, `tabSales Invoice Item` sid, `tabItem` it
				WHERE sid.parent = si.name AND sid.item_code = it.name AND
				si.docstatus = 1 %s 
				GROUP BY si.customer, it.stock_maintained""" % conditions
		else:
			query = """select si.customer, sum(sid.base_net_amount), it.stock_maintained
				FROM `tabSales Invoice` si, `tabSales Invoice Item` sid, `tabItem` it
				WHERE sid.parent = si.name AND sid.item_code = it.name AND
				si.docstatus = 1 %s 
				GROUP BY si.customer""" % conditions
	
	else:
		query = """select si.name, si.posting_date, si.customer, sid.item_code,
			sid.description, sid.qty, sid.base_price_list_rate, sid.discount_percentage, 
			sid.base_net_rate, sid.base_net_amount, it.stock_maintained, it.pl_item
			FROM `tabSales Invoice` si, `tabSales Invoice Item` sid, `tabItem` it
			WHERE sid.parent = si.name AND sid.item_code = it.name AND
			si.docstatus = 1 %s 
			ORDER BY si.customer, si.posting_date, si.name, sid.item_code""" % conditions
	
	si = frappe.db.sql(query, as_list=1)
	return si

def get_conditions(filters):
	conditions = ""
	if filters.get("fiscal_year"):
		frm_date = frappe.db.get_value("Fiscal Year", filters.get("fiscal_year"), "year_start_date")
		to_date = frappe.db.get_value("Fiscal Year", filters.get("fiscal_year"), "year_end_date")
		conditions += "and si.posting_date >= '%s'" % frm_date
		conditions += "and si.posting_date <= '%s'" % to_date

	if filters.get("customer"):
		conditions += "and si.customer = '%s'" % filters["customer"]

	if filters.get("to_date"):
		conditions += "and si.posting_date <= '%s'" % filters["to_date"]

	if filters.get("from_date"):
		conditions += "and si.posting_date >= '%s'" % filters["from_date"]

	if filters.get("letter_head"):
		conditions += "and si.letter_head = '%s'" % filters["letter_head"]

	return conditions
