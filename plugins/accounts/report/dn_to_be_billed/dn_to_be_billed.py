from __future__ import unicode_literals
import webnotes
from webnotes import msgprint, _
from webnotes.utils import getdate, nowdate, flt, cstr

def execute(filters=None):
	if not filters: filters = {}
	
	columns = get_columns()
	data = get_dn_entries(filters)
		
	return columns, data
	
def get_columns():
	

	return [
		"DN #:Link/Delivery Note:120", "Customer:Link/Customer:200" ,"Date:Date:100", 
		"Item Code:Link/Item:130","Description::350", "DN Qty:Float/2:70", 
		"DN Price:Currency:70", "DN Amount:Currency:80", "SO #:Link/Sales Order:140",
		"Unbilled Qty:Currency:80", "Unbilled Amount:Currency:80", "Order Type::150"
	]
	
def get_dn_entries(filters):
	conditions = get_conditions(filters)
	
	dn = webnotes.conn.sql("""select
    dn.name, dn.customer, dn.posting_date,
	dni.item_code, dni.description, dni.qty, dni.export_rate,
	dni.export_amount, dni.prevdoc_docname,
	(dni.qty - ifnull((select sum(sid.qty) from `tabSales Invoice Item` sid
	    where sid.delivery_note = dn.name and
	    sid.dn_detail = dni.name), 0)),
	(dni.amount - ifnull((select sum(sid.amount) from `tabSales Invoice Item` sid 
        where sid.delivery_note = dn.name and
        sid.dn_detail = dni.name), 0)),
	dni.item_name, dni.description
	from `tabDelivery Note` dn, `tabDelivery Note Item` dni
	where
    dn.docstatus = 1
    AND dn.name = dni.parent
    AND (dni.qty - ifnull((select sum(sid.qty) from `tabSales Invoice Item` sid
        where sid.delivery_note = dn.name and
        sid.dn_detail = dni.name), 0)>=1)
	AND (dni.amount - ifnull((select sum(sid.amount) from `tabSales Invoice Item` sid 
        where sid.delivery_note = dn.name and
        sid.dn_detail = dni.name), 0)>=1) %s
	order by dn.posting_date asc """ % conditions ,as_list=1)
	
	so = webnotes.conn.sql (""" SELECT so.name, so.order_type
		FROM `tabSales Order` so
		WHERE so.docstatus = 1""")
	
	for i in range(0,len(dn)):
		for j in range(0,len(so)):
			if dn[i][8] == so[j][0]:
				dn[i].insert (11,so[j][1])
	
	#si = webnotes.conn.sql("""SELECT sid.dn_detail, sum(sid.qty), sum(sid.amount)
	#	FROM `tabSales Invoice` si, `tabSales Invoice Item` sid
	#	WHERE sid.parent = si.name
	#	AND si.docstatus = 1
	#	AND sid.dn_detail IS NOT NULL
	#	GROUP BY sid.dn_detail
	#	ORDER BY sid.dn_detail""", as_list=1)

	return dn
	
def get_conditions(filters):
	conditions = ""
	#cond_dnq = ""
	
	if filters.get("customer"):
		conditions += " and dn.customer = '%s'" % filters["customer"]
		#cond_dnq += " and dn.customer = '%s'" % filters["customer"]

	if filters.get("from_date"):
		if filters.get("to_date"):
			if getdate(filters.get("from_date"))>getdate(filters.get("to_date")):
				webnotes.msgprint("From Date cannot be greater than To Date", raise_exception=1)
		conditions += " and dn.posting_date >= '%s'" % filters["from_date"]
	
	if filters.get("to_date"):
		conditions += " and dn.posting_date <= '%s'" % filters["to_date"]
	return conditions