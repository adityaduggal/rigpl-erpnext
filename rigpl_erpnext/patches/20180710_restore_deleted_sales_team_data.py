# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.core.doctype.deleted_document.deleted_document import restore

def execute():
	deleted_steam = frappe.db.sql("""SELECT name FROM `tabDeleted Document` 
		WHERE deleted_doctype = 'Sales Team' AND restored = 0""", as_list=1)
	for delitem in deleted_steam:
		restore(delitem[0])
		print("Restored: " + delitem[0])