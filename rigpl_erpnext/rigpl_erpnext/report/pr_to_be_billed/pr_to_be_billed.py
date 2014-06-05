from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils import getdate, nowdate, flt, cstr

def execute(filters=None):
	if not filters: filters = {}
	
	columns = get_columns()
	data = get_pr_entries(filters)
		
	return columns, data
	
def get_columns():
	

	return [
		"PR #:Link/Purchase Receipt:120", "Supplier:Link/Supplier:200" ,"Date:Date:100", 
		"Item Code:Link/Item:130","Description::350", "PR Qty:Float/2:70", 
		"PR Price:Currency:70", "PR Amount:Currency:80", "PO #:Link/Purchase Order:140",
		"Unbilled Qty:Float/3:80", "Unbilled Amount:Currency:80"
	]
	
def get_pr_entries(filters):
	conditions = get_conditions(filters)
	
	pr = frappe.db.sql("""select
    pr.name, pr.supplier, pr.posting_date,
	pri.item_code, pri.description, pri.qty, pri.import_rate,
	pri.import_amount, pri.prevdoc_docname,
	(pri.qty - ifnull((select sum(pid.qty) from `tabPurchase Invoice Item` pid
	    where pid.purchase_receipt = pr.name and
	    pid.pr_detail = pri.name), 0)),
	(pri.amount - ifnull((select sum(pid.amount) from `tabPurchase Invoice Item` pid 
        where pid.purchase_receipt = pr.name and
        pid.pr_detail = pri.name), 0)),
	pri.item_name, pri.description
	from `tabPurchase Receipt` pr, `tabPurchase Receipt Item` pri
	where
    pr.docstatus = 1
    AND pr.name = pri.parent
    AND (pri.qty - ifnull((select sum(pid.qty) from `tabPurchase Invoice Item` pid
        where pid.purchase_receipt = pr.name and
        pid.pr_detail = pri.name), 0)>=1)
	AND (pri.amount - ifnull((select sum(pid.amount) from `tabPurchase Invoice Item` pid 
        where pid.purchase_receipt = pr.name and
        pid.pr_detail = pri.name), 0)>=1) %s
	order by pr.posting_date asc """ % conditions ,as_list=1)
	
	po = frappe.db.sql (""" SELECT po.name
		FROM `tabPurchase Order` po
		WHERE po.docstatus = 1""")
	
	#for i in range(0,len(pr)):
	#	for j in range(0,len(po)):
	#		if pr[i][8] == po[j][0]:
	#			pr[i].insert (10,po[j][1])
	
	#si = frappe.db.sql("""SELECT sid.dn_detail, sum(sid.qty), sum(sid.amount)
	#	FROM `tabSales Invoice` si, `tabSales Invoice Item` sid
	#	WHERE sid.parent = si.name
	#	AND si.docstatus = 1
	#	AND sid.dn_detail IS NOT NULL
	#	GROUP BY sid.dn_detail
	#	ORDER BY sid.dn_detail""", as_list=1)

	return pr
	
def get_conditions(filters):
	conditions = ""
	#cond_dnq = ""
	
	if filters.get("supplier"):
		conditions += " and pr.supplier = '%s'" % filters["supplier"]
		#cond_dnq += " and pr.supplier = '%s'" % filters["supplier"]

	if filters.get("from_date"):
		if filters.get("to_date"):
			if getdate(filters.get("from_date"))>getdate(filters.get("to_date")):
				frappe.msgprint("From Date cannot be greater than To Date", raise_exception=1)
		conditions += " and pr.posting_date >= '%s'" % filters["from_date"]
	
	if filters.get("to_date"):
		conditions += " and pr.posting_date <= '%s'" % filters["to_date"]
	return conditions