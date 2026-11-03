# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import IfNull
from frappe.utils import flt, nowdate
from pypika.terms import Case
from ....utils.item_attribute_utils import attribute_filters, attribute_sort_key, get_attribute_map
from ....utils.lead_time_utils import get_detailed_manuf_lead_time_for_item, get_items_lead_time
from ....utils.purchase_utils import get_detailed_po_lead_time_for_item


def execute(filters=None):
    if not filters:
        filters = {}
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data


def get_columns(filters):
    if filters.get("detail") == 1:
        return [
            "Item:Link/Item:130",
            {
                "label": "Avg Based On",
                "fieldname": "based_on",
                "width": 10
            },
            {
                "label": "Trans #",
                "fieldname": "link_name",
                "fieldtype": "Dynamic Link",
                "options": "based_on",
                "width": 120
            },
            "Trans Date:Date:100", "S No Trans:Int:50", "Qty Trans:Float:100",
            "Curr Lead:Int:80", "Min Days Trans:Int:80", "Max Days Trans:Int:80", "Avg Days:Int:80",
            "Trans Weight:Int:80", "No of Sub Trans:Int:80",
            {
                "label": "Sub Trans Type",
                "fieldname": "sub_trans_type",
                "width": 10
            },
            {
                "label": "Sub Trans #",
                "fieldname": "sub_link_name",
                "fieldtype": "Dynamic Link",
                "options": "sub_trans_type",
                "width": 120
            },
            "Date Sub Trans:Date:80", "Qty Sub Trans:Float:80",
            "Days Sub Trans:Int:80", "Wt Sub Trans:Int:80","Description::450"
        ]
    else:
        return [
                "Item:Link/Item:130", "ROL:Int:60", "Avg Based On::90",
                "# Transactions:Int:80", "Total Qty:Float:80", "Min Days:Int:80",
                "Max Days:Int:80", "Current Lead Time:Int:80", "Calculated Lead Time:Int:80",
                "Lead Time Diff:Int:80",
                "BM::60", "Brand::60", "Quality::60", "TT::130", "SPL::50",
                "D1 MM:Float:50", "W1 MM:Float:50", "L1 MM:Float:60",
                "D2 MM:Float:50", "L2 MM:Float:60",
                "Description::450", "Template:Link/Item:150"
        ]


TEXT = ["Base Material", "Brand", "{bm} Quality", "Tool Type", "Special Treatment"]
NUMERIC = ["d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm"]
SORT_ORDER = ["Base Material", "{bm} Quality", "Tool Type", "d1_mm", "w1_mm", "d2_mm", "l2_mm"]
# filter: attribute
ATTRIBUTE_FILTERS = {"rm": "Is RM", "bm": "Base Material", "brand": "Brand", "quality": "{bm} Quality",
    "tt": "Tool Type"}


def get_data(filters):
    if filters.get("detail") == 1:
        if not filters.get("item"):
            frappe.throw("Please Select Item Code to Get Transaction Wise Details", title="Item Needed")
        return get_detail(filters)
    return get_summary(filters)


def get_detail(filters):
    data = []
    itd = frappe.get_doc("Item", filters.get("item"))
    if itd.include_item_in_manufacturing == 1:
        ld_dt = get_detailed_manuf_lead_time_for_item(itd.name, frm_dt=filters.get("from_date"),
            to_dt=filters.get("to_date"))
    else:
        ld_dt = get_detailed_po_lead_time_for_item(itd.name, frm_dt=filters.get("from_date"),
            to_dt=filters.get("to_date"))
    for ldt in ld_dt:
        base_row = [
            itd.name, ldt.based_on, ldt.trans_name, ldt.calc_trans_date, ldt.idx, ldt.trans_qty,
            itd.lead_time_days, ldt.trans_min_days, ldt.trans_max_days, ldt.trans_avg_days,
            ldt.trans_wt, len(ldt.sub_trans)
        ]
        for sub in ldt.sub_trans:
            data.append(base_row + [sub.sub_trans_type, sub.sub_trans_name, sub.sub_trans_date,
                sub.sub_trans_qty, sub.days_diff, sub.sub_trans_wt, itd.description])
    return data


def get_summary(filters):
    """
    The items of the filters with their lead times. The attributes come from get_attribute_map
    (#131, #187), in place of 13 self-joins, and the lead times from get_items_lead_time.
    """
    bm = filters.get("bm") or ""
    text = [att.format(bm=bm) for att in TEXT]
    items = get_item_rows(filters, bm)
    att_map = get_attribute_map([itm.name for itm in items], text + NUMERIC)
    items.sort(key=lambda itm: attribute_sort_key(att_map.get(itm.name, {}),
        [att.format(bm=bm) for att in SORT_ORDER], set(NUMERIC)))
    lead_times = get_items_lead_time([itm.name for itm in items], frm_dt=filters.get("from_date"),
        to_dt=filters.get("to_date"))
    data = []
    for itm in items:
        calc = lead_times[itm.name]
        values = att_map.get(itm.name, {})
        avg_days = calc.get("avg_days_wt", 0)
        lead = itm.lead_time_days or 0
        data.append([itm.name, itm.rol, calc["based_on"], calc["no_of_trans"], calc.get("total_qty", 0),
            calc.get("min_days", 0), calc.get("max_days", 0), lead, avg_days, avg_days - lead] + [values.get(att) or "-" for att in text]
            + [flt(values[att], 3) if values.get(att) is not None else None for att in NUMERIC]
            + [itm.description, itm.variant_of])
    return data


def get_item_rows(filters, bm):
    it = frappe.qb.DocType("Item")
    ro = frappe.qb.DocType("Item Reorder")
    rol = Case().when(ro.warehouse_reorder_level == 0, None).else_(ro.warehouse_reorder_level)
    query = (
        frappe.qb.from_(it)
        .left_join(ro).on(ro.parent == it.name)
        .select(it.name, rol.as_("rol"), it.lead_time_days, it.description, it.variant_of)
        .where(IfNull(it.end_of_life, "2099-12-31") > nowdate())
        .where(attribute_filters(it.name, {ATTRIBUTE_FILTERS[key].format(bm=bm): filters.get(key)
            for key in ATTRIBUTE_FILTERS}))
        .orderby(it.name)
    )
    if filters.get("item"):
        query = query.where(it.name == filters["item"])
    return query.run(as_dict=1)
