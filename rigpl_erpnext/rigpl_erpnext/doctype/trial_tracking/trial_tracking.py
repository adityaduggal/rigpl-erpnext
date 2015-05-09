# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class TrialTracking(Document):
	def validate(doc):
		if doc.target_life:
			if doc.unit_of_tool_life is "":
				frappe.msgprint("Please select the Unit for Tool Life",raise_exception = 1)
		
		#Unit of Hardness validation with Hardness
		if doc.hardness:
			if doc.unit_of_hardness is "":
				frappe.msgprint("Please select unit of Hardness", raise_exception=1)
		if doc.feed:
			min_feed = 30
			max_feed = 5000
			if doc.feed < min_feed or doc.feed > max_feed:
				frappe.msgprint('{0}{1}{2}{3}'.format("Feed is in mm/min and hence cannot be less than ",min_feed, " or higher than ", max_feed), raise_exception=1)
		
		if doc.status in ("Material Ready", "Awaited", "Failed", "Passed"):
			sod = frappe.get_doc("Sales Order Item", doc.prevdoc_detail_docname)
			if sod.delivered_qty is None:
				sod.delivered_qty = 0
			if (sod.qty - sod.delivered_qty) > 0:
				frappe.msgprint("Material not fully delivered hence cannot set this status", raise_exception=1)
		
		if doc.status in ("Awaited", "Failed", "Passed"):
			if doc.competitor_name is "" or doc.material_to_machine is "":
				frappe.msgprint("Cannot Set this status without filling Competitor Name and Material to Machine", raise_exception=1)
				
		if doc.status in ("Failed", "Passed"):
			if doc.target_life is None:
				frappe.msgprint("Cannot Set this status without filling Target Life", raise_exception=1)
		
		if doc.status == "Passed":
			if doc.target_life > doc.life_of_tool:
				frappe.msgprint("In Passed trials the target life has to be LESS than Actual Life of Tool achieved", raise_exception=1)
		
		if doc.status == "Failed":
			if doc.target_life <= doc.life_of_tool:
				frappe.msgprint("In Failed trials the target life has to be MORE than Actual Life of Tool achieved", raise_exception=1)
				
		#Check the SODetail Number as Unique
		if doc.prevdoc_detail_docname:
			sod_list = frappe.db.sql("""select prevdoc_detail_docname from `tabTrial Tracking` 
				WHERE prevdoc_detail_docname=%s""", doc.prevdoc_detail_docname)
			if len(sod_list)>1:
				frappe.msgprint('{0}{1}'.format("SO Detail No already exists ", doc.prevdoc_detail_docname), raise_exception=1)
		
	def on_submit(doc):
		if doc.status not in ("Failed", "Passed"):
			frappe.msgprint("Update the status to Passed or Failed before Submitting", raise_exception = 1)