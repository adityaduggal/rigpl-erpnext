# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_item_data(filters)

	return columns, data


def get_columns(filters):
	return [
		{
			"fieldname": "item",
			"label": "Item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120
		},
		{
			"fieldname": "pl1",
			"label": _(filters.pl1),
			"fieldtype": "Currency",
			"width": 70
		},
		{
			"fieldname": "pl1_cur",
			"label": _(filters.pl1) + " Cur",
			"width": 40
		},
		{
			"fieldname": "pl2",
			"label": _(filters.pl2),
			"fieldtype": "Currency",
			"width": 70
		},
		{
			"fieldname": "pl2_cur",
			"label": _(filters.pl2) + " Cur",
			"width": 40
		},
		{
			"fieldname": "pl2_diff",
			"label": _(filters.pl1) + "-" + _(filters.pl2),
			"options": "Float",
			"width": 80
		},
		{
			"fieldname": "pl3",
			"label": _(filters.pl3),
			"fieldtype": "Currency",
			"width": 70
		},
		{
			"fieldname": "pl3_cur",
			"label": _(filters.pl3) + " Cur",
			"width": 40
		},
		{
			"fieldname": "pl3_diff",
			"label": _(filters.pl1) + "-" + _(filters.pl3),
			"options": "Float",
			"width": 80
		},
		{
			"fieldname": "description",
			"label": "Description",
			"width": 400
		},
		{
			"fieldname": "bm",
			"label": "BM",
			"width": 60
		},
		{
			"fieldname": "brand",
			"label": "Brand",
			"width": 60
		},
		{
			"fieldname": "qlt",
			"label": "QLT",
			"width": 80
		},
		{
			"fieldname": "spl",
			"label": "SPL",
			"width": 50
		},
		{
			"fieldname": "tt",
			"label": "TT",
			"width": 150
		},
		{
			"fieldname": "d1",
			"label": "D1",
			"fieldtype": "Float",
			"width": 50
		},
		{
			"fieldname": "w1",
			"label": "W1",
			"fieldtype": "Float",
			"width": 50
		},
		{
			"fieldname": "l1",
			"label": "L1",
			"fieldtype": "Float",
			"width": 50
		},
		{
			"fieldname": "zn",
			"label": "Zn",
			"fieldtype": "Float",
			"width": 50
		},
		{
			"fieldname": "d2",
			"label": "D2",
			"fieldtype": "Float",
			"width": 50
		},
		{
			"fieldname": "l2",
			"label": "L2",
			"fieldtype": "Float",
			"width": 50
		},
		{
			"fieldname": "a1",
			"label": "A1",
			"fieldtype": "Float",
			"width": 50
		},
		{
			"fieldname": "is_pl",
			"label": "Is PL",
			"width": 50
		}
	]


