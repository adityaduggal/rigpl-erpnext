# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import datetime
import math
from ....utils.item_attribute_utils import chunks
from ....utils.report_utils import blank_zeros


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	return [
		"Date:Date:80", "Time:Time:70" ,"Item:Link/Item:130", "Description::450",
		"Qty:Float:60", "Source WH::120", "Target WH::120",
		{
			"label": "Ref#",
			"fieldname": "ref_no",
			"fieldtype": "Dynamic Link",
			"options": "ref_type",
			"width": 100
		},
		"PS#:Link/Process Sheet:100",
		"BT:Link/BOM Template RIGPL:100", "STE:Link/Stock Entry:100", "Operation:Link/Operation:100",
		"Workstation:Link/Workstation:100", "Operation#:Int:50", "SO SNo:Int:50", "SO#:Link/Sales Order:150",
		{
			"label": "Ref Type",
			"fieldname": "ref_type",
			"width": 1
		}
	]


def get_data(filters):
	"""
	Returns the rows of the completed Job Cards of the SO item that move stock in or out of the
	warehouse, and the Purchase Receipt rows of the subcontracted Job Cards into the warehouse
	"""
	wh = filters.get("warehouse")
	job_cards = get_job_cards(filters)
	subcontracted = [jc.name for jc in job_cards
		if wh not in (jc.t_warehouse, jc.s_warehouse) and jc.is_subcontracting_warehouse == 1]
	receipts = get_subcontracting_receipts(subcontracted)

	data = []
	for jc in job_cards:
		if jc.t_warehouse == wh or jc.s_warehouse == wh:
			qty = jc.total_completed_qty if jc.t_warehouse == wh else (-1) * jc.total_completed_qty
			data.append(blank_zeros([
				jc.posting_date, round_up_time(jc.posting_time), jc.production_item, jc.description, qty,
				jc.s_warehouse, jc.t_warehouse, jc.name, jc.process_sheet, jc.bom_template, jc.ste,
				jc.operation, jc.workstation, jc.op_sno, jc.sno, jc.so, "Process Job Card RIGPL"
			]))
			continue
		for d in receipts.get(jc.name, []):
			if d.warehouse == wh:
				# Add row for Material Receipt for Sub Contracting items
				data.append(blank_zeros([
					d.posting_date, round_up_time(d.posting_time), jc.production_item, d.description, d.qty,
					jc.t_warehouse, d.warehouse, d.pr_name, "X", "X", d.ste, "X", "X", "X",
					jc.sno, jc.so, "Purchase Receipt"
				]))
	return data


def get_job_cards(filters):
	jc = frappe.qb.DocType("Process Job Card RIGPL")
	ste = frappe.qb.DocType("Stock Entry")
	ps = frappe.qb.DocType("Process Sheet")
	whs = frappe.qb.DocType("Warehouse")
	query = (
		frappe.qb.from_(jc)
		.join(ste).on(ste.process_job_card == jc.name)
		.join(ps).on(ps.name == jc.process_sheet)
		.join(whs).on(whs.name == jc.t_warehouse)
		.select(
			jc.name, jc.posting_date, jc.posting_time, jc.production_item, jc.description,
			jc.total_completed_qty, jc.s_warehouse, jc.t_warehouse, jc.process_sheet, ps.bom_template,
			ste.name.as_("ste"), jc.operation, jc.workstation, jc.operation_serial_no.as_("op_sno"),
			jc.sales_order.as_("so"), jc.sno, whs.is_subcontracting_warehouse
		)
		.where(jc.docstatus == 1)
		.where(jc.status == "Completed")
		.where(jc.sales_order_item == filters.get("so_item"))
		.orderby(jc.posting_date, order=frappe.qb.desc)
		.orderby(jc.posting_time, order=frappe.qb.desc)
	)
	if filters.get("from_date"):
		query = query.where(jc.posting_date >= filters.get("from_date"))
	if filters.get("to_date"):
		query = query.where(jc.posting_date <= filters.get("to_date"))
	return query.run(as_dict=True)


def get_subcontracting_receipts(job_cards):
	"""
	Returns {job card: [Purchase Receipt rows]} for the first submitted PO item of each Job Card
	"""
	if not job_cards:
		return {}
	po = frappe.qb.DocType("Purchase Order")
	poi = frappe.qb.DocType("Purchase Order Item")
	po_item_of = {}
	for chunk in chunks(job_cards):
		rows = (
			frappe.qb.from_(poi)
			.join(po).on(po.name == poi.parent)
			.select(poi.name, poi.reference_dn)
			.where(po.docstatus == 1)
			.where(poi.reference_dn.isin(chunk))
			.orderby(poi.creation)
			.orderby(poi.name)
			.run(as_dict=True)
		)
		for row in rows:
			po_item_of.setdefault(row.reference_dn, row.name)
	if not po_item_of:
		return {}

	job_card_of = {po_item: jc for jc, po_item in po_item_of.items()}
	grn = frappe.qb.DocType("Purchase Receipt Item")
	pr = frappe.qb.DocType("Purchase Receipt")
	ste = frappe.qb.DocType("Stock Entry")
	receipts = {}
	for chunk in chunks(list(job_card_of)):
		rows = (
			frappe.qb.from_(grn)
			.join(pr).on(pr.name == grn.parent)
			.join(ste).on(ste.purchase_receipt_no == grn.parent)
			.select(
				grn.purchase_order_item, pr.posting_date, pr.posting_time, grn.description, grn.qty,
				grn.warehouse, ste.name.as_("ste"), pr.name.as_("pr_name")
			)
			.where(pr.docstatus == 1)
			.where(grn.purchase_order_item.isin(chunk))
			.run(as_dict=True)
		)
		for row in rows:
			receipts.setdefault(job_card_of[row.purchase_order_item], []).append(row)
	return receipts


def round_up_time(posting_time):
	return datetime.timedelta(seconds=math.ceil(posting_time.total_seconds()))
