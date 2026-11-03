# Copyright (c) 2021, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import IfNull
from frappe.utils import cint, flt, nowdate
from ....utils.item_attribute_utils import attribute_filters, attribute_sort_key, get_attribute_map
from ....utils.stock_utils import get_wh_wise_qty_for_items

TEXT = ["Series", "{bm} Quality", "Special Treatment", "Tool Type"]
NUMERIC = ["d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm"]
FLUTES = "Number of Flutes Zn"
SORT_ORDER = ["Is RM", "Brand", "Special Treatment", "Tool Type", "d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm"]
# filter: attribute
ATTRIBUTE_FILTERS = {"bm": "Base Material", "series": "Series", "tt": "Tool Type", "brand": "Brand",
    "quality": "{bm} Quality", "spl": "Special Treatment"}


def execute(filters=None):
    filters = filters or {}
    if not filters.get("bm"):
        frappe.throw("Select a Base Material", title="Base Material Needed")
    columns = get_columns()
    data = get_items(filters, get_warehouses())
    return columns, data


def get_warehouses():
    """The listed warehouses that are not groups, disabled or subcontracting, by listing serial."""
    wh = frappe.qb.DocType("Warehouse")
    return (
        frappe.qb.from_(wh)
        .select(wh.name, wh.listing_serial, wh.short_code, wh.warehouse_type)
        .where((wh.disabled == 0) & (wh.is_group == 0) & (wh.listing_serial != 0)
            & (wh.is_subcontracting_warehouse == 0))
        .orderby(wh.listing_serial)
        .run(as_dict=1)
    )


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
    """
    The sales items of the filters with their stock. The attributes come from get_attribute_map
    and the quantities from get_wh_wise_qty_for_items, in place of 13 self-joins and 1 stock query
    for each item (#187).
    """
    bm = filters["bm"]
    text = [att.format(bm=bm) for att in TEXT]
    items = get_item_rows(filters, bm)
    names = [d.name for d in items]
    att_map = get_attribute_map(names, text + NUMERIC + [FLUTES, "Is RM", "Brand"])
    items.sort(key=lambda d: attribute_sort_key(att_map.get(d.name, {}), SORT_ORDER, set(NUMERIC)))
    qty_by_item = get_wh_wise_qty_for_items(names)
    actual_data = []
    for d in items:
        values = att_map.get(d.name, {})
        ready, wip, res = get_stock(qty_by_item.get(d.name, []), wh_dict)
        total = ready + wip - res
        row = [d.name] + [values.get(att) or "-" for att in text] \
            + [flt(values[att], 3) if values.get(att) is not None else None for att in NUMERIC] \
            + [cint(flt(values[FLUTES])) if values.get(FLUTES) is not None else None, d.description,
            ready if ready > 0 else None, wip if wip > 0 else None, res if res > 0 else None,
            total if total > 0 else None]
        actual_data.append(row)
    return actual_data


def get_stock(qty_rows, wh_dict):
    """(ready, wip, reserved) of 1 item from its Bin rows and the listed warehouses."""
    wip = res = 0
    actual_by_code = {}
    for q in qty_rows:
        if q.subcon == 1:
            wip += flt(q.actual)
        else:
            wip += flt(q.on_po) + flt(q.plan)
            res += flt(q.on_so) + flt(q.prd)
            actual_by_code[q.scode] = flt(q.actual)
    ready = 0
    for wh in wh_dict:
        if wh.warehouse_type in ("Finished Stock", "Dead Stock"):
            ready += actual_by_code.get(wh.short_code, 0)
        elif wh.warehouse_type != "Recoverable Stock":
            wip += actual_by_code.get(wh.short_code, 0)
    return ready, wip, res


def get_item_rows(filters, bm):
    it = frappe.qb.DocType("Item")
    query = (
        frappe.qb.from_(it)
        .select(it.name, it.description)
        .where((IfNull(it.end_of_life, "2099-12-31") > nowdate()) & (it.is_sales_item == 1))
        .where(attribute_filters(it.name, {ATTRIBUTE_FILTERS[key].format(bm=bm): filters.get(key)
            for key in ATTRIBUTE_FILTERS}))
        .orderby(it.name)
    )
    if filters.get("item"):
        query = query.where(it.name == filters["item"])
    return query.run(as_dict=1)
