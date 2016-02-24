from __future__ import unicode_literals

import frappe
from erpnext.stock.doctype.item.item import DuplicateReorderRows

def execute():
	if frappe.db.has_column("Item", "re_order_level"):
		for item in frappe.db.sql("""select name, default_warehouse, re_order_level, re_order_qty
			from tabItem
			where has_variants =0 AND ifnull(re_order_level, 0) != 0""", as_dict=1):
			if item.re_order_qty == 0:
				item.re_order_qty = 1
			item_doc = frappe.get_doc("Item", item.name)
			item_doc.append("reorder_levels", {
				"warehouse": item.default_warehouse,
				"warehouse_reorder_level": item.re_order_level,
				"warehouse_reorder_qty": item.re_order_qty,
				"material_request_type": "Transfer"
			})

			try:
				item_doc.save()
				print "Update ROL for", item.name, "WH=", item.default_warehouse, " ROL=", item.re_order_level, " ROQ=", item.re_order_qty
			except DuplicateReorderRows:
				pass