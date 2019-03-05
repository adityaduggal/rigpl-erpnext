from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils import getdate, nowdate, flt, cstr

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_dn_entries(filters)

	return columns, data

def get_columns(filters):
	if filters.get("summary") != 1:
		return [
			"DN_No:Link/Delivery Note:120", "Customer:Link/Customer:200", "Date:Date:100",
			"Item_Code:Link/Item:130","Description::350", "DN_Qty:Float:70",
			"DN_Price:Currency:70", "DN Amount:Currency:80", "SO_No:Link/Sales Order:140",
			"SO_Date:Date:80", "Trial::60"
		]
	else:
		return[
			"Customer:Link/Customer:200", "Payment Terms::250", "Rating::60",
			"Total DN#:Int:80", "No of Items:Int:80",
			"Earliest DN Date:Date:80", "Total Qty:Int:80", "Total Value:Currency:150"
		]

def get_dn_entries(filters):
	if filters.get("summary") != 1:
		conditions, si_cond, conditions_cu = get_conditions(filters)
		

		query = """SELECT dn.name as dn, dn.customer as cust,
		dn.posting_date as dn_posting, 
		dni.item_code as dn_itemcode, dni.description as dn_desc, dni.qty as dn_qty, 
		dni.base_rate, dni.base_amount, dni.against_sales_order, so.transaction_date,
	    
	    IF(so.track_trial = 1, "Yes", "No")
	     
		
		FROM `tabDelivery Note` dn, `tabDelivery Note Item` dni, `tabSales Order` so,
		 `tabCustomer` cu

		WHERE dn.docstatus = 1 AND so.docstatus = 1 AND dn.customer = cu.name %s
			AND so.name = dni.against_sales_order
	    	AND dn.name = dni.parent
	    	AND (dni.qty - ifnull((select sum(sid.qty) FROM `tabSales Invoice Item` sid, 
				`tabSales Invoice` si
	        	WHERE sid.delivery_note = dn.name
					AND sid.parent = si.name
					AND sid.qty > 0
					AND sid.dn_detail = dni.name %s), 0)>=0.01) %s
		
		ORDER BY dn.posting_date asc """ % (conditions_cu, si_cond, conditions)

		dn = frappe.db.sql(query ,as_list=1)
	else:
		query = """SELECT dn.customer, cu.payment_terms, cu.customer_rating,
			COUNT(DISTINCT(dn.name)), COUNT(dni.item_code), dn.posting_date,
			SUM(dni.qty), SUM(dni.base_amount)
			FROM `tabDelivery Note` dn, `tabDelivery Note Item` dni,
				`tabCustomer` cu
			WHERE dn.docstatus = 1 AND dni.parent = dn.name 
				AND cu.name = dn.customer 
				AND (dni.qty - ifnull((select sum(sid.qty) FROM `tabSales Invoice Item` sid, 
				`tabSales Invoice` si
	        	WHERE sid.delivery_note = dn.name
					AND sid.parent = si.name
					AND sid.qty > 0
					AND sid.dn_detail = dni.name AND si.docstatus = 1), 0)>=0.01)
			GROUP BY dn.customer"""
		dn = frappe.db.sql(query, as_list=1)

	return dn

def get_conditions(filters):
	conditions = ""
	si_cond = ""
	conditions_cu = ""

	if filters.get("customer"):
		conditions += " and dn.customer = '%s'" % filters["customer"]
		conditions_cu += " AND cu.name = '%s'" % filters["customer"]

	if filters.get("from_date"):
		if filters.get("to_date"):
			if getdate(filters.get("from_date"))>getdate(filters.get("to_date")):
				frappe.msgprint("From Date cannot be greater than To Date", raise_exception=1)
		conditions += " and dn.posting_date >= '%s'" % filters["from_date"]
		si_cond += " AND si.posting_date >= '%s'" % filters ["from_date"]

	if filters.get("to_date"):
		conditions += " and dn.posting_date <= '%s'" % filters["to_date"]
		si_cond += " AND si.posting_date <= '%s'" % filters ["to_date"]

	if filters.get("territory"):
		territory = frappe.get_doc("Territory", filters["territory"])
		if territory.is_group == 1:
			child_territories = frappe.db.sql("""SELECT name FROM `tabTerritory` 
				WHERE lft >= %s AND rgt <= %s""" %(territory.lft, territory.rgt), as_list = 1)
			for i in child_territories:
				if child_territories[0] == i:
					conditions_cu += " AND (cu.territory = '%s'" %i[0]
				elif child_territories[len(child_territories)-1] == i:
					conditions_cu += " OR cu.territory = '%s')" %i[0]
				else:
					conditions_cu += " OR cu.territory = '%s'" %i[0]
		else:
			conditions_cu += " and cu.territory = '%s'" % filters["territory"]

	#if filters.get("sales_person"):
	#	conditions += "AND st.sales_person = '%s'" % filters["sales_person"]
		
	if filters.get("draft")== 1:
		si_cond += " and si.docstatus != 2"
	else:
		si_cond += " and si.docstatus = 1"
	
	return conditions, si_cond, conditions_cu
