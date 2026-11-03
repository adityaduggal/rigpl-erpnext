#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import IfNull
from frappe.utils import cint, flt
from ....utils.item_attribute_utils import attribute_filters, chunks
from ....utils.other_utils import auto_round_up
from ....utils.report_utils import blank_zeros
from ....utils.stock_utils import get_quantities_for_items


def execute(filters=None):
    columns = get_columns(filters)
    data = get_items(filters)

    return columns, data


def get_columns(filters):
    if filters.get("subcontracting") == 1:
        return [
            "PO# :Link/Purchase Order:120", "PO Date:Date:80",
            "SCH Date:Date:80", "Supplier:Link/Supplier:200", "Item Code:Link/Item:120",
            "Description::280", "Pend Qty:Float:60", "Ordered Qty:Float:60", "Rejected Qty:Float:60",
            "UoM::50", "Price:Currency:80", "Item Qty:Float:100", "JC#:Link/Process Job Card RIGPL:80"
        ]
    else:
        return [
            "PO# :Link/Purchase Order:120", "PO Date:Date:80",
            "SCH Date:Date:80", "Supplier:Link/Supplier:200", "Item Code:Link/Item:120",
            "Description::280", "Pend Qty:Float:60", "Ordered Qty:Float:60", "Rejected Qty:Float:60",
            "UoM::50", "Price:Currency:80", "Urgency::200", "Min Qty:Float:80"
        ]


def get_items(filters):
    """
    The pending PO rows of the filters. A normal PO row also gets the urgency from the stock of
    its item, read for all items at once (#187).
    """
    subcontracting = cint(filters.get("subcontracting")) == 1
    rows = get_po_rows(filters, subcontracting)
    if subcontracting:
        return [blank_zeros([
            row.name, row.transaction_date, row.schedule_date, row.supplier, row.subcontracted_item,
            row.description, row.pend_qty, row.qty, row.returned_qty, row.stock_uom, row.base_rate,
            row.conversion_factor if flt(row.conversion_factor) != 1 else None, row.reference_dn
        ]) for row in rows]
    qty_by_item = get_item_quantities({row.item_code for row in rows})
    data = []
    for row in rows:
        urgency, shortfall = get_urgency(row, qty_by_item.get(row.item_code) or frappe._dict())
        data.append(blank_zeros([
            row.name, row.transaction_date, row.schedule_date, row.supplier, row.item_code, row.description,
            row.pend_qty, row.qty, row.returned_qty, row.stock_uom, row.base_rate, urgency, shortfall
        ]))
    return data


def get_po_rows(filters, subcontracting):
    """The submitted PO rows that are not closed and not fully received."""
    po = frappe.qb.DocType("Purchase Order")
    pod = frappe.qb.DocType("Purchase Order Item")
    item_field = pod.subcontracted_item if subcontracting else pod.item_code
    query = (
        frappe.qb.from_(po).join(pod).on(pod.parent == po.name)
        .select(po.name, po.transaction_date, pod.schedule_date, po.supplier, pod.item_code,
            pod.subcontracted_item, pod.description, (pod.qty - pod.received_qty).as_("pend_qty"), pod.qty,
            pod.returned_qty, pod.stock_uom, pod.base_rate, pod.conversion_factor, pod.reference_dn)
        .where((po.docstatus == 1) & (po.status != "Closed"))
        .where(po.is_subcontracting == (1 if subcontracting else 0))
        .where(IfNull(pod.received_qty, 0) < IfNull(pod.qty, 0))
        .where(attribute_filters(item_field, {"Base Material": filters.get("bm")}))
        .orderby(po.transaction_date).orderby(pod.schedule_date).orderby(po.name).orderby(pod.idx)
    )
    if filters.get("item"):
        query = query.where(pod.item_code == filters["item"])
    if filters.get("supplier"):
        query = query.where(po.supplier == filters["supplier"])
    if filters.get("date"):
        query = query.where(po.transaction_date <= filters["date"])
    return query.run(as_dict=1)


def get_item_quantities(items):
    """{item: qty_dict of get_quantities_for_items}"""
    item_rows = []
    for chunk in chunks(items):
        item_rows += frappe.get_all("Item", filters={"name": ["in", chunk]},
            fields=["name", "made_to_order", "valuation_rate", "lead_time_days"])
    return get_quantities_for_items(item_rows)


def get_urgency(row, qd):
    """(urgency, shortfall) of a PO row from the stock of its item"""
    calc_rol = flt(qd.calculated_rol)
    cur_stk = flt(qd.raw_material_qty) + flt(qd.dead_qty) + flt(qd.finished_qty) + flt(qd.wip_qty) - \
        flt(qd.on_so) - flt(qd.reserved_for_prd)
    months = cur_stk / (calc_rol + 1)
    if row.pend_qty / row.qty < 0.1:
        return "Can be Short Closed", 0
    if months < 0:
        return "Needed Now", auto_round_up(cur_stk * (-1) + int(calc_rol))
    if months < 1:
        urgency = "Needed in Next 15~30 Days"
    elif months < 1.5:
        urgency = "Need in Next 30~45 Days"
    elif months < 2:
        urgency = "Needed in Next 45~60 Days"
    else:
        urgency = "Needed After 60 Days"
    return urgency, auto_round_up(calc_rol)
