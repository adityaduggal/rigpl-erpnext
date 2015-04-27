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
			if doc.feed <= 50 or doc.feed >= 5000:
				frappe.msgprint("Feed is in mm/min and hence cannot be less than 50 or higher than 500", raise_exception=1)
		
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
		
	def on_submit(doc):
		if doc.status not in ("Failed", "Passed"):
			frappe.msgprint("Update the status to Passed or Failed before Submitting", raise_exception = 1)