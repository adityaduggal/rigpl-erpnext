from __future__ import unicode_literals
import frappe
from frappe import msgprint

def execute():
	tt_without_invoice = frappe.db.sql("""SELECT name from `tabTrial Tracking` WHERE invoice_no is NULL""", as_list=1)
	for i in tt_without_invoice:
		tt = frappe.get_doc("Trial Tracking", i[0])
		query = """SELECT si.name FROM `tabSales Invoice` si, `tabSales Invoice Item` sid 
		WHERE si.docstatus = 1 AND sid.parent = si.name AND sid.so_detail = '%s' 
		ORDER BY si.name""" % tt.prevdoc_detail_docname
		
		sid = frappe.db.sql(query, as_list=1)
		
		if sid:
			frappe.db.set_value("Trial Tracking", i[0], "invoice_no", sid[0][0])
			print "Trial Tracking Number ", tt.name, "updated with Sales Invoice Number ", sid[0][0]