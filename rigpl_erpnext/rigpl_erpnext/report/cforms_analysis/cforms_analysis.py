from __future__ import unicode_literals
import frappe
import datetime
import math
from frappe.utils import flt

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_va_entries(filters)

	return columns, data


def exceil(x,s):
	return s * math.ceil(float(x)/s)
	
def get_columns(filters):
		
	if filters.get("summary") == 1:
		return ["Customer:Link/Customer:200", "Net Total:Currency:100", "Grand Total:Currency:100",
		"Fiscal Year::100", "Customer Taxes::100"]
	else:
		return ["Invoice Date:Date:80", "Invoice#:Link/Sales Invoice:110","Customer:Link/Customer:200",
		"Taxes::100", "Customer Taxes::100", "Net Total:Currency:100", 
		"Grand Total:Currency:100","Fiscal Year::100", 
		"Q::30", "C-Form:Link/C-Form:130", "C-Form #::100",
		"State::100", "Received On:Date:80"]

def get_va_entries(filters):
	if filters.get("status") is None:
		frappe.msgprint("Please Select the Status of C-Form first", raise_exception=1)
	
	conditions = get_conditions(filters)
	
	if filters.get("status") == "Received" and filters.get("summary") is None :
		query = """select si.posting_date, si.name, si.customer, 
			si.taxes_and_charges, cu.default_taxes_and_charges, 
			si.net_total, si.grand_total, 
			si.fiscal_year, cf.name,
			cf.c_form_no, cf.state, cf.received_date
			FROM `tabSales Invoice` si, `tabC-Form` cf, `tabCustomer` cu
			WHERE si.docstatus = 1 AND si.customer=cu.name AND
			si.c_form_applicable = 'Yes' AND si.c_form_no = cf.name %s
			ORDER BY si.customer, si.name""" % conditions
		
		si = frappe.db.sql(query, as_list=1)
		
	elif filters.get("status") == "Not Received" and filters.get("summary") is None :
		query = """ select si.posting_date, si.name, si.customer, 
			si.taxes_and_charges, cu.default_taxes_and_charges, 
			si.net_total, si.grand_total, si.fiscal_year,
			null, null, null
			FROM `tabSales Invoice` si, `tabCustomer` cu
			WHERE si.docstatus = 1 AND si.customer=cu.name AND
			si.c_form_applicable = 'Yes' AND
			si.c_form_no is NULL %s
			ORDER BY si.customer, si.name""" % conditions
			
		si = frappe.db.sql(query, as_list=1)
	
	elif filters.get("status") == "Not Received" and filters.get("summary")==1 :
		query = """select si.customer, sum(si.net_total), sum(si.grand_total), si.fiscal_year,
			cu.default_taxes_and_charges
			FROM `tabSales Invoice` si, `tabCustomer` cu
			WHERE si.docstatus=1 AND si.c_form_applicable = 'Yes' AND
			si.c_form_no is NULL AND si.customer = cu.name %s
			GROUP BY si.customer, si.fiscal_year
			ORDER BY si.fiscal_year, si.customer""" % conditions
		
		si = frappe.db.sql(query, as_list=1)
	
	elif filters.get("status") == "Received" and filters.get("summary")==1 :
		query = """select si.customer, sum(si.net_total), sum(si.grand_total), si.fiscal_year,
			cu.default_taxes_and_charges
			FROM `tabSales Invoice` si, `tabCustomer` cu
			WHERE si.docstatus=1 AND si.c_form_applicable = 'Yes' AND
			si.c_form_no is NOT NULL AND si.customer = cu.name %s
			GROUP BY si.customer, si.fiscal_year
			ORDER BY si.fiscal_year, si.customer""" % conditions
		
		si = frappe.db.sql(query, as_list=1)
	else:
		si = []
		
	if filters.get("summary") is None:
		for i in range(0,len(si)):
			mo = (si[i][0]).month
			if mo < 4:
				qtr = "Q4"
			elif mo < 7:
				qtr = "Q1"
			elif mo < 10:
				qtr = "Q2"
			elif mo <= 12:
				qtr = "Q3"
			si[i].insert (8, qtr)
	
		si = sorted(si, key=lambda k: (k[0], k[1],k[2], k[3]))
	
	return si

def get_conditions(filters):
	conditions = ""
	if filters.get("fiscal_year"):
		conditions += "and si.fiscal_year = '%s'" % filters["fiscal_year"]

	if filters.get("quarter"):
		if filters.get("fiscal_year"):
			year = frappe.db.get_value("Fiscal Year", filters.get("fiscal_year"), "year_start_date").year
			quarter = filters.get("quarter")
			if quarter == "Q1":
				start_date = datetime.datetime.strptime(str(year)+"-04-01", '%Y-%m-%d').date()
				end_date = datetime.datetime.strptime(str(year) + "-06-30", '%Y-%m-%d').date()
			elif quarter == "Q2":
				start_date = datetime.datetime.strptime(str(year)+"-07-01", '%Y-%m-%d').date()
				end_date = datetime.datetime.strptime(str(year) + "-09-30", '%Y-%m-%d').date()
			elif quarter == "Q3":
				start_date = datetime.datetime.strptime(str(year)+"-10-01", '%Y-%m-%d').date()
				end_date = datetime.datetime.strptime(str(year) + "-12-31", '%Y-%m-%d').date()
			elif quarter == "Q4":
				start_date = datetime.datetime.strptime(str(year+1)+"-01-01", '%Y-%m-%d').date()
				end_date = datetime.datetime.strptime(str(year+1) + "-03-31", '%Y-%m-%d').date()
			conditions += "and si.posting_date >= '%s'" % start_date
			conditions += "and si.posting_date <= '%s'" % end_date
		else:
			frappe.msgprint("Please select fiscal year before selecting Quarter", raise_exception=1)

	if filters.get("customer"):
		conditions += "and si.customer = '%s'" % filters["customer"]

	if filters.get("date"):
		conditions += "and si.posting_date <= '%s'" % filters["date"]

	if filters.get("letter_head"):
		conditions += "and si.letter_head = '%s'" % filters["letter_head"]

	return conditions
