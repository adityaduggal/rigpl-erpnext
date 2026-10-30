#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
from frappe.query_builder import Order
from frappe.utils import getdate, nowdate
from ....utils.pending_report_utils import get_pending_rows
from ....utils.report_utils import blank_zeros


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = [blank_zeros(row) for row in get_so_entries(filters)]

	return columns, data


def get_columns():
	return [
		"SO No:Link/Sales Order:100", "SO Date:Date:80", "ED Date:Date:80", "Customer:Link/Customer:180",
		"Item Code:Link/Item:160", "Description::300", "Pending Qty:Float:70", "Qty:Float:40",
		"Delivered Qty:Float:40", "PO No::80", "Status::100"
	]


def get_so_entries(filters):
	so_filters = {"customer": filters.get("customer"), "item": filters.get("item"),
		"to_date": min(getdate(filters.get("date") or nowdate()), getdate(nowdate()))}
	return [
		[so.parent, so.date, so.delivery_date, so.party, so.item_code, so.description, so.pending_qty, so.qty,
			so.delivered_qty, so.po_no, so.status]
		for so in get_pending_rows("so_delivery", so_filters, order=Order.desc,
			fields=["parent.delivery_date", "parent.po_no", "parent.status", "child.delivered_qty"])
	]
