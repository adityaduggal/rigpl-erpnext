# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt
from ....utils.stock_utils import get_wh_wise_qty


def execute(filters=None):
    wh_dict = frappe.db.sql("""SELECT name, listing_serial, short_code, warehouse_type FROM `tabWarehouse`
        WHERE disabled=0 AND is_group=0 AND listing_serial != 0  and is_subcontracting_warehouse = 0
        ORDER BY listing_serial ASC""", as_dict=1)
    columns = get_columns(wh_dict)
    data = get_items(filters, wh_dict)
    return columns, data


def get_columns(wh_dict):
    columns = [
        "Item:Link/Item:120",

        # Item Attribute fields
        "RM::30", "Brand::50", "Series::50", "Qual::50", "SPL::50", "TT::60",
        "D1:Float:40", "W1:Float:40", "L1:Float:50",
        "D2:Float:40", "L2:Float:40", "Zn:Float:40",
        # Item Attribute fields

        "CUT::120", "URG::120",
        "Total:Float:60",
        "RO:Int:40", "SO:Int:40", "PO:Int:40",
        "PL:Int:40", "PRD_RES:Int:40"
    ]

    for wh in wh_dict:
        if wh.listing_serial < 10:
            columns += [wh.short_code + ":Float:50"]
    columns += ["Description::400"]
    for wh in wh_dict:
        if wh.listing_serial >= 10:
            columns += [wh.short_code + ":Float:50"]

    columns += ["JW:Int:30", "Pur:Int:30", "Sale:Int:30"]

    return columns


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
        WHERE ifnull(it.end_of_life, '2099-12-31') > CURDATE() %s
        ORDER BY rm.attribute_value, brand.attribute_value, spl.attribute_value, tt.attribute_value,
            CAST(d1.attribute_value AS DECIMAL(8,3)) ASC, CAST(w1.attribute_value AS DECIMAL(8,3)) ASC,
            CAST(l1.attribute_value AS DECIMAL(8,3)) ASC, CAST(d2.attribute_value AS DECIMAL(8,3)) ASC,
            CAST(l2.attribute_value AS DECIMAL(8,3)) ASC""" % (bm, conditions_it)
    items = frappe.db.sql(query, as_dict=1)
    for d in items:
        d.update({"on_so":0, "on_po":0, "plan":0, "prd":0, "total": 0})
        qty_dict = get_wh_wise_qty(item_name=d.name)
        for q in qty_dict:
            if q.subcon == 1:
                d["on_po"] += flt(q.actual)
            else:
                d["on_po"] += flt(q.on_po)
                d["on_so"] += flt(q.on_so)
                d["prd"] += flt(q.prd)
                d["plan"] += flt(q.plan)
                d[q.scode] = flt(q.actual)
        for wh in wh_dict:
            if wh.warehouse_type != "Recoverable Stock":
                d["total"] += d.get(wh.short_code, 0)
        d = get_urgency(itd=d, whd=wh_dict)
        d["total"] += flt(d.on_po) + flt(d.plan) - flt(d.prd) - flt(d.on_so)
        row = [d.name, d.is_rm, d.brand, d.series, d.qual, d.spl, d.tt, d.d1, d.w1, d.l1, d.d2, d.l2, d.zn,
            d.cut_urg, d.prd_urg, d.total if d.get("total", 0) > 0 else None,
            d.rol if flt(d.get("rol", 0)) > 0 else None,
            d.on_so if flt(d.get("on_so", 0)) > 0 else None, d.on_po if flt(d.get("on_po", 0)) > 0 else None,
            d.plan if flt(d.get("plan", 0)) > 0 else None, d.prd if flt(d.get("prd", 0)) > 0 else None]
        for wh in wh_dict:
            if wh.listing_serial < 10:
                row += [d.get(wh.short_code, 0) if d.get(wh.short_code, 0) > 0 else None]
        row += [d.description]
        for wh in wh_dict:
            if wh.listing_serial >= 10:
                row += [d.get(wh.short_code, 0) if d.get(wh.short_code, 0) > 0 else None]
        row += [d.jw if d.jw > 0 else None, d.pur if d.pur > 0 else None, d.sale if d.sale > 0 else None]
        actual_data.append(row)
    return actual_data

def get_urgency(itd, whd):
    ROL = flt(itd.rol)
    SO = flt(itd.on_so)
    PO = flt(itd.on_po)
    PLAN = flt(itd.plan)
    PRD_RES = flt(itd.prd)
    VR = flt(itd.vr)
    stock = 0
    prd_qty = 0
    dead = 0
    urg = ""
    prd = ""

    if itd.is_rm == 1:
        for wh in whd:
            if wh.warehouse_type == "Raw Material":
                stock += flt(itd.get(wh.short_code))
            elif wh.warehouse_type == "Finished Stock":
                stock += flt(itd.get(wh.short_code))
            elif wh.warehouse_type == "Dead Stock":
                dead += flt(itd.get(wh.short_code))
    else:
        for wh in whd:
            if wh.warehouse_type == "Finished Stock":
                stock += flt(itd.get(wh.short_code))
            elif wh.warehouse_type != "Finished Stock" and wh.warehouse_type != "Recoverable Stock":
                if wh.warehouse_type == "Dead Stock":
                    dead += flt(itd.get(wh.short_code))
                else:
                    prd_qty += flt(itd.get(wh.short_code))
    total = stock + prd_qty + dead + PLAN + PO - PRD_RES

    if 0 <= ROL * VR <= 1000:
        ROL = 5 * ROL
    elif 1000 < ROL * VR <= 2000:
        ROL = 2.5 * ROL
    elif 2000 < ROL * VR <= 5000:
        ROL = 1.5 * ROL

    if dead > 0:
        urg = "Dead Stock"
    elif total < SO:
        if SO > 0:
            urg = "1C ORD"
        else:
            urg = "1C For Production"
    elif total < SO + (0.3 * ROL):
        urg = "2C STK"
    elif total < SO + (0.6 * ROL):
        urg = "3C STK"
    elif total < SO + (1 * ROL):
        urg = "4C STK"
    elif total < SO + (1.4 * ROL):
        urg = "5C STK"
    elif total < SO + (1.8 * ROL):
        urg = "6C STK"
    elif total > (SO + 2.5 * ROL):
        if ROL > 0:
            urg = "7 Over"
        else:
            urg = ""
    else:
        urg = ""

    # Cutting Quantity
    if urg != "":
        c_qty = ((2 * ROL) + SO - total)
        urg = urg + " Qty= " + str(int(c_qty))

    if dead > 0:
        prd = "Dead Stock"
    elif stock < SO:
        if SO > 0:
            prd = "1P ORD"
        else:
            prd = "1P for Production"
    elif stock < SO + ROL:
        prd = "2P STK"
    elif stock < SO + 1.2 * ROL:
        prd = "3P STK"
    elif stock < SO + 1.4 * ROL:
        prd = "4P STK"
    elif stock < SO + 1.6 * ROL:
        prd = "5P STK"
    elif stock < SO + 1.8 * ROL:
        prd = "6P STK"
    elif stock < SO + 2 * ROL:
        prd = "7P STK"
    elif stock > SO + 2.5 * ROL:
        if ROL > 0:
            prd = "9 OVER"
        else:
            prd = ""
    else:
        prd = ""

    # Production Quantity
    if prd != "":
        shortage = (2 * ROL) - stock - dead
        if shortage < prd_qty:
            prd = prd + " Qty= " + str(int(shortage))
        else:
            prd = prd + " Qty = " + str(int(prd_qty))
    itd["cut_urg"] = urg
    itd["prd_urg"] = prd
    return itd


def get_conditions(filters):
    conditions_it = ""

    if filters.get("rm"):
        conditions_it += " AND rm.attribute_value = '%s'" % filters["rm"]

    if filters.get("bm"):
        conditions_it += " AND bm.attribute_value = '%s'" % filters["bm"]

    if filters.get("series"):
        conditions_it += " AND series.attribute_value = '%s'" % filters["series"]

    if filters.get("quality"):
        conditions_it += " AND quality.attribute_value = '%s'" % filters["quality"]

    if filters.get("spl"):
        conditions_it += " AND spl.attribute_value = '%s'" % filters["spl"]

    if filters.get("tt"):
        conditions_it += " AND tt.attribute_value = '%s'" % filters["tt"]

    if filters.get("show_in_website") == 1:
        conditions_it += " and it.show_in_website =%s" % filters["show_in_website"]

    if filters.get("item"):
        conditions_it += " and it.name = '%s'" % filters["item"]

    if filters.get("variant_of"):
        conditions_it += " and it.variant_of = '%s'" % filters["variant_of"]

    return conditions_it
