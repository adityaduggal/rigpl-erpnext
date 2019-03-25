# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import date_diff, flt
from datetime import datetime
from six import iteritems

def execute(filters=None):

	columns = get_columns(filters)
	items, item_map = get_item_details(filters)
	item_details = get_fifo_queue(filters, items)
	to_date = filters["to_date"]
	data = []
	for item, item_dict in iteritems(item_details):
		fifo_queue = item_dict["fifo_queue"]
		details = item_dict["details"]
		if not fifo_queue: continue

		average_age = get_average_age(fifo_queue, to_date)
		earliest_age = date_diff(to_date, fifo_queue[0][1])
		latest_age = date_diff(to_date, fifo_queue[-1][1])
		item_detail_dict = item_map[details.name]
		row = [details.name, item_detail_dict["desc"]]

		if filters.get("show_ageing_warehouse_wise"):
			row.append(details.warehouse)

		row.extend([item_dict.get("total_qty"), average_age,
			earliest_age, latest_age,
			item_detail_dict["stock_uom"], item_detail_dict["rm"], item_detail_dict["bm"],
			item_detail_dict["tt"], item_detail_dict["brand"], item_detail_dict["quality"], item_detail_dict["spl"],
			item_detail_dict["d1"], item_detail_dict["w1"], item_detail_dict["l1"], item_detail_dict["d2"],
			item_detail_dict["l2"], item_detail_dict["zn"]])

		data.append(row)

	return columns, data

def get_average_age(fifo_queue, to_date):
	batch_age = age_qty = total_qty = 0.0
	for batch in fifo_queue:
		batch_age = date_diff(to_date, batch[1])
		age_qty += batch_age * batch[0]
		total_qty += batch[0]

	return (age_qty / total_qty) if total_qty else 0.0

def get_stock_ledger_entries(filters, items):
	conditions, conditions_it = get_conditions(filters)
	filters["to_date"] = datetime.strptime(filters["to_date"], '%Y-%m-%d').date()

	wh = frappe.db.sql("""SELECT name FROM `tabWarehouse` WHERE disabled = 'No' AND is_group = 0
		ORDER BY name""", as_list=1)

	sle_entries = frappe.db.sql("""select
		sle.item_code as name, sle.stock_uom,
		sle.actual_qty, sle.posting_date, sle.voucher_type, sle.qty_after_transaction, sle.warehouse
		FROM `tabStock Ledger Entry` sle, `tabWarehouse` wh
		WHERE IFNULL(sle.is_cancelled, 'No') = 'No'
		AND wh.name = sle.warehouse AND wh.is_group = 0
		AND wh.disabled = 'No' {condition} AND sle.item_code IN (%s)
		ORDER BY sle.item_code, sle.warehouse, posting_date ASC
		""".format(condition=conditions) %(", ".join(['%s']*len(items))), \
		tuple([d.name for d in items]), as_dict=1)
	return sle_entries

def get_fifo_queue(filters, items):
	item_details = {}
	for d in get_stock_ledger_entries(filters, items):
		key = (d.name, d.warehouse) if filters.get('show_ageing_warehouse_wise') else d.name
		item_details.setdefault(key, {"details": d, "fifo_queue": []})
		fifo_queue = item_details[key]["fifo_queue"]

		if d.voucher_type == "Stock Reconciliation":
			d.actual_qty = flt(d.qty_after_transaction) - flt(item_details[key].get("qty_after_transaction", 0))

		if d.actual_qty > 0:
			fifo_queue.append([d.actual_qty, d.posting_date])
		else:
			qty_to_pop = abs(d.actual_qty)
			while qty_to_pop:
				batch = fifo_queue[0] if fifo_queue else [0, None]
				if 0 < batch[0] <= qty_to_pop:
					# if batch qty > 0
					# not enough or exactly same qty in current batch, clear batch
					qty_to_pop -= batch[0]
					fifo_queue.pop(0)
				else:
					# all from current batch
					batch[0] -= qty_to_pop
					qty_to_pop = 0

		item_details[key]["qty_after_transaction"] = d.qty_after_transaction

		if "total_qty" not in item_details[key]:
			item_details[key]["total_qty"] = d.actual_qty
		else:
			item_details[key]["total_qty"] += d.actual_qty

	return item_details

