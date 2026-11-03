# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import flt, get_link_to_form
from ....utils.item_attribute_utils import chunks
from ....utils.report_utils import blank_zeros


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
	"""
	The stock of each item in the subcontracting warehouses against its pending subcontract PO qty.
	2 queries in place of 1 per warehouse and 1 per item (#187).
	"""
	stock = get_subcontracting_stock()
	po_rows = get_pending_po_rows(list(stock))
	data = []
	for item_code, (qty, valuation_rate) in stock.items():
		pend_po_qty = 0
		po_list = ""
		for po in po_rows.get(item_code, []):
			pend_po_qty += po.pend_qty
			po_list += get_link_to_form("Purchase Order", po.name) + "\n"
		diff = qty - pend_po_qty
		if diff > 0:
			message = f"Qty = {diff} was Short Closed but No Issue Entry done for Same"
		elif diff < 0:
			message = f"Qty = {pend_po_qty - qty} Over PO but not in Warehouse"
		else:
			message = "OK"
		data.append(blank_zeros([item_code, pend_po_qty, qty, diff, diff * flt(valuation_rate), message, po_list]))
	return data


def get_subcontracting_stock():
	"""{item: (qty, valuation rate)} of the items with stock in the subcontracting warehouses."""
	bn = frappe.qb.DocType("Bin")
	it = frappe.qb.DocType("Item")
	wh = frappe.qb.DocType("Warehouse")
	rows = (
		frappe.qb.from_(bn)
		.join(it).on(it.name == bn.item_code)
		.join(wh).on(wh.name == bn.warehouse)
		.select(bn.item_code, Sum(bn.actual_qty), it.valuation_rate)
		.where((wh.is_subcontracting_warehouse == 1) & (bn.actual_qty > 0))
		.groupby(bn.item_code, it.valuation_rate)
		.orderby(bn.item_code)
		.run()
	)
	return {row[0]: row[1:] for row in rows}


def get_pending_po_rows(items):
	"""{subcontracted item: [pending subcontract PO rows]}"""
	po = frappe.qb.DocType("Purchase Order")
	poi = frappe.qb.DocType("Purchase Order Item")
	po_rows = {}
	for chunk in chunks(items):
		rows = (
			frappe.qb.from_(po).join(poi).on(poi.parent == po.name)
			.select(poi.subcontracted_item, po.name, (poi.qty - poi.received_qty).as_("pend_qty"))
			.where((po.docstatus == 1) & (po.status != "Closed") & (po.is_subcontracting == 1))
			.where(poi.qty - poi.received_qty > 0)
			.where(poi.subcontracted_item.isin(chunk))
			.orderby(po.name).orderby(poi.idx)
			.run(as_dict=1)
		)
		for row in rows:
			po_rows.setdefault(row.subcontracted_item, []).append(row)
	return po_rows
