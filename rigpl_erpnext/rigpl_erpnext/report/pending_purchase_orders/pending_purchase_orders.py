#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt
from ....utils.stock_utils import get_quantities_for_item
from ....utils.other_utils import auto_round_up


def execute(filters=None):
    conditions = get_conditions(filters)
    columns = get_columns(filters)
    data = get_items(filters, conditions)

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


def get_items(filters, conditions):
    tbl_join = ""
    if filters.get("subcontracting") == 1:
        item_field = "subcontracted_item"
    else:
        item_field = "item_code"
    if filters.get("bm"):
        conditions += " AND bm.attribute_value = '%s'" % filters["bm"]
        tbl_join += " LEFT JOIN `tabItem Variant Attribute` bm ON pod.%s = bm.parent " \
                    "AND bm.attribute = 'Base Material'" % item_field

    if filters.get("subcontracting") == 1:
        query = """SELECT po.name, po.transaction_date, pod.schedule_date, po.supplier, pod.subcontracted_item,
        pod.description, (pod.qty - pod.received_qty) as pend_qty, pod.qty, pod.returned_qty,
        pod.stock_uom, pod.base_rate, IF(pod.conversion_factor != 1, pod.conversion_factor, NULL) as con_fac,
        pod.reference_dn FROM `tabPurchase Order` po
        LEFT JOIN `tabPurchase Order Item` pod ON pod.parent = po.name %s
        WHERE po.docstatus = 1 AND po.status != 'Closed' AND IFNULL(pod.received_qty,0) < IFNULL(pod.qty,0) %s
        ORDER BY po.transaction_date, pod.schedule_date""" % (tbl_join, conditions)
        data = frappe.db.sql(query, as_list=1)
    else:
        query = """SELECT po.name, po.transaction_date, pod.schedule_date, po.supplier, pod.item_code, pod.description,
        (pod.qty - pod.received_qty) as pend_qty, pod.qty, pod.returned_qty, pod.stock_uom, pod.base_rate, "Urgent"
        FROM `tabPurchase Order` po, `tabPurchase Order Item` pod %s
        WHERE po.docstatus = 1 AND po.name = pod.parent AND po.status != 'Closed'
        AND IFNULL(pod.received_qty,0) < IFNULL(pod.qty,0) %s
        ORDER BY po.transaction_date, pod.schedule_date""" % (tbl_join, conditions)
        data_dict = frappe.db.sql(query, as_dict=1)
        data = []
        for d in data_dict:
            itd = frappe.get_doc("Item", d.item_code)
            qd = get_quantities_for_item(itd)
            calc_rol = flt(d.calculated_rol)
            cur_stk = flt(qd.raw_material_qty) + flt(qd.dead_qty) + flt(qd.finished_qty) + flt(qd.wip_qty) - \
                          flt(qd.on_so) - flt(qd.reserved_for_prd)
            months = cur_stk / (flt(qd.calculated_rol) + 1)
            if d.pend_qty / d.qty >= 0.1:
                if months < 0:
                    urg = "Needed Now"
                    shortfall = auto_round_up(cur_stk * (-1) + int(calc_rol))
                elif months < 1:
                    urg = "Needed in Next 15~30 Days"
                    shortfall = auto_round_up(calc_rol)
                elif months < 1.5:
                    urg = "Need in Next 30~45 Days"
                    shortfall = auto_round_up(calc_rol)
                elif months < 2:
                    urg = "Needed in Next 45~60 Days"
                    shortfall = auto_round_up(calc_rol)
                else:
                    urg = "Needed After 60 Days"
                    shortfall = auto_round_up(calc_rol)
            else:
                urg = "Can be Short Closed"
                shortfall = 0
            d["urgency"] = urg
            d["shortfall"] = shortfall
        for i in data_dict:
            row = [
                i.name, i.transaction_date, i.schedule_date, i.supplier, i.item_code, i.description, i.pend_qty,
                i.qty, i.returned_qty, i.stock_uom, i.base_rate, i.urgency, i.shortfall
            ]
            data.append(row)
    return data


def get_conditions(filters):
    conditions = ""

    if filters.get("subcontracting") == 1:
        conditions += " AND po.is_subcontracting = 1"
    else:
        conditions += " AND po.is_subcontracting = 0"

    if filters.get("item"):
        conditions += " AND pod.item_code = '%s'" % filters["item"]

    if filters.get("supplier"):
        conditions += " AND po.supplier = '%s'" % filters["supplier"]

    if filters.get("date"):
        conditions += " AND po.transaction_date <= '%s'" % filters["date"]
    return conditions
