# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from ....utils.job_card_utils import get_last_jc_for_so


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def get_columns(filters):
	if filters.get("summary") == 1:
		return [
			"Employee Name::150", "Workstation:Link/Workstation:150",
			"Item Code:Link/Item:100", "Description::300", "Planned Qty:Float:100", "Completed Qty:Float:100",
			"Rejected Qty:Float:100", "Operation::200", "Total Time (mins):Float:80", "Time Per Pc:Float:80",
			"JC#:Link/Process Job Card RIGPL:100"
		]
	elif filters.get("production_planning") == 1:
		return [
			"JC#:Link/Process Job Card RIGPL:100", "Status::60", "Item:Link/Item:120", "Priority:Int:50",
			"BM::60", "TT::60", "SPL::60", "Series::60", "D1:Float:50", "W1:Float:50", "L1:Float:50", "D2:Float:50",
			"L2:Float:50", "Description::400",
			"Operation:Link/Operation:100", "Allocated Machine:Link/Workstation:150",
			"Planned Qty:Float:80", "Qty Avail:Float:80",
			"ROL:Int:80", "SO:Int:80", "PO:Int:80", "Plan:Int:80", "Prod:Float:80", "Total Actual:Float:80"
		]
	elif filters.get("order_wise_summary") == 1:
		return [
			"SO#:Link/Sales Order:150", "SO Date:Date:80", "Item:Link/Item:120", "Description::450",
			"Pending:Float:60", "Ordered:Float:60", "JC#:Link/Process Job Card RIGPL:80", "PS#::150",
			"Status::60", "Operation:Link/Operation:100", "Priority:Int:50", "Planned Qty:Float:80",
			"Qty Avail:Float:80", "Remarks::400"
		]
	else:
		frappe.throw("Select one of the 3 Check Boxes.")


def get_data(filters):
	cond_jc, cond_it, cond_so = get_conditions(filters)
	if filters.get("summary") == 1:
		query = """SELECT jc.employee_name, jc.workstation, jc.production_item, jc.description, 
		jc.for_quantity, jc.total_completed_qty, jc.total_rejected_qty, jc.operation, jc.total_time_in_mins, 
		ROUND((jc.total_time_in_mins/ (jc.total_completed_qty + jc.total_rejected_qty)),2), jc.name
		FROM `tabProcess Job Card RIGPL` jc WHERE jc.docstatus = 1 %s 
		ORDER BY jc.workstation, jc.production_item""" % cond_jc
		data = frappe.db.sql(query, as_list=1)
	elif filters.get("production_planning") == 1:
		query = """SELECT jc.name, jc.status, jc.production_item, IF(jc.priority=0, NULL, jc.priority),
		bm.attribute_value, tt.attribute_value,
		spl.attribute_value, ser.attribute_value, d1.attribute_value, w1.attribute_value, l1.attribute_value,
		d2.attribute_value, l2.attribute_value,
		jc.description, jc.operation, jc.workstation, jc.for_quantity, 
		IF(jc.qty_available=0, NULL, jc.qty_available),
		IF(ro.warehouse_reorder_level=0, NULL ,ro.warehouse_reorder_level) AS rol,
		IF(bn.on_so=0, NULL ,bn.on_so) AS on_so,
		IF(bn.on_po=0, NULL ,bn.on_so) AS on_po,
		IF(bn.plan=0, NULL ,bn.plan) AS plan,
		IF(bn.prod=0, NULL ,bn.prod) AS prod,
		IF(bn.act=0, NULL ,bn.act) AS act
		FROM `tabProcess Job Card RIGPL` jc 
		LEFT JOIN `tabItem` it ON it.name = jc.production_item
		LEFT JOIN `tabBOM Operation` bo ON jc.operation_id = bo.name
		LEFT JOIN `tabItem Reorder` ro ON jc.production_item = ro.parent
		LEFT JOIN (SELECT item_code, SUM(reserved_qty) as on_so, SUM(ordered_qty) as on_po, SUM(actual_qty) as act,
			SUM(planned_qty) as plan, SUM(reserved_qty_for_production) as prod, SUM(indented_qty) as indent
			FROM `tabBin` GROUP BY item_code) bn 
			ON jc.production_item = bn.item_code
		LEFT JOIN `tabItem Variant Attribute` bm ON it.name = bm.parent
			AND bm.attribute = 'Base Material'
		LEFT JOIN `tabItem Variant Attribute` tt ON it.name = tt.parent
			AND tt.attribute = 'Tool Type'
		LEFT JOIN `tabItem Variant Attribute` spl ON it.name = spl.parent
			AND spl.attribute = 'Special Treatment'
		LEFT JOIN `tabItem Variant Attribute` ser ON it.name = ser.parent
			AND ser.attribute = 'Series'
		LEFT JOIN `tabItem Variant Attribute` d1 ON it.name = d1.parent
			AND d1.attribute = 'd1_mm'
		LEFT JOIN `tabItem Variant Attribute` w1 ON it.name = w1.parent
			AND w1.attribute = 'w1_mm'
		LEFT JOIN `tabItem Variant Attribute` l1 ON it.name = l1.parent
			AND l1.attribute = 'l1_mm'
		LEFT JOIN `tabItem Variant Attribute` d2 ON it.name = d2.parent
			AND d2.attribute = 'd2_mm'
		LEFT JOIN `tabItem Variant Attribute` l2 ON it.name = l2.parent
			AND l2.attribute = 'l2_mm'
		WHERE jc.docstatus = 0 %s %s
		ORDER BY bo.idx, jc.operation, jc.production_item""" % (cond_jc, cond_it)
		data = frappe.db.sql(query, as_list=1)
	elif filters.get("order_wise_summary") == 1:
		query = """SELECT so.name, so.transaction_date, soi.item_code, soi.description, 
		(soi.qty - ifnull(soi.delivered_qty, 0)) as pend_qty, soi.qty, "" as jc_name, "NO JC" as jc_status, 
		"" as jc_operation, 0 as jc_priority, 0 as planned_qty, 0 as qty_avail, "Not in Production" as remarks, 
		soi.name as so_item
		FROM `tabSales Order` so, `tabSales Order Item` soi, `tabItem` it
		WHERE soi.parent = so.name AND so.docstatus = 1 AND (soi.qty - ifnull(soi.delivered_qty, 0)) > 0 
		AND so.status != "Closed" AND so.transaction_date <= curdate() AND soi.item_code = it.name 
		AND it.made_to_order = 1 %s ORDER BY so.transaction_date, so.name, soi.item_code, soi.description""" % cond_so
		so_data = frappe.db.sql(query, as_dict=1)
		data = update_so_data_with_job_card(so_data)
	else:
		frappe.throw("Select one of the 3 Check Boxes.")
	return data