def get_item_data(filters):
	conditions_it = get_conditions(filters)
	bm = filters["bm"]
	pl1 = " AND itp1.price_list = '%s'" % filters.get("pl1")
	pl2 = " AND itp2.price_list = '%s'" % filters.get("pl2")
	pl3 = " AND itp3.price_list = '%s'" % filters.get("pl3")
	query = """SELECT
		it.name, itp1.price_list_rate, IFNULL(itp1.currency, "-"),
		itp2.price_list_rate, IFNULL(itp2.currency, "-"), IF(itp1.price_list_rate > 0, 
		((itp2.price_list_rate-itp1.price_list_rate)/itp1.price_list_rate)*100,0),
		itp3.price_list_rate, IFNULL(itp3.currency, "-"),
		IF(itp1.price_list_rate > 0, ((itp3.price_list_rate-itp1.price_list_rate)/itp1.price_list_rate)*100,0),
		it.description,
		IFNULL(bm.attribute_value, "-"), IFNULL(brand.attribute_value, "-"),
		IFNULL(quality.attribute_value, "-"), IFNULL(spl.attribute_value, "-"),
		IFNULL(tt.attribute_value, "-"),
		CAST(d1.attribute_value AS DECIMAL(8,3)),
		CAST(w1.attribute_value AS DECIMAL(8,3)),
		CAST(l1.attribute_value AS DECIMAL(8,3)),
		CAST(zn.attribute_value AS UNSIGNED),
		CAST(d2.attribute_value AS DECIMAL(8,3)),
		CAST(l2.attribute_value AS DECIMAL(8,3)),
		CAST(a1.attribute_value AS DECIMAL(8,3)), it.pl_item
		
	FROM `tabItem` it
	
		LEFT JOIN `tabItem Price` itp1 ON it.name = itp1.item_code %s
		LEFT JOIN `tabItem Price` itp2 ON it.name = itp2.item_code %s
		LEFT JOIN `tabItem Price` itp3 ON it.name = itp3.item_code %s
		LEFT JOIN `tabItem Variant Attribute` bm ON it.name = bm.parent
			AND bm.attribute = 'Base Material'
		LEFT JOIN `tabItem Variant Attribute` quality ON it.name = quality.parent
			AND quality.attribute = '%s Quality'
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
			AND zn.attribute = 'Number of Flutes (Zn)'
		LEFT JOIN `tabItem Variant Attribute` a1 ON it.name = a1.parent
			AND a1.attribute = 'a1_deg'
		LEFT JOIN `tabItem Variant Attribute` purpose ON it.name = purpose.parent
			AND purpose.attribute = 'Purpose'
		LEFT JOIN `tabItem Variant Attribute` type ON it.name = type.parent
			AND type.attribute = 'Type Selector'
		LEFT JOIN `tabItem Variant Attribute` mtm ON it.name = mtm.parent
			AND mtm.attribute = 'Material to Machine'
	
	WHERE
		IFNULL(it.end_of_life, '2099-12-31') > CURDATE() %s
	
	ORDER BY bm.attribute_value, brand.attribute_value,
		quality.attribute_value, tt.attribute_value,
		CAST(d1.attribute_value AS DECIMAL(8,3)) ASC,
		CAST(w1.attribute_value AS DECIMAL(8,3)) ASC,
		CAST(l1.attribute_value AS DECIMAL(8,3)) ASC,
		CAST(zn.attribute_value AS UNSIGNED) ASC,
		CAST(d2.attribute_value AS DECIMAL(8,3)) ASC,
		CAST(l2.attribute_value AS DECIMAL(8,3)) ASC,
		spl.attribute_value""" % (pl1, pl2, pl3, bm, conditions_it)

	data = frappe.db.sql(query, as_list=1)

	return data


def get_conditions(filters):
	conditions_it = ""

	if filters.get("bm"):
		conditions_it += " AND bm.attribute_value = '%s'" % filters["bm"]

	if filters.get("brand"):
		conditions_it += " AND brand.attribute_value = '%s'" % filters["brand"]

	if filters.get("quality"):
		conditions_it += " AND quality.attribute_value = '%s'" % filters["quality"]

	if filters.get("spl"):
		conditions_it += " AND spl.attribute_value = '%s'" % filters["spl"]

	if filters.get("purpose"):
		conditions_it += " AND purpose.attribute_value = '%s'" % filters["purpose"]

	if filters.get("type"):
		conditions_it += " AND type.attribute_value = '%s'" % filters["type"]

	if filters.get("mtm"):
		conditions_it += " AND mtm.attribute_value = '%s'" % filters["mtm"]

	if filters.get("tt"):
		conditions_it += " AND tt.attribute_value = '%s'" % filters["tt"]

	if filters.get("item"):
		conditions_it += " AND it.name = '%s'" % filters["item"]

	if filters.get("template"):
		conditions_it += " AND it.variant_of = '%s'" % filters["template"]

	if filters.get("is_pl") == 1:
		conditions_it += " AND it.pl_item = 'Yes'"
	return conditions_it
