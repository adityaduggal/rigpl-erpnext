# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import datetime
import math
from frappe.utils import getdate, flt

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
	data = []
	so_item = filters.get("so_item")
	wh = filters.get("warehouse")
	conditions = get_conditions(filters)

	query = """SELECT jc.posting_date, jc.posting_time, jc.production_item, jc.description, jc.total_completed_qty, 0, 
	jc.s_warehouse, jc.t_warehouse, jc.name, jc.process_sheet, ps.bom_template, ste.name as ste, 
	jc.operation, jc.workstation, jc.operation_serial_no as op_sno, jc.sales_order as so, jc.sno, 
	wh.is_subcontracting_warehouse, "Process Job Card RIGPL" as ref_type
	FROM `tabProcess Job Card RIGPL` jc, `tabStock Entry` ste, `tabProcess Sheet` ps, `tabWarehouse` wh
	WHERE ste.process_job_card = jc.name AND jc.process_sheet = ps.name AND jc.docstatus = 1 
	AND jc.status = 'Completed' AND wh.name = jc.t_warehouse AND jc.sales_order_item = '%s' %s
	ORDER BY jc.posting_date DESC, jc.posting_time DESC""" % (so_item, conditions)
	rd = frappe.db.sql(query, as_dict=1)
	for i in range(0, len(rd)):
		ptime = datetime.timedelta(seconds=math.ceil((rd[i].posting_time).total_seconds()))
		if rd[i].t_warehouse == filters.get("warehouse"):
			qty = rd[i].total_completed_qty
			row = [
				rd[i].posting_date, ptime, rd[i].production_item, rd[i].description, qty, rd[i].s_warehouse,
				rd[i].t_warehouse, rd[i].name, rd[i].process_sheet, rd[i].bom_template, rd[i].ste, rd[i].operation,
				rd[i].workstation, rd[i].op_sno, rd[i].sno, rd[i].so, rd[i].ref_type
			]
			data.append(row)
		elif rd[i].s_warehouse == filters.get("warehouse"):
			qty = (-1) * rd[i].total_completed_qty
			row = [
				rd[i].posting_date, ptime, rd[i].production_item, rd[i].description, qty, rd[i].s_warehouse,
				rd[i].t_warehouse, rd[i].name, rd[i].process_sheet, rd[i].bom_template, rd[i].ste, rd[i].operation,
				rd[i].workstation, rd[i].op_sno, rd[i].sno, rd[i].so, rd[i].ref_type
			]
			data.append(row)
		else:
			if rd[i].is_subcontracting_warehouse == 1:
				poi = frappe.db.sql("""SELECT poi.name FROM `tabPurchase Order Item` poi, `tabPurchase Order` po
				WHERE po.docstatus=1 AND poi.parent = po.name AND poi.reference_dn = '%s'""" % rd[i].name, as_dict=1)
				if poi:
					query = """SELECT grn.name, pr.posting_date, pr.posting_time, grn.item_code,
					grn.description, grn.qty, grn.warehouse, ste.name as ste, "Purchase Receipt" as ref_type,
					pr.name as pr_name
					FROM `tabPurchase Receipt Item` grn, `tabStock Entry` ste, `tabPurchase Receipt` pr
					WHERE ste.purchase_receipt_no = grn.parent AND grn.parent = pr.name AND pr.docstatus = 1 
					AND grn.purchase_order_item = '%s' """ % poi[0].name
					grn = frappe.db.sql(query, as_dict=1)
					if grn:
						for d in grn:
							ptime = datetime.timedelta(seconds=math.ceil((d.posting_time).total_seconds()))
							if d.warehouse == filters.get("warehouse"):
								# Add row for Material Receipt for Sub Contracting items
								row = [
									d.posting_date, ptime, rd[i].production_item, d.description, d.qty,
									rd[i].t_warehouse, d.warehouse, d.pr_name, "X", "X", d.ste, "X", "X", "X",
									rd[i].sno, rd[i].so, d.ref_type
								]
								data.append(row)
			else:
				continue
		dn = frappe.db.sql("""SELECT dn.name, dni.item_code, dni.warehouse, dni.description, dn.posting_date,
		dn.posting_time, dni.qty, dni.against_sales_order, dni.so_detail, sod.idx, "Delivery Note" as ref_type
		FROM `tabDelivery Note` dn, `tabDelivery Note Item` dni, `tabSales Order Item` sod
		WHERE dn.docstatus = 1 AND dni.parent = dn.name AND sod.name = dni.so_detail
		AND dni.so_detail = '%s'""" % so_item, as_dict=1)
	return data


def get_conditions(filters):
	cond = ""
	all_entries_cond = ""
	'''
	if filters.get("warehouse"):
		cond += " AND (jc.t_warehouse = '%s' OR jc.s_warehouse = '%s')" % (filters.get("warehouse"),
																		  filters.get("warehouse"))
		all_entries_cond += " AND (t_warehouse = '%s' OR s_warehouse = '%s')" % (filters.get("warehouse"),
																		  filters.get("warehouse"))
	'''
	if filters.get("from_date"):
		cond += " AND jc.posting_date >= '%s'" % filters.get("from_date")
	if filters.get("to_date"):
		cond += " AND jc.posting_date <= '%s'" % filters.get("to_date")
	return cond
