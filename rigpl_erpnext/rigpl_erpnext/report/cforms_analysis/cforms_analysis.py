from __future__ import unicode_literals
import frappe
import datetime
import math
from frappe.utils import flt

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_va_entries(filters)

	return columns, data


def exceil(x,s):
	return s * math.ceil(float(x)/s)
	
def get_columns():


	return [
		"Invoice Date:Date:80", "Invoice#:Link/Sales Invoice:110",
		"Customer:Link/Customer:200","Taxes::100", 
		"Net Total:Currency:100","Grand Total:Currency:100", 
		"C-Form:Link/C-Form:130", "C-Form #::100", 
		"State::100", "Received On:Date:80",
	]

def get_va_entries(filters):
	conditions = get_conditions(filters)
	if filters.get("status") == "Received":
		si = frappe.db.sql(""" select si.posting_date, si.name, si.customer, 
			si.taxes_and_charges,si.net_total, si.grand_total, cf.name,
			cf.c_form_no, cf.state, cf.received_date
			FROM `tabSales Invoice` si, `tabC-Form` cf
			WHERE si.docstatus = 1 AND
			si.c_form_applicable = 'Yes' AND si.c_form_no = cf.name %s
			ORDER BY si.customer, si.name""" % conditions, as_list=1)
	else:
		si = frappe.db.sql(""" select si.posting_date, si.name, si.customer, 
			si.taxes_and_charges, si.net_total, si.grand_total
			FROM `tabSales Invoice` si
			WHERE si.docstatus = 1 AND
			si.c_form_applicable = 'Yes' %s
			ORDER BY si.customer, si.name""" % conditions, as_list=1)
	#fmonth = frappe.db.get_value("Fiscal Year", filters.get("fiscal_year"), "year_start_date")
	#frappe.msgprint(len(si))
	#find quarter of invoice:
	#for i in range (0,len(si)):
	#	frappe.msgprint(si[i][0])
		#quarter = ((exceil((22-fmonth.month+si[i][0].month),3))/3%4)+1
		#si[i].insert(1,"Q"+quarter)
	
	return si

def get_conditions(filters):
	conditions = ""
	if filters.get("fiscal_year"):
		conditions += "and si.fiscal_year = '%s'" % filters["fiscal_year"]

	if filters.get("customer"):
		conditions += "and si.customer = '%s'" % filters["customer"]

	if filters.get("company"):
		conditions += "and si.letter_head = '%s'" % filters["company"]

	return conditions
