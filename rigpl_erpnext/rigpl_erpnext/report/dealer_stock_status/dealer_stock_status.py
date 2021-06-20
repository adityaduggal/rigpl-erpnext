# Copyright (c) 2021, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt
from ....utils.stock_utils import get_wh_wise_qty


def execute(filters=None):
    wh_dict = frappe.db.sql("""SELECT name, listing_serial, short_code, warehouse_type FROM `tabWarehouse`
        WHERE disabled=0 AND is_group=0 AND listing_serial != 0  and is_subcontracting_warehouse = 0
        ORDER BY listing_serial ASC""", as_dict=1)
    columns = get_columns()
    data = get_items(filters, wh_dict)
    return columns, data


def get_columns():
    return [
        "Item:Link/Item:120",

        # Below are attribute fields
        "Series::60", "Qual::50", "SPL::100","TT::150", "D1:Float:50", "W1:Float:50", "L1:Float:60",
        "D2:Float:50", "L2:Float:60", "Zn:Int:40",
        # Above are Attribute fields

        "Description::500", "Ready Stock:Int:100", "WIP:Int:50", "Reserved:Int:80", "Total:Int:100"
    ]


def get_items(filters, wh_dict):
    actual_data = []
    conditions_it = get_conditions(filters)
    bm = filters["bm"]
    query = """SELECT it.name as name, IFNULL(rm.attribute_value, "-") as is_rm, it.description,
        IFNULL(brand.attribute_value, "-") as brand, IFNULL(series.attribute_value, "-") as series,
        IFNULL(quality.attribute_value, "-") as qual, IFNULL(spl.attribute_value, "-") as spl,
        IFNULL(tt.attribute_value, "-") as tt, CAST(d1.attribute_value AS DECIMAL(8,3)) as d1,
        CAST(w1.attribute_value AS DECIMAL(8,3)) as w1, CAST(l1.attribute_value AS DECIMAL(8,3)) as l1,
        CAST(d2.attribute_value AS DECIMAL(8,3)) as d2, CAST(l2.attribute_value AS DECIMAL(8,3)) as l2,
        CAST(zn.attribute_value AS UNSIGNED) as zn, 
        IF(ro.warehouse_reorder_level=0, NULL ,ro.warehouse_reorder_level) AS rol,
        it.is_job_work as jw, it.is_purchase_item as pur, it.is_sales_item as sale, it.valuation_rate as vr
        FROM `tabItem` it
        LEFT JOIN `tabItem Reorder` ro ON it.name = ro.parent
        LEFT JOIN `tabItem Variant Attribute` rm ON it.name = rm.parent AND rm.attribute = 'Is RM'
        LEFT JOIN `tabItem Variant Attribute` bm ON it.name = bm.parent AND bm.attribute = 'Base Material'
        LEFT JOIN `tabItem Variant Attribute` brand ON it.name = brand.parent AND brand.attribute = 'Brand'
        LEFT JOIN `tabItem Variant Attribute` series ON it.name = series.parent AND series.attribute = 'Series'
        LEFT JOIN `tabItem Variant Attribute` quality ON it.name = quality.parent AND quality.attribute = '%s Quality'
        LEFT JOIN `tabItem Variant Attribute` tt ON it.name = tt.parent AND tt.attribute = 'Tool Type'
        LEFT JOIN `tabItem Variant Attribute` spl ON it.name = spl.parent AND spl.attribute = 'Special Treatment'
        LEFT JOIN `tabItem Variant Attribute` d1 ON it.name = d1.parent AND d1.attribute = 'd1_mm'
        LEFT JOIN `tabItem Variant Attribute` w1 ON it.name = w1.parent AND w1.attribute = 'w1_mm'
        LEFT JOIN `tabItem Variant Attribute` l1 ON it.name = l1.parent AND l1.attribute = 'l1_mm'
        LEFT JOIN `tabItem Variant Attribute` d2 ON it.name = d2.parent AND d2.attribute = 'd2_mm'
        LEFT JOIN `tabItem Variant Attribute` l2 ON it.name = l2.parent AND l2.attribute = 'l2_mm'
        LEFT JOIN `tabItem Variant Attribute` zn ON it.name = zn.parent AND zn.attribute = 'Number of Flutes Zn'
        WHERE ifnull(it.end_of_life, '2099-12-31') > CURDATE() AND it.is_sales_item = 1 %s
        ORDER BY rm.attribute_value, brand.attribute_value, spl.attribute_value, tt.attribute_value,
            CAST(d1.attribute_value AS DECIMAL(8,3)) ASC, CAST(w1.attribute_value AS DECIMAL(8,3)) ASC,
            CAST(l1.attribute_value AS DECIMAL(8,3)) ASC, CAST(d2.attribute_value AS DECIMAL(8,3)) ASC,
            CAST(l2.attribute_value AS DECIMAL(8,3)) ASC""" % (bm, conditions_it)
    items = frappe.db.sql(query, as_dict=1)
    for d in items:
        d.update({"res":0, "on_po":0, "plan":0, "prd":0, "total": 0, "ready": 0, "wip": 0})
        qty_dict = get_wh_wise_qty(item_name=d.name)
        for q in qty_dict:
            if q.subcon == 1:
                d["wip"] += flt(q.actual)
            else:
                d["wip"] += flt(q.on_po)
                d["res"] += flt(q.on_so)
                d["res"] += flt(q.prd)
                d["wip"] += flt(q.plan)
                d[q.scode] = flt(q.actual)
        for wh in wh_dict:
            if wh.warehouse_type == "Finished Stock" or wh.warehouse_type == "Dead Stock":
                d["ready"] += d.get(wh.short_code, 0)
            elif wh.warehouse_type != "Recoverable Stock":
            	d["wip"] += d.get(wh.short_code, 0)
        d["total"] += flt(d.ready) + flt(d.wip) - flt(d.res)

        row = [d.name, d.series, d.qual, d.spl, d.tt, d.d1, d.w1, d.l1, d.d2, d.l2, d.zn, d.description,
            d.ready if d.get("ready", 0) > 0 else None, d.wip if d.get("wip", 0) > 0 else None,
            d.res if d.get("res", 0) > 0 else None, d.total if d.get("total", 0) > 0 else None]
        actual_data.append(row)
    return actual_data


def get_conditions(filters):
    conditions_it = ""

    if filters.get("bm"):
        conditions_it += " AND bm.attribute_value = '%s'" % filters["bm"]

    if filters.get("series"):
        conditions_it += " AND series.attribute_value = '%s'" % filters["series"]

    if filters.get("tt"):
        conditions_it += " AND tt.attribute_value = '%s'" % filters["tt"]

    if filters.get("brand"):
        conditions_it += " AND brand.attribute_value = '%s'" % filters["brand"]

    if filters.get("quality"):
        conditions_it += " AND quality.attribute_value = '%s'" % filters["quality"]

    if filters.get("spl"):
        conditions_it += " AND spl.attribute_value = '%s'" % filters["spl"]

    if filters.get("item"):
        conditions_it += " and it.name = '%s'" % filters["item"]

    return conditions_it
