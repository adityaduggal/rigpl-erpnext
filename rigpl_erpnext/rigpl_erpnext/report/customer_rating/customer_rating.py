# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import getdate, add_days
from ...scheduled_tasks.customer_rating import build_customer_rating

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	return [
		"Customer:Link/Customer:200", "Territory:Link/Territory:150", "Group:Link/Customer Group:100",
		"Avg Pmt Days:Int:50", "Pmt Factor:Int:50", "Age Factor:Int:50", "Period:Int:50", "Since:Int:50",
		"Total SO:Currency:100", "# SO:Int:80", "Total Sales:Currency:100", "# SI:Int:50",
		"Factor:Int:100", "Total Rating:Int:100", "# Monthly Orders:Int:50", "Calculated Rating:Int:80",
		"Actual Rating:Int:80"
	]

def get_data(filters):
	to_date = getdate(filters.get("to_date"))
	years = filters.get("years")
	from_date = add_days(to_date, years*(-365))
	period = (to_date - from_date).days
	fov = filters.get("first_order")
	conditions = get_conditions(filters)
	cust_list = frappe.db.sql("""SELECT cu.name, cu.territory, cu.customer_group 
	FROM `tabCustomer` cu WHERE cu.docstatus = 0 %s""" % conditions, as_dict=1)
	customers_rated = []
	for cust in cust_list:
		cust_dict = build_customer_rating(cust_dict=cust, from_date=from_date, to_date=to_date, fov=fov, days=years*365)
		cust_dict["territory"] = cust.territory
		cust_dict["customer_group"] = cust.customer_group
		cust_dict["period"] = period
		customers_rated.append(cust_dict.copy())
	customers_rated = sorted(customers_rated, key=lambda i: (i["total_rating"]))
	data = []
	for cu in customers_rated:
		cust_doc = frappe.get_doc("Customer", cu.name)
		row = [cu.name, cu.territory, cu.customer_group, cu.avg_pmt_days, cu.pmt_factor, cu.age_factor,
			   cu.period, cu.days_since, cu.total_orders, cu.total_so, cu.total_sales, cu.total_invoices,
			   cu.factor, cu.total_rating, cu.avg_monthly_orders, cu.customer_rating, cust_doc.customer_rating]
		data.append(row)
	# data = sorted(data, key=lambda i:(i["total_rating"]))
	return data



def get_conditions(filters):
	cond = ""
	if filters.get("customer"):
		cond += " AND cu.name = '%s'" % filters["customer"]

	if filters.get("territory"):
		territory = frappe.get_doc("Territory", filters["territory"])
		if territory.is_group == 1:
			child_territories = frappe.db.sql("""SELECT name FROM `tabTerritory`  WHERE lft >= %s AND rgt <= %s""" %
											  (territory.lft, territory.rgt), as_list=1)
			for i in child_territories:
				if child_territories[0] == i:
					cond += " AND (cu.territory = '%s'" % i[0]
				elif child_territories[len(child_territories) - 1] == i:
					cond += " OR cu.territory = '%s')" % i[0]
				else:
					cond += " OR cu.territory = '%s'" % i[0]
		else:
			cond += " AND cu.territory = '%s'" % filters["territory"]

	if filters.get("customer_group"):
		cg = frappe.get_doc("Customer Group", filters["customer_group"])
		if cg.is_group == 1:
			child_cgs = frappe.db.sql("""SELECT name FROM `tabCustomer Group` WHERE lft >= %s AND rgt <= %s""" %
									  (cg.lft, cg.rgt), as_list=1)
			for i in child_cgs:
				if child_cgs[0] == i:
					cond += " AND (cu.customer_group = '%s'" % i[0]
				elif child_cgs[len(child_cgs) - 1] == i:
					cond += " OR cu.customer_group = '%s')" % i[0]
				else:
					cond += " OR cu.customer_group = '%s'" % i[0]
		else:
			cond += " AND cu.customer_group = '%s'" % filters["customer_group"]

	return cond
