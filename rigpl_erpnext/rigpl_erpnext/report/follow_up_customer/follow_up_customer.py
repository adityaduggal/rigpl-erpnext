# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import datetime
from frappe.utils import flt, getdate, nowdate

def execute(filters=None):
	if not filters: filters = {}
	columns = get_columns(filters)
	data = get_data(filters)

	return columns, data

def get_columns(filters):
	if filters.get("details") == 1:
		return [
			"Customer:Link/Customer:150", "Contact:Link/Contact:120", "Mobile #::100", "Email::100",
			"Rating::100", "Territory:Link/Territory:100", "Last Comm Date:Date:100", "Next Date:Date:100", 
			"Medium::60", "Last Comm Details::200", "Link Comm:Link/Communication:120",
			"Comm Owner::120", "Comm Next Contact By::120", "Sales Person:Link/Sales Person:120"
		]
	else:
		return [
			"Customer:Link/Customer:150", "Contact:Link/Contact:120", "Mobile #::100", "Email::100",
			"Rating::100", "Territory:Link/Territory:100", "Requirement:Currency:100", 
			"SO Days:Int:50", "Comm Days:Int:50", "Last Comm Date:Date:100", "Next Date:Date:100", 
			"Sales Person:Link/Sales Person:120"
		]
	
def get_data(filters):
	data = []
	conditions, conditions_st, conditions_comm = get_conditions(filters)
	customers = get_customers(filters, conditions)
	contacts = get_contacts(customers)
	last_so = get_last_so(customers)
	comm_days = get_comm_days(customers)
	sales_person = get_sales_person(conditions_st, customers)
	comm, no_of_rows = get_comm(filters, conditions_comm)
	
	for cu in customers:
		if filters.get("details") == 1:
			pass
		else:
			no_of_rows = 1

		for i in range(no_of_rows):
			contact_count = 0
			row = [cu.name]
			
			#Get Contact Details (only one contact)
			for con in contacts:
				if con.customer == cu.name and contact_count == 0:
					if con.name:
						con.full_name = """<a href="#Form/Contact/%s">%s</a>""" \
						%(con.name, con.full_name)
					row += [con.full_name or "-", con.mobile_no or "-", con.email_id or "-"]
					contact_count += 1
			if contact_count == 0:
				row += ["-", "-", "-"]
			
			row += [cu.customer_rating or "-", cu.territory or "-"]
			if filters.get("details") == 1:
				row += ["", "", "", "", "", "", ""]
			else:
				row += [cu.requirement or 0]
				#Get Last SO Details 
				lso_check = 0
				for lsod in last_so:
					if lsod.customer == cu.name:
						row += [lsod.sodays]
						lso_check += 1
				if lso_check == 0:
					row += [36500]
				
				#Get Communication Details
				lcom_chieck = 0
				for lcomd in comm_days:
					if lcomd["customer"] == cu.name:
						row += [lcomd["com_days"], lcomd["last"], lcomd["next"]]
						lcom_chieck += 1
				if lcom_chieck == 0:
					row += [36500, '1900-01-01', "1900-01-01"]
			
			#Get Sales Person (Only One)
			sp_count = 0
			for sp in sales_person:
				if sp.customer == cu.name:
					row += [sp.sales_person]
					sp_count += 1
			if sp_count == 0:
				row += ["-"]
			data.append(row)
	
	if filters.get("details") == 1:
		indexes = [6,7,8,9,10,11,12]
		i = 0
		for c in comm:
			com = [c.communication_date, c.next_action_date, c.medium, c.content, c.name, c.owner, c.user]
			for ind in indexes:
				data[i][ind] = com[ind-6]
			i += 1

	return data

def get_customers(filters, conditions):
	if filters.get("rating"):
		pass
	else:
		conditions += " AND (cu.customer_rating != 'Black Listed' AND cu.customer_rating != 'Changed Business' OR cu.customer_rating IS NULL)"

	if filters.get("sales_person"):
		cust_lst = frappe.db.sql("""SELECT cu.name, cu.customer_rating, cu.territory, cu.requirement
		FROM `tabCustomer` cu, `tabSales Team` st
		WHERE cu.name = st.parent AND st.parenttype = 'Customer' %s""" %conditions, as_dict=1)
	else:
		cust_lst = frappe.db.sql("""SELECT cu.name, cu.customer_rating, cu.territory, cu.requirement
		FROM `tabCustomer` cu WHERE cu.docstatus = 0 %s""" \
			%conditions, as_dict=1)
	#frappe.throw(cust_lst)
	if cust_lst:
		pass
	else:
		frappe.throw("No Customers in given Criteria")
		
	return cust_lst

def get_contacts(customers):

	contacts = frappe.db.sql("""SELECT co.name, CONCAT(co.first_name, " ", IFNULL(co.last_name,"")) as full_name, 
	co.mobile_no, co.email_id, co.customer
	FROM `tabContact` co
	WHERE co.customer IN (%s) ORDER BY co.name """ %(", ".join(['%s']*len(customers))), \
		tuple([d.name for d in customers]), as_dict=1)
		
	return contacts

def get_last_so(customers):
	lso_days = frappe.db.sql("""SELECT so.customer, DATEDIFF(CURDATE(), MAX(so.transaction_date)) as sodays
		FROM `tabSales Order` so 
		WHERE so.docstatus != 2 AND so.transaction_date <= CURDATE() AND so.customer IN (%s)
		GROUP BY so.customer ORDER BY so.customer""" %(", ".join(['%s']*len(customers))), \
		tuple([d.name for d in customers]), as_dict=1)
	
	return lso_days