def get_item_details(filters):
	conditions, conditions_it = get_conditions(filters)
	item_map = {}
	query = """SELECT it.name AS "name", it.description AS "desc", it.valuation_rate AS "vr", it.stock_uom,
		IFNULL(bm.attribute_value, "-") AS "bm", IFNULL(brand.attribute_value, "-") AS "brand",
		IFNULL(h_qual.attribute_value, IFNULL (c_qual.attribute_value, "-")) AS "quality",
		IFNULL(tt.attribute_value, "-") AS "tt",
		IFNULL (spl.attribute_value, "-") AS "spl",
		CAST(d1.attribute_value AS DECIMAL(8,3)) AS "d1",
		CAST(w1.attribute_value AS DECIMAL(8,3)) AS "w1",
		CAST(l1.attribute_value AS DECIMAL(8,3)) AS "l1",
		CAST(d2.attribute_value AS DECIMAL(8,3)) AS "d2",
		CAST(l2.attribute_value AS DECIMAL(8,3)) AS "l2",
		IFNULL(rm.attribute_value, "-") AS "rm", it.is_purchase_item,
		CAST(zn.attribute_value AS DECIMAL(8,3)) AS "zn"
		FROM `tabItem` it
		LEFT JOIN `tabItem Variant Attribute` rm ON it.name = rm.parent
			AND rm.attribute = 'Is RM'
		LEFT JOIN `tabItem Variant Attribute` bm ON it.name = bm.parent
			AND bm.attribute = 'Base Material'
		LEFT JOIN `tabItem Variant Attribute` h_qual ON it.name = h_qual.parent
			AND h_qual.attribute = 'HSS Quality'
		LEFT JOIN `tabItem Variant Attribute` c_qual ON it.name = c_qual.parent
			AND c_qual.attribute = 'Carbide Quality'
		LEFT JOIN `tabItem Variant Attribute` brand ON it.name = brand.parent
			AND brand.attribute = 'Brand'
		LEFT JOIN `tabItem Variant Attribute` tt ON it.name = tt.parent
			AND tt.attribute = 'Tool Type'
		LEFT JOIN `tabItem Variant Attribute` spl ON it.name = spl.parent
			AND spl.attribute = 'Special Treatment'
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
		LEFT JOIN `tabItem Variant Attribute` zn ON it.name = zn.parent
			AND zn.attribute = 'Number of Flutes Zn'
		WHERE IFNULL(it.end_of_life, '2099-12-31') > CURDATE() %s
		ORDER BY 
			rm.attribute_value, bm.attribute_value, h_qual.attribute_value,
			c_qual.attribute_value, tt.attribute_value,
			CAST(d1.attribute_value AS DECIMAL(8,3)),
			CAST(w1.attribute_value AS DECIMAL(8,3)),
			CAST(l1.attribute_value AS DECIMAL(8,3)),
			CAST(d2.attribute_value AS DECIMAL(8,3)),
			CAST(l2.attribute_value AS DECIMAL(8,3))""" %conditions_it
	
	items = frappe.db.sql(query , as_dict=1)
	if items:
		pass
	else:
		frappe.throw("No Items Found in given Criterion")
	for d in items:item_map.setdefault(d.name, d)

	return items, item_map


def get_columns(filters):
	columns = [_("Item Code") + ":Link/Item:120", _("Description") + "::200"]

	if filters.get("show_ageing_warehouse_wise"):
		columns.extend([_("Warehouse") + ":Link/Warehouse:130"])

	columns.extend([_("Available Qty") + ":Float:100", _("Average Age") + ":Int:80",
		_("Earliest") + ":Int:80", _("Latest") + ":Int:80", _("UOM") + ":Link/UOM:50",
		_("Is RM") + "::60", _("BM") + "::60", _("TT") + "::150", _("Brand") + "::60", _("Qual") + "::60",
		_("Spl") + "::60", _("D1") + ":Float:60", _("W1") + ":Float:60", _("L1") + ":Float:60",
		_("D2") + ":Float:60", _("L2") + ":Float:60", _("Zn") + ":Float:60"])

	return columns


def get_item_conditions(filters):
	conditions = []
	if filters.get("item_code"):
		conditions.append("item_code=%(item_code)s")
	if filters.get("brand"):
		conditions.append("brand=%(brand)s")

	return "where {}".format(" and ".join(conditions)) if conditions else ""

def get_conditions(filters):
	conditions_sle = ""
	conditions_it = ""
	if filters.get("item_code"):
		conditions_sle += " AND sle.item_code='%s'" % filters["item_code"]
		conditions_it += " AND it.name ='%s'" % filters["item_code"]

	if filters.get("warehouse"):
		conditions_sle += " AND sle.warehouse='%s'" % filters["warehouse"]

	if filters.get("to_date"):
		conditions_sle += " AND sle.posting_date <= '%s'" % filters["to_date"]

	if filters.get("rm"):
		conditions_it += " AND rm.attribute_value = '%s'" % filters["rm"]

	if filters.get("bm"):
		conditions_it += " AND bm.attribute_value = '%s'" % filters["bm"]

	if filters.get("brand"):
		conditions_it += " AND brand.attribute_value = '%s'" % filters["brand"]
		
	if filters.get("tt"):
		conditions_it += " AND tt.attribute_value = '%s'" % filters["tt"]

	if filters.get("spl"):
		conditions_it += " AND spl.attribute_value = '%s'" % filters["spl"]
		
	return conditions_sle, conditions_it

def get_sle_conditions(filters):
	conditions = []
	if filters.get("warehouse"):
		lft, rgt = frappe.db.get_value('Warehouse', filters.get("warehouse"), ['lft', 'rgt'])
		conditions.append("""warehouse in (select wh.name from `tabWarehouse` wh
			where wh.lft >= {0} and rgt <= {1})""".format(lft, rgt))

	return "and {}".format(" and ".join(conditions)) if conditions else ""