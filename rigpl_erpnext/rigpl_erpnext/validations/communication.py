# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from rigpl_erpnext.rigpl_erpnext.doctype.daily_call.daily_call import check_date_time_diff

def validate(doc, method):
	in_daily_call = frappe.db.sql("""SELECT name, parent FROM `tabDaily Call Details` 
		WHERE communication = '%s'"""%(doc.name), as_list=1)
	if in_daily_call:
		dcr_details = frappe.get_doc("Daily Call Details", in_daily_call[0][0])
		dcr = frappe.get_doc("Daily Call", in_daily_call[0][1])
	if doc.follow_up == 1:
		if not doc.next_action_date:
			frappe.throw('Next Action Date is Mandatory for Follow Up Communication')
		else:
			check_date_time_diff(doc.next_action_date, hours_diff=1, \
				type_of_check= 'time', name_of_field = 'Next Action')
	if dcr_details.details != doc.content:
		doc.content = dcr_details.details
	if dcr_details.document != doc.reference_doctype:
		doc.reference_doctype = dcr_details.document
	if dcr_details.document_name != doc.reference_name:
		doc.reference_name = dcr_details.document_name
	if dcr_details.type_of_communication != doc.communication_medium:
		doc.communication_medium = dcr_details.type_of_communication
	if dcr_details.communication_date != doc.communication_date:
		doc.communication_date = dcr_details.communication_date