# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import IfNull, Max
from frappe.utils import cint, flt, nowdate
from ....utils.item_attribute_utils import (
    attribute_filters,
    attribute_sort_key,
    chunks,
    get_attribute_map,
)
from ....utils.stock_utils import get_wh_wise_qty_for_items

TEXT_COLUMNS = [
    ("is_rm", "Is RM"),
    ("brand", "Brand"),
    ("series", "Series"),
    ("spl", "Special Treatment"),
    ("tt", "Tool Type"),
]
NUMERIC_COLUMNS = ["d1", "w1", "l1", "d2", "l2"]
NUMERIC_ATTS = ["d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm"]
ZN_ATT = "Number of Flutes Zn"
SORT_ATTS = ["Is RM", "Brand", "Special Treatment", "Tool Type"] + NUMERIC_ATTS


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
    items = get_item_list(filters)
    names = [d.name for d in items]
    quality = "%s Quality" % filters["bm"]
    attributes = [att for _, att in TEXT_COLUMNS] + [quality, ZN_ATT] + NUMERIC_ATTS
    att_map = get_attribute_map(names, attributes)
    rol_dict = get_reorder_levels(names)
    qty_dicts = get_wh_wise_qty_for_items(names, non_zero=True)
    numeric = set(NUMERIC_ATTS)
    items.sort(key=lambda d: (attribute_sort_key(att_map.get(d.name, {}), SORT_ATTS, numeric), d.name))
    for d in items:
        values = att_map.get(d.name, {})
        for column, attribute in TEXT_COLUMNS + [("qual", quality)]:
            d[column] = values[attribute] if values.get(attribute) is not None else "-"
        for column, attribute in zip(NUMERIC_COLUMNS, NUMERIC_ATTS):
            value = values.get(attribute)
            d[column] = None if value is None else round(flt(value), 3)
        zn = values.get(ZN_ATT)
        d.zn = None if zn is None else cint(zn)
        d.rol = rol_dict.get(d.name) or None
        d.update({"on_so":0, "on_po":0, "plan":0, "prd":0, "total": 0})
        for q in qty_dicts.get(d.name, []):
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


def get_item_list(filters):
    """
    Returns the Items that are not End of Life and match the filters
    """
    it = frappe.qb.DocType("Item")
    query = (
        frappe.qb.from_(it)
        .select(
            it.name,
            it.description,
            it.is_job_work.as_("jw"),
            it.is_purchase_item.as_("pur"),
            it.is_sales_item.as_("sale"),
            it.valuation_rate.as_("vr"),
        )
        .where(IfNull(it.end_of_life, "2099-12-31") > nowdate())
        .where(attribute_filters(it.name, get_attribute_values(filters)))
    )
    if filters.get("show_in_website") == 1:
        query = query.where(it.show_in_website == 1)
    if filters.get("item"):
        query = query.where(it.name == filters["item"])
    if filters.get("variant_of"):
        query = query.where(it.variant_of == filters["variant_of"])
    return query.run(as_dict=True)


def get_reorder_levels(items):
    """
    Returns {item: highest warehouse reorder level}
    """
    ro = frappe.qb.DocType("Item Reorder")
    rol_dict = {}
    for chunk in chunks(items):
        rows = (
            frappe.qb.from_(ro)
            .select(ro.parent, Max(ro.warehouse_reorder_level))
            .where(ro.parent.isin(chunk) & (ro.parenttype == "Item"))
            .groupby(ro.parent)
            .run()
        )
        rol_dict.update(dict(rows))
    return rol_dict


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

    if itd.is_rm == "Yes":
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


def get_attribute_values(filters):
    """
    Returns {attribute: value} for the attribute filters
    """
    return {
        "Is RM": filters.get("rm"),
        "Base Material": filters.get("bm"),
        "Series": filters.get("series"),
        "%s Quality" % filters.get("bm"): filters.get("quality"),
        "Special Treatment": filters.get("spl"),
        "Tool Type": filters.get("tt"),
    }
