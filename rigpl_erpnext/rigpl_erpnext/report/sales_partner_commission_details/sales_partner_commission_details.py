# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_entries(filters)

	return columns, data

def get_columns(filters):
	if not filters.get("doc_type"):
		msgprint(_("Please select the document type first"), raise_exception=1)

	return [filters["doc_type"] + ":Link/" + filters["doc_type"] + ":140", 
		"Customer:Link/Customer:140", "Territory:Link/Territory:100", "Posting Date:Date:100", 
		"Item Code:Link/Item:120", "Description::300", "Qty:Float:80", 
		"Rate:Currency:80", "List Price:Currency:60", "Discount:Float:60", "Amount:Currency:100", 
		"Sales Partner:Link/Sales Partner:140", "Commission %:Float:80", 
		"Comm Amt:Currency:100"]

def get_entries(filters):
	date_field = filters["doc_type"] == "Sales Order" and "transaction_date" or "posting_date"
	conditions = get_conditions(filters, date_field)
	if filters.get("based_on")=="Transaction":
		data = frappe.db.sql("""select dt.name, dt.customer, dt.territory, dt.%s, 
			dt_item.item_code, dt_item.description, dt_item.qty, dt_item.base_net_rate, 
			dt_item.base_price_list_rate, dt_item.discount_percentage, 
			dt_item.base_net_amount, dt.sales_partner, 
			dt.commission_rate, dt.commission_rate*dt_item.base_net_amount/100
			from `tab%s` dt, `tab%s Item` dt_item
			where dt.name = dt_item.parent and dt.docstatus = 1 %s order by dt.customer, dt.name desc""" % 
			(date_field, filters["doc_type"], filters["doc_type"],conditions), as_list=1)
	elif filters.get("based_on")=="Master":
		#msgprint(_("WIP2"), raise_exception=1)
		data = frappe.db.sql("""select dt.name, dt.customer, cu.territory, dt.%s, 
			dt_item.item_code, dt_item.description, dt_item.qty, dt_item.base_net_rate, 
			dt_item.base_price_list_rate, dt_item.discount_percentage, 
			dt_item.base_net_amount, cu.default_sales_partner, 
			cu.default_commission_rate, cu.default_commission_rate*dt_item.base_net_amount/100
			from `tab%s` dt, `tab%s Item` dt_item, `tabCustomer` cu 
			WHERE dt.customer = cu.name
			AND dt.name = dt_item.parent 
			AND dt.docstatus = 1 %s order by dt.customer, dt.name desc""" % 
			(date_field, filters["doc_type"], filters["doc_type"],conditions), as_list=1)
	
	for i in range(0,len(data)):
		if data[i][11] is None:
			data[i][11] = "-"
	
	return data

def get_conditions(filters, date_field):
	conditions = ""

	if filters.get("customer"): conditions += " and dt.customer = '%s'" % \
		filters["customer"].replace("'", "\'")
	
	if filters.get("based_on") == "Transaction":
		if filters.get("territory"):
			territory = frappe.get_doc("Territory", filters["territory"])
			if territory.is_group == 1:
				child_territories = frappe.db.sql("""SELECT name FROM `tabTerritory` 
					WHERE lft >= %s AND rgt <= %s""" %(territory.lft, territory.rgt), as_list = 1)
				for i in child_territories:
					if child_territories[0] == i:
						conditions += " AND (dt.territory = '%s'" %i[0]
					elif child_territories[len(child_territories)-1] == i:
						conditions += " OR dt.territory = '%s')" %i[0]
					else:
						conditions += " OR dt.territory = '%s'" %i[0]
			else:
				conditions += " and dt.territory = '%s'" % filters["territory"]

		if filters.get("sales_partner"): conditions += " and dt.sales_partner = '%s'" % \
		 	filters["sales_partner"].replace("'", "\'")
	
	elif filters.get("based_on") == "Master":
		if filters.get("territory"):
			territory = frappe.get_doc("Territory", filters["territory"])
			if territory.is_group == 1:
				child_territories = frappe.db.sql("""SELECT name FROM `tabTerritory` 
					WHERE lft >= %s AND rgt <= %s""" %(territory.lft, territory.rgt), as_list = 1)
				for i in child_territories:
					if child_territories[0] == i:
						conditions += " AND (cu.territory = '%s'" %i[0]
					elif child_territories[len(child_territories)-1] == i:
						conditions += " OR cu.territory = '%s')" %i[0]
					else:
						conditions += " OR cu.territory = '%s'" %i[0]
			else:
				conditions += " and cu.territory = '%s'" % filters["territory"]

		if filters.get("sales_partner"): conditions += " and cu.default_sales_partner = '%s'" % \
		 	filters["sales_partner"].replace("'", "\'")
	else:
		msgprint(_("Please select the whether commission to be shown \
			from Customer Master or from Transaction first"), raise_exception=1)
		

	if filters.get("from_date"): conditions += " and dt.%s >= '%s'" % \
		(date_field, filters["from_date"])
	if filters.get("to_date"): conditions += " and dt.%s <= '%s'" % (date_field, filters["to_date"])



	return conditions

