# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def get_columns(filters):
	return [
		"Item:Link/Item:120", "PO Qty Pending:Int:80", "Qty in WH:Int:80", "Difference:Int:80", "Diff Value:Float:120",
		"Message::300", "Pending PO#::500"
	]


def get_data(filters):
	data = []
	temp_dict = frappe._dict({})
	item_qty_list = []
	wh_list = frappe.db.sql("""SELECT name FROM `tabWarehouse` WHERE is_subcontracting_warehouse = 1""", as_dict=1)
	for wh in wh_list:
		it_list = frappe.db.sql("""SELECT bn.item_code, bn.warehouse, bn.actual_qty, it.valuation_rate FROM `tabBin` bn,
		`tabItem` it WHERE bn.warehouse = '%s' AND bn.actual_qty > 0 AND bn.item_code = it.name 
		ORDER BY bn.item_code""" % wh.name, as_dict=1)
		# frappe.msgprint(str(it_list))
		for it in it_list:
			exists = 0
			for d in item_qty_list:
				if d.get("item_code", "") == it.name:
					d["qty"] += it.actual_qty
					exists = 1
			if exists == 0:
				temp_dict["item_code"] = it.item_code
				temp_dict["valuation_rate"] = it.valuation_rate
				temp_dict["qty"] = it.actual_qty
				item_qty_list.append(temp_dict.copy())
	for it in item_qty_list:
		it["po_list"] = ""
		pending_sub_con_po_qty = frappe.db.sql("""SELECT po.name, po.supplier, (poi.qty - poi.received_qty) as pend_qty 
		FROM `tabPurchase Order` po, `tabPurchase Order Item` poi
		WHERE poi.parent = po.name AND po.docstatus = 1 AND po.status != 'Closed' AND po.is_subcontracting = 1
		AND (poi.qty - poi.received_qty) > 0 AND poi.subcontracted_item = '%s'""" % it.item_code, as_dict=1)
		po_list = ""
		po_qty = 0
		if pending_sub_con_po_qty:
			for po in pending_sub_con_po_qty:
				po_link = """<a href="#Form/Purchase Order/%s" target="_blank">%s</a>""" % (po.name, po.name)
				it["po_list"] += po_link + "\n"
				po_qty += po.pend_qty
			it["pend_po_qty"] = po_qty
		else:
			it["po_list"] = po_list
			it["pend_po_qty"] = po_qty
	for it in item_qty_list:
		diff = it.qty - it.pend_po_qty
		if diff > 0:
			message = f"Qty = {it.qty - it.pend_po_qty} was Short Closed but No Issue Entry done for Same"
		elif diff < 0:
			message = f"Qty = {it.pend_po_qty - it.qty} Over PO but not in Warehouse"
		else:
			message = "OK"
		row = [it.item_code, it.pend_po_qty, it.qty, diff, diff * flt(it.valuation_rate), message, it.po_list]
		data.append(row)
	return data

