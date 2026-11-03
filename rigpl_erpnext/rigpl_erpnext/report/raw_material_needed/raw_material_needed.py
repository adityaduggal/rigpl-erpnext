# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import IfNull, Sum
from frappe.utils import cint, flt, nowdate
from pypika.terms import Case
from ....utils.item_attribute_utils import attribute_filters, attribute_sort_key, chunks, get_attribute_map
from ....utils.report_utils import blank_zeros
from ....utils.stock_utils import get_first_reorder_levels

TEXT = ["Is RM", "Brand", "{bm} Quality", "Special Treatment", "Tool Type"]
NUMERIC = ["d1_mm", "w1_mm", "l1_mm"]
SORT_ORDER = ["Is RM", "Brand", "Special Treatment", "Tool Type", "d1_mm", "w1_mm", "l1_mm"]
# filter: attribute
ATTRIBUTE_FILTERS = {"rm": "Is RM", "bm": "Base Material", "brand": "Brand", "quality": "{bm} Quality",
    "spl": "Special Treatment", "tt": "Tool Type"}
# Bin sums: column
BIN_FIELDS = {"so": "reserved_qty", "po": "ordered_qty", "plan": "planned_qty", "indent": "indented_qty",
    "prd": "reserved_qty_for_production"}
# actual qty of a warehouse: column
WAREHOUSES = {"brm": "RM-BGH655 - RIGPL", "drm": "RM-DEL20A - RIGPL", "bgh": "BGH655 - RIGPL",
    "del20a": "DEL20A - RIGPL", "dead": "Dead Stock - RIGPL"}
BANDS = ["1<30 Days", "2<60 Days", "3<90 Days", "4<120 Days", "5<150 Days", "6<180 Days"]

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_items(filters)

    return columns, data

def get_columns():
    return [
            "Item:Link/Item:130",
            ###Below are attribute fields
            "RM::30", "Brand::60", "Qual::80", "SPL::50", "TT::120",
            "D1:Float:50", "W1:Float:50", "L1:Float:50",
            ###Above are Attribute fields
            "Future Stock::100", "Current Stock::100",
            "Lead Time:Int:50", "Total:Float:50",
            "RO:Float:40", "SO:Float:40", "PO:Float:40",
            "PL:Float:40", "IND:Float:50", "PRD:Float:50",
            "Description::300",
            "BRM:Float:50", "DRM:Float:50", "BGH:Float:50", "DEL:Float:50",
            "Dead:Float:50",
    ]

def get_items(filters):
    """
    The purchase items of the filters that have Bins, with their stock and the stock bands. The
    attributes come from get_attribute_map and the stock from grouped Bin queries (#187), in place
    of 10 self-joins.
    """
    bm = filters.get("bm")
    if not bm:
        frappe.throw("Select a Base Material", title="Base Material Needed")
    text = [att.format(bm=bm) for att in TEXT]
    items = get_item_rows(filters, bm)
    names = [it.name for it in items]
    stock = get_stock(names)
    rol_by_item = {}
    for chunk in chunks(names):
        rol_by_item.update(get_first_reorder_levels(chunk))
    att_map = get_attribute_map(names, text + NUMERIC)
    items.sort(key=lambda it: attribute_sort_key(att_map.get(it.name, {}), SORT_ORDER, set(NUMERIC)))
    actual_data = []
    for it in items:
        qty = stock.get(it.name, {})
        values = att_map.get(it.name, {})
        rol = flt(rol_by_item.get(it.name))
        so, po, plan, ind, prd = (flt(qty.get(key)) for key in BIN_FIELDS)
        brm, drm, bgh, del20a, dead = (flt(qty.get(key)) for key in WAREHOUSES)

        total = (drm + brm + plan + po + ind + bgh + del20a + dead) - prd
        stock_qty = drm + brm + bgh + del20a + dead - prd
        calc_rol = get_calc_rol(rol)
        fut_stock = "Raise More PO and Indent" if total < so else get_stock_band(total, so, calc_rol, rol)
        cur_stock = "NO STOCK" if stock_qty < calc_rol else get_stock_band(stock_qty, so, calc_rol, rol)

        actual_data.append(blank_zeros(
            [it.name] + [values.get(att) or "-" for att in text]
            + [flt(values[att], 3) if values.get(att) is not None else None for att in NUMERIC]
            + [fut_stock, cur_stock, it.lead_time_days, total, rol, so, po, plan, ind, prd, it.description,
            brm, drm, bgh, del20a, dead]
        ))

    return actual_data


def get_calc_rol(rol):
    if rol < 10:
        return 3*rol
    elif 10 <= rol < 20:
        return 2*rol
    elif 20 <= rol < 50:
        return 1.5*rol
    return rol


def get_stock_band(qty, so, calc_rol, rol):
    """The months of stock that `qty` covers after the sales orders, at `calc_rol` each month."""
    for months, band in enumerate(BANDS, start=1):
        if qty < so + months*calc_rol:
            return band
    if qty > so + 6*calc_rol and rol > 0:
        return "7 Over Stocked >180 Days"
    return "-"


def get_item_rows(filters, bm):
    """The enabled purchase items that are not templates or end of life, have Bins and the filters."""
    it = frappe.qb.DocType("Item")
    bn = frappe.qb.DocType("Bin")
    query = (
        frappe.qb.from_(it)
        .select(it.name, it.lead_time_days, it.description)
        .where((it.is_purchase_item == 1) & (it.has_variants == 0) & (it.disabled == 0))
        .where(IfNull(it.end_of_life, "2099-12-31") > nowdate())
        .where(it.name.isin(frappe.qb.from_(bn).select(bn.item_code)))
        .where(attribute_filters(it.name, {ATTRIBUTE_FILTERS[key].format(bm=bm): filters.get(key)
            for key in ATTRIBUTE_FILTERS}))
        .orderby(it.name)
    )
    if cint(filters.get("show_in_website")) == 1:
        query = query.where(it.pl_item == 1)
    if filters.get("item"):
        query = query.where(it.name == filters["item"])
    if filters.get("variant_of"):
        query = query.where(it.variant_of == filters["variant_of"])
    return query.run(as_dict=1)


def get_stock(items):
    """{item: {column: qty}} of the Bin sums and the actual qty of each warehouse in WAREHOUSES"""
    bn = frappe.qb.DocType("Bin")
    sums = [Sum(getattr(bn, field)).as_(key) for key, field in BIN_FIELDS.items()]
    actual = [Sum(Case().when(bn.warehouse == warehouse, bn.actual_qty).else_(0)).as_(key)
        for key, warehouse in WAREHOUSES.items()]
    stock = {}
    for chunk in chunks(items):
        rows = frappe.qb.from_(bn).select(bn.item_code, *sums, *actual).where(bn.item_code.isin(chunk)) \
            .groupby(bn.item_code).run(as_dict=1)
        stock.update({row.item_code: row for row in rows})
    return stock
