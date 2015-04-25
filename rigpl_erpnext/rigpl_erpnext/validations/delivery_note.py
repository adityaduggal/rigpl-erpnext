# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def on_submit(doc, method):
	for dnd in doc.get("delivery_note_details"):
		tt = frappe.get_doc("Trial Tracking", dnd.prevdoc_detail_docname)
		if tt:
			frappe.msgprint('{0}{1}'.format("Please update Trial Tracking No: ", dnd.prevdoc_detail_docname))