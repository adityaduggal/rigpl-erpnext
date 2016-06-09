# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cstr, flt, getdate, new_line_sep

def validate(doc,method):
	pass

@frappe.whitelist()
def add_items_to_purchase_order(source_name, target_doc=None):
	def postprocess(source, target_doc):
		set_missing_values(source, target_doc)

	doclist = get_mapped_doc("Production Order", source_name, 	{
		"Production Order": {
			"doctype": "Purchase Order",
			"validation": {
				"docstatus": ["=", 1],
				"status": ["!=", "Stopped"]
			}
		},
		"Production Order": {
			"doctype": "Purchase Order Item",
			"field_map": [
				["production_item", "item_code"],
				["item_description", "description"],
				["wip_warehouse", "warehouse"],
				["sales_order", "prevdoc_docname"]
			],
			"postprocess": update_item,
			"condition": lambda doc: doc.docstatus == 1
		}
	}, target_doc, postprocess)
	frappe.msgprint(doclist.items)
	return doclist

def update_item(obj, target, source_parent):
	target.conversion_factor = 1
	target.qty = flt(obj.qty)
	target.stock_qty = target.qty
	
def set_missing_values(source, target_doc):
	target_doc.run_method("set_missing_values")
	target_doc.run_method("calculate_taxes_and_totals")