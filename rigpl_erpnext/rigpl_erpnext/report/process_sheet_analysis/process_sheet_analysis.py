# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe


def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data


def get_columns(filters):
    columns = [
        "Process Sheet:Link/Process Sheet:100", "Status::80", "Priority:Int:50", "Item:Link/Item:120",
        "BM::60", "TT::60", "SPL::60", "Series::40",
        "D1:Float:50", "W1:Float:50", "L1:Float:50", "D2:Float:50", "L2:Float:50", "Qty:Int:50",
        "Comp Qty:Int:50", "SC Qty:Int:50", "BT:Link/BOM Template RIGPL:80",
        "ROL:Int:50", "SO:Int:50", "PO:Int:50", "Plan:Int:50", "PRD:Int:50", "ACT:Int:50",
        "Description::500"
    ]
    return columns


def get_data(filters):
    conditions_it, conditions_ps = get_conditions (filters)
    query = """SELECT ps.name, ps.status, ps.priority, ps.production_item, bm.attribute_value, tt.attribute_value,
    spl.attribute_value, ser.attribute_value, d1.attribute_value, w1.attribute_value, l1.attribute_value,
    d2.attribute_value, l2.attribute_value, ps.quantity, IF(ps.produced_qty=0, NULL,ps.produced_qty), 
    IF(ps.short_closed_qty=0, NULL, ps.short_closed_qty), 
    ps.bom_template,
    IF(ro.warehouse_reorder_level=0, NULL ,ro.warehouse_reorder_level) AS rol,
    IF(bn.on_so=0, NULL ,bn.on_so) AS on_so,
    IF(bn.on_po=0, NULL ,bn.on_so) AS on_po,
    IF(bn.plan=0, NULL ,bn.plan) AS plan,
    IF(bn.prod=0, NULL ,bn.prod) AS prod,
    IF(bn.act=0, NULL ,bn.act) AS act, ps.description
    FROM `tabProcess Sheet` ps 
    LEFT JOIN `tabItem` it ON it.name = ps.production_item
    LEFT JOIN `tabItem Reorder` ro ON ps.production_item = ro.parent
    LEFT JOIN (SELECT item_code, SUM(reserved_qty) as on_so, SUM(ordered_qty) as on_po, SUM(actual_qty) as act,
    	SUM(planned_qty) as plan, SUM(reserved_qty_for_production) as prod, SUM(indented_qty) as indent
    	FROM `tabBin` GROUP BY item_code) bn 
    	ON ps.production_item = bn.item_code
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
    WHERE ps.docstatus < 3 %s %s
    ORDER BY ps.priority, bm.attribute_value, tt.attribute_value, spl.attribute_value, ser.attribute_value,
    d1.attribute_value, w1.attribute_value, l1.attribute_value, d2.attribute_value, l2.attribute_value,
    ps.production_item, ps.sales_order, ps.description""" % (conditions_ps, conditions_it)
    data = frappe.db.sql(query, as_list=1)
    return data


def get_conditions(filters):
    conditions_it = ""
    conditions_ps = ""

    if filters.get("status"):
        conditions_ps += " AND ps.status = '%s'" % filters.get("status")
    else:
        conditions_ps += " AND ps.docstatus < 2 AND ps.status != 'Stopped' AND ps.status != 'Completed' " \
                         "AND status != 'Short Closed'"

    if filters.get("bm"):
        conditions_it += " AND bm.attribute_value = '%s'" % filters.get("bm")

    if filters.get("tt"):
        conditions_it += " AND tt.attribute_value = '%s'" % filters.get("tt")

    if filters.get("series"):
        conditions_it += " AND ser.attribute_value = '%s'" % filters.get("series")

    if filters.get("spl"):
        conditions_it += " AND spl.attribute_value = '%s'" % filters.get("spl")

    if filters.get("item"):
        conditions_it += " and it.name = '%s'" % filters.get("item")

    if filters.get("so"):
        conditions_it += " and ps.sales_order = '%s'" % filters.get("so")

    return conditions_it, conditions_ps
