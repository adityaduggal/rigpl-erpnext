from __future__ import unicode_literals
import frappe
import datetime
import time
from frappe import msgprint, _

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_entries(filters)

	return columns, data

def get_columns(filters):
	return [
	"ID:Link/Sales Order:100",  "SO Date:Date:100", "Customer:Link/Customer:140",
	"Item Code:Link/Item:120", "Description::300", "Qty:Float:100",
	"Amount:Currency:120", "Territory:Link/Territory:150",
	"Sales Partner:Link/Sales Partner:150"
	]

def get_entries (filters):

	conditions = get_conditions(filters)
	conditions_cust = get_cust_conditions (filters)

	data = frappe.db.sql("""select so.name, so.transaction_date, so.customer,
	sod.item_code, sod.description, sod.qty, sod.amount
	from `tabSales Order` so, `tabSales Order Item` sod where sod.parent = so.name
	AND so.docstatus = 1 %s
	order by so.customer""" %conditions , as_list=1)

	cust = frappe.db.sql("""select cu.name, cu.territory, cu.default_sales_partner
	FROM `tabCustomer` cu where cu.docstatus = 0 %s
	ORDER BY cu.name"""	%conditions_cust, as_list=1)

	data2 = []

	for i in range(0,len(data)):
		#frappe.msgprint(i)
		if any (data[i][2] in s for s in cust):
			for j in range(0,len(cust)):
				if data[i][2] == cust[j][0]:
					if cust[j][1] is None:
						data[i].insert(7,None)
					else:
						data[i].insert(7,cust[j][1])
					if cust[j][2] is None:
						data[i].insert(8,None)
					else:
						data[i].insert(8,cust[j][2])
			data2.append(data[i])

	return data2

def get_conditions(filters):
	conditions = ""

	if filters.get("from_date"):
		conditions += " and so.transaction_date >= '%s'" % filters["from_date"]

	if filters.get("to_date"):
		conditions += " and so.transaction_date <= '%s'" % filters["to_date"]
	return conditions

def get_cust_conditions(filters):
	conditions_cust = ""

	if filters.get("sales_partner"):
		conditions_cust += "and cu.default_sales_partner = '%s'" % filters["sales_partner"]

	if filters.get("territory"):
		conditions_cust += "and cu.territory = '%s'" % filters["territory"]

	return conditions_cust
