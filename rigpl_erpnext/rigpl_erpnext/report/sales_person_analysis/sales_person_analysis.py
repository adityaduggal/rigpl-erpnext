# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

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
	"Sales Person:Link/Sales Person:150","Target:Currency:100","SO Booked:Currency:100", "SI Raised:Currency:100",
	"Est AR:Currency:100"
	#, "D::100", "E::100", "F::100", "G::100", "H::100", "J::100", #"K::100","L::100","M::100", "N::100"
	]

def get_entries(filters):
	date_field = filters["doc_type"] == "Sales Order" and "transaction_date" or "posting_date"
	conditions_sperson = get_conditions(filters, date_field)[0]
	conditions_so = get_conditions(filters, date_field)[1]
	conditions_si = get_conditions(filters, date_field)[2]
	
	query = """SELECT sp.sales_person_name, spt.target_amount
		FROM `tabSales Person` sp, `tabTarget Detail` spt
		WHERE spt.parent = sp.name %s
		ORDER BY sp.sales_person_name""" % conditions_sperson
	
	query2 = """SELECT "", "", sum(so.net_total) from `tabSales Order` so WHERE so.docstatus = 1 %s """ % conditions_so
	
	so_sum = frappe.db.sql("""SELECT st.sales_person, sum(so.net_total*st.allocated_percentage/100)
	from `tabSales Order`  so, `tabSales Team` st
	WHERE so.docstatus = 1 AND st.parent = so.name AND st.parenttype = 'Sales Order' %s
	GROUP BY st.sales_person""" % conditions_so, as_list=1)
	
	si_sum = frappe.db.sql("""SELECT st.sales_person, sum(si.net_total*st.allocated_percentage/100)
	from `tabSales Invoice`  si, `tabSales Team` st
	WHERE si.docstatus = 1 AND st.parent = si.name AND st.parenttype = 'Sales Invoice' %s
	GROUP BY st.sales_person""" % conditions_si, as_list=1)
	
	ar_sum = frappe.db.sql("""SELECT st.sales_person, sum(si.outstanding_amount)
	from `tabSales Invoice`  si, `tabSales Team` st
	WHERE si.docstatus = 1 AND st.parent = si.name AND st.parenttype = 'Sales Invoice' %s
	GROUP BY st.sales_person""" % conditions_si, as_list=1)
	
	data = frappe.db.sql(query , as_list=1)
	#frappe.msgprint(ar_sum)
	
	for i in range(len(data)):
		for j in range(len(so_sum)):
			if data[i][0] == so_sum[j][0]:
				data[i].insert(2,so_sum[j][1])
	
	for i in range(len(data)):
		for j in range(len(si_sum)):
			if data[i][0] == si_sum[j][0]:
				data[i].insert(3,si_sum[j][1])
				
	for i in range(len(data)):
		for j in range(len(ar_sum)):
			if data[i][0] == ar_sum[j][0]:
				data[i].insert(4,ar_sum[j][1])
	
	return data
	
def get_conditions(filters, date_field):
	conditions_sperson = ""
	conditions_so = ""
	conditions_si = ""
	
	if filters.get("sales_person"):
		conditions_sperson += " AND sp.name = '%s'" % \
		filters["sales_person"].replace("'", "\'")
		
		conditions_so += " AND st.sales_person = '%s'" % \
		filters["sales_person"].replace("'", "\'")
		
		conditions_si += " AND st.sales_person = '%s'" % \
		filters["sales_person"].replace("'", "\'")
		
	if filters.get("fiscal_year"):
		conditions_sperson += " AND spt.fiscal_year = '%s'" % \
		filters["fiscal_year"].replace("'", "\'")
		
		conditions_so += " AND so.fiscal_year = '%s'" % \
		filters["fiscal_year"].replace("'", "\'")
		
		conditions_si += " AND si.fiscal_year = '%s'" % \
		filters["fiscal_year"].replace("'", "\'")
	
	#frappe.msgprint(conditions_sperson)
	return conditions_sperson, conditions_so, conditions_si