def get_comm_days(customers):
	comm_days = frappe.db.sql("""SELECT com.reference_name as customer, 
	DATEDIFF(CURDATE(), MAX(com.communication_date)) as com_days, 
	MAX(com.communication_date) as last,
	MAX(IFNULL(com.next_action_date, '1900-01-01')) as next
	FROM `tabCommunication` com 
	WHERE com.communication_type = 'Communication' AND
		com.reference_doctype = 'Customer' AND com.reference_name IN (%s)
	GROUP BY com.reference_name ORDER BY com.reference_name""" %(", ".join(['%s']*len(customers))), \
		tuple([d.name for d in customers]), as_dict=1)
	
	comm_days2 = frappe.db.sql("""SELECT com.timeline_name as customer, 
	DATEDIFF(CURDATE(), MAX(com.communication_date)) as com_days, 
	MAX(com.communication_date) as last,
	MAX(IFNULL(com.next_action_date, '1900-01-01')) as next
	FROM `tabCommunication` com 
	WHERE com.communication_type = 'Communication' AND
		com.timeline_doctype = 'Customer' AND com.timeline_name IN (%s)
	GROUP BY com.timeline_name ORDER BY com.timeline_name""" %(", ".join(['%s']*len(customers))), \
		tuple([d.name for d in customers]), as_dict=1)
	result = []
	temp = {}
	for cust in customers:
		if any(d["customer"] == cust.name for d in comm_days):
			for ref in comm_days:
				if cust.name == ref.customer:
					result.append(ref.copy())
		else:
			temp["customer"] = cust.name
			temp["com_days"] = 36500
			temp["last"] = '1900-01-01'
			temp["next"] = '1900-01-01'
			result.append(temp.copy())

	for cust in result:
		if (any(d["customer"] == cust["customer"] for d in comm_days2)):
			for time in comm_days2:
				if time.customer == cust["customer"]:
					if getdate(time.last) > getdate(cust["last"]):
						result[result.index(cust)] = time
	return result

def get_comm(filters, conditions_comm):
	cust = filters.get("customer")
	query = """SELECT com.communication_date, com.next_action_date,
	IFNULL(com.communication_medium, "Comment") as medium, com.content, com.name, com.owner, com.user, 
	com.reference_name as ref_cust, com.timeline_name as time_cust
	FROM `tabCommunication` com 
	WHERE ((com.communication_type = 'Communication' AND
	(com.reference_doctype = 'Customer' OR com.timeline_doctype = 'Customer') AND
	(com.reference_name = '%s' OR com.timeline_name = '%s')) OR (com.communication_type = 'Comment'
	AND com.reference_doctype = 'Customer' AND com.reference_name = '%s' AND 
	com.comment_type = 'Comment')) %s
	ORDER BY com.communication_date DESC""" %(cust, cust, cust,conditions_comm)

	comm = frappe.db.sql(query, as_dict = 1)
	
	no_of_rows = len(comm)
	
	return comm, no_of_rows
	
def get_sales_person(conditions_st, customers):
	sales_person = frappe.db.sql("""SELECT st.parent as customer, st.sales_person
	FROM `tabSales Team` st WHERE st.parenttype = 'Customer' {condition}
	AND st.parent IN (%s)""".format(condition=conditions_st) %(", ".join(['%s']*len(customers))), \
		tuple([d.name for d in customers]), as_dict=1)
	
	return sales_person
	
def get_conditions(filters):
	conditions = ""
	conditions_st = ""
	conditions_comm = ""
	
	if filters.get("from_date"):
		conditions_comm = " AND com.communication_date >= '%s'" %filters["from_date"]
	
	if filters.get("details") == 1:
		if filters.get("customer"):
			pass
		else:
			frappe.throw("For Detailed Report Customer Selection is Mandatory")
			
	if filters.get("customer"):
		conditions += " AND cu.name = '%s'" %filters["customer"]
		
	if filters.get("territory"):
		territory = frappe.get_doc("Territory", filters["territory"])
		if territory.is_group == "Yes" or territory.is_group == 1:
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
			conditions += " AND cu.territory = '%s'" % filters["territory"]

	if filters.get("rating"):
		conditions += " AND cu.customer_rating = '%s'" % filters["rating"]

	if filters.get("sales_person"):
		sales_person = frappe.get_doc("Sales Person", filters["sales_person"])
		if sales_person.is_group == "Yes" or sales_person.is_group == 1:
			child_sp = frappe.db.sql("""SELECT name FROM `tabSales Person`
				WHERE lft >= %s AND rgt <= %s""" %(sales_person.lft, sales_person.rgt), as_list = 1)
				
			for i in child_sp:
				if child_sp[0] == i:
					conditions += " AND (st.sales_person = '%s'" %i[0]
					conditions_st += " AND (st.sales_person = '%s'" %i[0]
					
				elif child_sp[len(child_sp)-1] == i:
					conditions += " OR st.sales_person = '%s')" %i[0]
					conditions_st += " OR st.sales_person = '%s')" %i[0]
					
				else:
					conditions += " OR st.sales_person = '%s'" %i[0]
					conditions_st += " OR st.sales_person = '%s'" %i[0]
		else:
			conditions += " AND st.sales_person = '%s'" % filters["sales_person"]
			conditions_st += " AND st.sales_person = '%s'" % filters["sales_person"]

	return conditions, conditions_st, conditions_comm