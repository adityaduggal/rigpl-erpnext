#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder import Order
from frappe.utils import add_days, flt, getdate, nowdate
from ....manufacturing_rigpl.utils.job_card_utils import get_last_jc_for_so_items
from ....utils.pending_report_utils import check_dates, get_bin_qtys, get_pending_rows, get_process_sheets
from ....utils.report_utils import blank_zeros

DELAYED_AFTER_DAYS = 45


def execute(filters=None):
	if not filters: filters = {}
	if filters.get("stock_status") == 1 and filters.get("made_to_order") == 1:
		frappe.throw("Both Check boxes checked is Not Allowed")
	check_dates(filters, required="date")

	columns = get_columns(filters)
	data = [blank_zeros(row) for row in get_so_entries(filters)]

	return columns, data


def get_columns(filters):
	if filters.get("stock_status") == 1:
		return get_stock_status_columns()
	elif filters.get("made_to_order") == 1:
		return [
			"SO#:Link/Sales Order:150", "Customer:Link/Customer:150", "SO Date:Date:80", "Item:Link/Item:120",
			"Description::450", "Pending:Float:60", "Ordered:Float:60", "JC#:Link/Process Job Card RIGPL:80",
			"PS#::150", "Status::60", "Operation:Link/Operation:100", "Priority:Int:50", "Planned Qty:Float:80",
			"Qty Avail:Float:80", "Remarks::400"
		]
	else:
		return [
			"Date:Date:80", "SO #:Link/Sales Order:100", "ED Date:Date:80",
			"Customer:Link/Customer:180","Item Code:Link/Item:160",
			"Description::300", "Pending:Float:60", "Ordered:Float:60",
			"Delivered:Float:60", "Price:Currency:60", "Pending Amount:Currency:100",
			"PO#::80", "PRD Notes::100", "Status::100", "% SO Pending:Float:80",
			"% Item Pending:Float:80"
		]


def get_stock_status_columns():
	return ["SO #:Link/Sales Order:100", "Date:Date:80", "Item Code:Link/Item:160",
			"Description::300", "Pending:Float:60", "Warehouse:Link/Warehouse:100", "Actual Qty:Float:60",
			"Reserved:Float:60", "Customer:Link/Customer:200"]


def get_so_filters(filters):
	return {"customer": filters.get("customer"), "item": filters.get("item"), "bm": filters.get("bm"),
		"to_date": filters.get("date")}


def get_so_entries(filters):
	if filters.get("stock_status") == 1:
		return get_stock_status_rows(filters)
	elif filters.get("made_to_order") == 1:
		return get_made_to_order_rows(filters)
	return get_pending_order_rows(filters)


def get_pending_order_rows(filters):
	delayed_before = add_days(nowdate(), -DELAYED_AFTER_DAYS)
	data = []
	for so in get_pending_rows("so_delivery", get_so_filters(filters), order=Order.desc,
			fields=["child.delivery_date", "child.delivered_qty", "child.prd_notes", "parent.po_no",
				"parent.per_delivered"]):
		data.append([
			so.date, so.parent, so.delivery_date, so.party, so.item_code, so.description, so.pending_qty,
			so.qty, so.delivered_qty, so.base_rate, so.pending_amount, so.po_no, so.prd_notes,
			"DELAYED" if getdate(so.date) < getdate(delayed_before) else "OK", 100 - flt(so.per_delivered),
			so.pending_qty / so.qty * 100 if so.qty else None,
		])
	return data


def get_stock_status_rows(filters):
	"""Rows of stock items that have stock in the warehouse of the Sales Order row"""
	so_filters = dict(get_so_filters(filters), made_to_order=0)
	so_filters["to_date"] = min(getdate(filters.get("date")), getdate(nowdate()))
	rows = get_pending_rows("so_delivery", so_filters, fields=["child.warehouse"])
	bins = get_bin_qtys([(so.item_code, so.warehouse) for so in rows])
	data = []
	for so in rows:
		bn = bins.get((so.item_code, so.warehouse))
		if bn and flt(bn.actual_qty) > 0:
			data.append([so.parent, so.date, so.item_code, so.description, so.pending_qty, so.warehouse,
				bn.actual_qty, bn.reserved_qty, so.party])
	return data


def get_made_to_order_rows(filters):
	so_filters = dict(get_so_filters(filters), made_to_order=1)
	so_filters["to_date"] = min(getdate(filters.get("date")), getdate(nowdate()))
	rows = get_pending_rows("so_delivery", so_filters)
	rows.sort(key=lambda so: (so.date, so.parent, so.item_code, so.description or ""))
	so_items = [so.row_name for so in rows]
	sheets = get_process_sheets(so_items)
	last_jcs = get_last_jc_for_so_items(so_items)
	data = []
	for so in rows:
		ps_name = "".join('<a href="#Form/Process Sheet/{0}" target="_blank">{0}</a>\n'.format(ps)
			for ps in sheets.get(so.row_name, []))
		jc = last_jcs.get(so.row_name) or frappe._dict(name="", status="NO JC", operation="", priority=0,
			for_quantity=0, qty_available=0, remarks="Not in Production")
		data.append([so.parent, so.party, so.date, so.item_code, so.description, so.pending_qty, so.qty,
			jc.name, ps_name, jc.status, jc.operation, jc.priority, jc.for_quantity, jc.qty_available,
			jc.remarks])
	return data