def update_so_data_with_job_card(so_dict):
	data = []
	for so in so_dict:
		line_data = []
		ps_dict = frappe.db.sql("""SELECT name FROM `tabProcess Sheet` 
			WHERE docstatus != 2 AND sales_order_item = '%s' ORDER BY creation""" % so.so_item, as_dict=1)
		so["ps_name"] = ""
		for ps in ps_dict:
			ps_link = """<a href="#Form/Process Sheet/%s" target="_blank">%s</a>""" % (ps.name, ps.name)
			so["ps_name"] += ps_link + "\n"
		so_jc = get_last_jc_for_so(so.so_item)
		if so_jc:
			so["jc_name"] = so_jc.name
			so["jc_status"] = so_jc.status
			so["jc_operation"] = so_jc.operation
			so["jc_priority"] = so_jc.priority
			so["planned_qty"] = so_jc.for_quantity
			so["qty_avail"] = so_jc.qty_available
			so["remarks"] = so_jc.remarks
		line_data = [so.name, so.transaction_date, so.item_code, so.description, so.pend_qty, so.qty, so.jc_name,
					 so.ps_name, so.jc_status, so.jc_operation, so.jc_priority, so.planned_qty, so.qty_avail, so.remarks]
		data.append(line_data)
	return data


def get_conditions(filters):
	cond_jc = ""
	cond_it = ""
	cond_so = ""
	no_of_checks = 0
	if filters.get("summary") == 1:
		no_of_checks += 1
	if filters.get("production_planning") == 1:
		no_of_checks += 1
	if filters.get("order_wise_summary") == 1:
		no_of_checks += 1
	if no_of_checks == 0:
		frappe.throw("One checkbox is needed to be checked")
	elif no_of_checks > 1:
		frappe.throw("Only 1 checkbox should be checked")

	if filters.get("from_date") and filters.get("summary") == 1:
		cond_jc += " AND jc.posting_date >= '%s'" % filters.get("from_date")
	if filters.get("to_date") and filters.get("summary") == 1:
		cond_jc += " AND jc.posting_date <= '%s'" % filters.get("to_date")

	if not filters.get("summary"):
		if filters.get("sales_order") and filters.get("summary") != 1:
			cond_jc += " AND jc.sales_order = '%s'" % filters.get("sales_order")
		if filters.get("jc_status"):
			cond_jc += " AND jc.status = '%s'" % filters.get("jc_status")
		if filters.get("operation"):
			cond_jc += " AND jc.operation = '%s'" % filters.get("operation")
		if filters.get("bm"):
			cond_it += " AND bm.attribute_value = '%s'" % filters.get("bm")
		if filters.get("tt"):
			cond_it += " AND tt.attribute_value = '%s'" % filters.get("tt")
		if filters.get("spl"):
			cond_it += " AND spl.attribute_value = '%s'" % filters.get("spl")
		if filters.get("series"):
			cond_it += " AND ser.attribute_value = '%s'" % filters.get("series")
		if filters.get("item"):
			cond_jc += " AND jc.production_item = '%s'" % filters.get("item")

	if filters.get("order_wise_summary") == 1:
		if filters.get("sales_order"):
			cond_so	+= " AND so.name = '%s'" % filters.get("sales_order")

	return cond_jc, cond_it, cond_so
