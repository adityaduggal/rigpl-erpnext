# -*- coding: utf-8 -*-
import frappe
from frappe.utils import flt

def execute():
	cust_list = frappe.db.sql("""SELECT cu.name FROM `tabCustomer` cu 
		WHERE cu.name NOT IN (SELECT parent FROM `tabSales Team` WHERE parenttype = 'Customer'
		AND parent = cu.name)""", as_list=1)
	if cust_list:
		for d in range(len(cust_list)):
			new_st = frappe.get_doc({
					"doctype": "Sales Team",
					"parent": cust_list[d][0],
					"parenttype": 'Customer',
					"allocated_percentage": 100,
					"sales_person": "Rohit Duggal",
					"idx": 1,
					"parentfield": 'sales_team'
					})
			new_st.insert(ignore_permissions=True)
			print "For Customer:", cust_list[d][0], "inserted New Sales Person Rohit Duggal"
