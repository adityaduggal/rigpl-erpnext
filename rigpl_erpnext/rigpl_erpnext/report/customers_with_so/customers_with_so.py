from __future__ import unicode_literals
import frappe
from frappe.utils import flt, getdate, nowdate

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_so_data(filters)

	return columns, data

def get_columns():
	return [
		"Customer ID:Link/Customer:150", "Territory:Link/Territory:150", "Total SO Val:Currency:120",
		"Sale Considered:Currency:120", "# of SO:Int:80", "Avg SO Value:Currency:120",
		"Last SO Date:Date:100", "#Days Since Last SO:Int:80", "Sales Partner:Link/Sales Partner:100", 
		"Sales Person:Link/Sales Person:100", "Allocated %:Float:50"
	]

def get_so_data(filters):
	conditions = get_conditions(filters)
	conditions_cust, conditions_sp = get_conditions_cust(filters)

	if (filters.get("from_date")):
		diff = (getdate(filters.get("to_date")) - getdate(filters.get("from_date"))).days
		if diff < 0:
			frappe.msgprint("From Date has to be less than To Date", raise_exception=1)
	else:
		frappe.msgprint("Select from date first",raise_exception =1)

	data = frappe.db.sql("""SELECT so.customer, SUM(so.net_total),
	SUM(if(so.status = "Closed", so.net_total * so.per_delivered/100, so.net_total)), COUNT(DISTINCT so.name),
	SUM(if(so.status = "Closed", so.net_total * so.per_delivered/100, so.net_total))/COUNT(DISTINCT so.name)
	FROM `tabSales Order` so
	WHERE so.docstatus = 1 %s
	GROUP BY so.customer
	ORDER BY so.customer""" %(conditions) , as_list=1)
	
	
	cust_query = """SELECT cu.name, cu.territory, IFNULL(cu.default_sales_partner, "-"), 
		IFNULL(st.sales_person, "-"), IFNULL(st.allocated_percentage,0)
		FROM `tabCustomer` cu
			LEFT JOIN `tabSales Team` st ON st.parent = cu.name AND st.parenttype = 'Customer'
		WHERE 
			cu.docstatus = 0 %s %s
		ORDER BY cu.name""" %(conditions_sp, conditions_cust)

	cust_tbl = frappe.db.sql(cust_query, as_list=1)

	last_so = frappe.db.sql("""SELECT so.customer, MAX(so.transaction_date), so.name
	FROM `tabSales Order` so WHERE so.docstatus = 1 GROUP BY so.customer""", as_list=1)


	for i in cust_tbl:
		#Below loop would add the Territory to the data
		if any (i[0] in s for s in data):
			for j in data:
				if i[0] == j[0]:
					if j[1] is None:
						frappe.msgprint(j[1])
						i.insert(2,None)
					else:
						i.insert(2,j[1])

					if j[2] is None:
						i.insert(3,None)
					else:
						i.insert(3,j[2])

					if j[3] is None:
						i.insert(4,None)
					else:
						i.insert(4,j[3])

					if j[4] is None:
						i.insert(5,None)
					else:
						i.insert(5,j[4])
		else:
			i.insert(2,None)
			i.insert(3,None)
			i.insert(4,None)
			i.insert(5,None)

		if any (i[0] in s for s in last_so):
			for j in last_so:
				if i[0] == j[0]:
					if j[1] is None:
						i.insert(6,None)
					else:
						i.insert(6,j[1])
		else:
			i.insert(6,None)

		if not i[6]:
			i.insert(7,None)
		else:
			days_last_so = (getdate(filters.get("to_date")) - getdate(i[6])).days
			i.insert(7,days_last_so)

	return cust_tbl



def get_conditions(filters):
	conditions = ""

	if filters.get("from_date"):
		conditions += " AND so.transaction_date >= '%s'" % filters["from_date"]

	if filters.get("to_date"):
		conditions += " AND so.transaction_date <= '%s'" % filters["to_date"]
	return conditions

def get_conditions_cust(filters):
	conditions_cust = ""
	conditions_sp = ""

	if filters.get("customer"):
		conditions_cust += " AND cu.name = '%s'" % filters["customer"]
	
	if filters.get("sales_partner"):
		conditions_cust += " AND cu.default_sales_partner = '%s'" % filters["sales_partner"]
	
	if filters.get("territory"):
		territory = frappe.get_doc("Territory", filters["territory"])
		if territory.is_group == "Yes":
			child_territories = frappe.db.sql("""SELECT name FROM `tabTerritory` 
				WHERE lft >= %s AND rgt <= %s""" %(territory.lft, territory.rgt), as_list = 1)
			for i in child_territories:
				if child_territories[0] == i:
					conditions_cust += " AND (cu.territory = '%s'" %i[0]
				elif child_territories[len(child_territories)-1] == i:
					conditions_cust += " OR cu.territory = '%s')" %i[0]
				else:
					conditions_cust += " OR cu.territory = '%s'" %i[0]
		else:
			conditions_cust += " AND cu.territory = '%s'" % filters["territory"]
			
	if filters.get("sales_person"):
		sales_person = frappe.get_doc("Sales Person", filters["sales_person"])
		if sales_person.is_group == "Yes":
			child_sp = frappe.db.sql("""SELECT name FROM `tabSales Person`
				WHERE lft >= %s AND rgt <= %s""" %(sales_person.lft, sales_person.rgt), as_list = 1)
				
			for i in child_sp:
				if child_sp[0] == i:
					conditions_sp += " AND (st.sales_person = '%s'" %i[0]
				elif child_sp[len(child_sp)-1] == i:
					conditions_sp += " OR st.sales_person = '%s')" %i[0]
				else:
					conditions_sp += " OR st.sales_person = '%s'" %i[0]
		else:
			conditions_sp += " AND st.sales_person = '%s'" % filters["sales_person"]

	return conditions_cust, conditions_sp

