# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cint, flt
from ....utils.item_attribute_utils import attribute_filters, attribute_sort_key, get_attribute_map
from ....utils.report_utils import blank_zeros

TEXT_ATTS = ["Base Material", "Tool Type", "Special Treatment", "Series"]
SIZE_ATTS = ["d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm"]
SORT_ATTS = TEXT_ATTS + SIZE_ATTS
CLOSED_STATUS = ("Stopped", "Completed", "Short Closed")
CLOSED_OP_STATUS = ("Short Closed", "Stopped", "Obsolete")


def execute(filters=None):
    view = get_view(filters)
    columns = get_columns(view)
    data = get_data(view, filters)
    return columns, data


def get_view(filters):
    """
    Returns the checked view (pending, rm_used, process_wise or default) and checks its filters
    """
    views = [view for view in ("pending", "rm_used", "process_wise") if cint(filters.get(view))]
    if len(views) > 1:
        frappe.throw("Maximum 1 Checkbox can be Selected")
    if "rm_used" in views and not filters.get("item"):
        frappe.throw("Please Select the Item Code to Check its Usage as RM")
    if "process_wise" in views and not filters.get("item"):
        frappe.throw("Item Code is Mandatory to Get Process Wise Details")
    return views[0] if views else "default"


def get_columns(view):
    if view == "process_wise":
        columns = [
            "Process Sheet:Link/Process Sheet:100", "Status::80", "Priority:Int:50",
            "Item:Link/Item:120",
            "Operation::120", "Op Plan Qty:Int:50", "Op Comp Qty:Int:50", "Balance:Int:50",
            "Description::500",
            "OP Status::100", "RM Consume:Int:50", "PS Pending:Int:50", "PS Date:Date:80",
            "BT:Link/BOM Template RIGPL:120", "Source::120", "Target::120"
        ]
    elif view == "pending":
        columns = [
            "Process Sheet:Link/Process Sheet:100", "PS Date:Date:90", "Status::80",
            "Priority:Int:50", "Item:Link/Item:120",
            "BM::60", "TT::60", "SPL::60", "Series::40",
            "D1:Float:50", "W1:Float:50", "L1:Float:50", "D2:Float:50", "L2:Float:50", "Qty:Int:50",
            "Comp Qty:Int:50", "Pending Qty:Int:50", "BT:Link/BOM Template RIGPL:80",
            "SO#:Link/Sales Order:200", "Description::500", "Created On:Date:150"
        ]
    elif view == "rm_used":
        columns = [
            "PS#:Link/Process Sheet:120", "PS Date:Date:80", "RM:Link/Item:150",
            "RM Description::300", "Calc Qty:Float:100", "Qty Used:Float:100",
            "Balance Needed:Float:100",
            "From WH:Link/Warehouse:150", "Production Item:Link/Item:150",
            "Prod Item Desc::300", "For Prod Qty:Float:100", "Qty Produced:Float:100"
        ]
    else:
        columns = [
            "Process Sheet:Link/Process Sheet:100", "Status::80", "Priority:Int:50",
            "Item:Link/Item:120",
            "BM::60", "TT::60", "SPL::60", "Series::40",
            "D1:Float:50", "W1:Float:50", "L1:Float:50", "D2:Float:50", "L2:Float:50", "Qty:Int:50",
            "Comp Qty:Int:50", "SC Qty:Int:50", "BT:Link/BOM Template RIGPL:80",
            "SO#:Link/Sales Order:200", "Description::500", "Created On:Date:150"
        ]
    return columns


def get_data(view, filters):
    if view == "process_wise":
        return get_process_wise_data(filters["item"])
    if view == "rm_used":
        return get_rm_used_data(filters["item"])
    return get_attribute_data(filters, pending=view == "pending")


def get_process_wise_data(item):
    ps = frappe.qb.DocType("Process Sheet")
    pso = frappe.qb.DocType("BOM Operation")
    rows = (
        frappe.qb.from_(ps)
        .join(pso)
        .on(pso.parent == ps.name)
        .select(
            ps.name, ps.status, ps.priority, ps.production_item, pso.operation, pso.planned_qty,
            pso.completed_qty, ps.description, pso.status.as_("op_status"),
            pso.allow_consumption_of_rm, ps.quantity, ps.produced_qty, ps.date, ps.bom_template,
            pso.source_warehouse, pso.target_warehouse,
        )
        .where(pso.parenttype == "Process Sheet")
        .where(ps.docstatus != 2)
        .where(ps.production_item == item)
        .orderby(ps.name)
        .orderby(pso.idx)
        .run(as_dict=True)
    )
    data = []
    for d in rows:
        op_balance = flt(d.planned_qty) - flt(d.completed_qty)
        if op_balance <= 0 or d.op_status is None or d.op_status in CLOSED_OP_STATUS:
            op_balance = 0
        row = [
            d.name, d.status, d.priority, d.production_item, d.operation, d.planned_qty,
            d.completed_qty, op_balance, d.description, d.op_status, d.allow_consumption_of_rm,
            max(flt(d.quantity) - flt(d.produced_qty), 0), d.date, d.bom_template,
            d.source_warehouse, d.target_warehouse
        ]
        data.append(blank_zeros(row))
    return data


def get_rm_used_data(item):
    ps = frappe.qb.DocType("Process Sheet")
    rm = frappe.qb.DocType("Process Sheet Items")
    rows = (
        frappe.qb.from_(ps)
        .join(rm)
        .on(rm.parent == ps.name)
        .select(
            ps.name, ps.date, rm.item_code, rm.description.as_("rm_desc"), rm.calculated_qty,
            rm.qty, rm.source_warehouse, ps.production_item, ps.description, ps.quantity,
            ps.produced_qty,
        )
        .where(ps.docstatus == 1)
        .where(ps.status.notin(CLOSED_STATUS))
        .where(rm.parenttype == "Process Sheet")
        .where(rm.parentfield == "rm_consumed")
        .where(rm.donot_consider_rm_for_production == 0)
        .where(rm.qty < rm.calculated_qty)
        .where(rm.item_code == item)
        .orderby(ps.name)
        .orderby(rm.idx)
        .run(as_dict=True)
    )
    data = []
    for d in rows:
        row = [
            d.name, d.date, d.item_code, d.rm_desc, d.calculated_qty, d.qty,
            flt(d.calculated_qty) - flt(d.qty), d.source_warehouse, d.production_item,
            d.description, d.quantity, d.produced_qty
        ]
        data.append(blank_zeros(row))
    return data


def get_attribute_data(filters, pending):
    sheets = get_process_sheets(filters, pending)
    att_map = get_attribute_map([d.production_item for d in sheets], SORT_ATTS)
    numeric = set(SIZE_ATTS)
    sheets.sort(key=lambda d: sort_key(d, att_map.get(d.production_item, {}), numeric))
    data = []
    for d in sheets:
        values = att_map.get(d.production_item, {})
        atts = [values.get(att) for att in TEXT_ATTS] + [size_value(values.get(att)) for att in SIZE_ATTS]
        if pending:
            row = [d.name, d.date, d.status, d.priority, d.production_item] + atts + [
                d.quantity, d.produced_qty, flt(d.quantity) - flt(d.produced_qty), d.bom_template,
                d.sales_order, d.description, d.creation
            ]
        else:
            row = [d.name, d.status, d.priority, d.production_item] + atts + [
                d.quantity, d.produced_qty, d.short_closed_qty, d.bom_template, d.sales_order,
                d.description, d.creation
            ]
        data.append(blank_zeros(row))
    return data


def get_process_sheets(filters, pending):
    """
    Returns the Process Sheets of the pending or the default view that match the filters
    """
    ps = frappe.qb.DocType("Process Sheet")
    query = frappe.qb.from_(ps).select(
        ps.name, ps.date, ps.status, ps.priority, ps.production_item, ps.quantity, ps.produced_qty,
        ps.short_closed_qty, ps.bom_template, ps.sales_order, ps.description, ps.creation,
    )
    if pending:
        query = (
            query.where(ps.docstatus == 1)
            .where(ps.produced_qty < ps.quantity)
            .where(ps.status.notin(CLOSED_STATUS))
        )
    else:
        if cint(filters.get("show_zero_qty")):
            query = query.where(ps.quantity == 0)
        else:
            query = query.where(ps.quantity > 0)
        if filters.get("status"):
            query = query.where(ps.status == filters["status"])
        else:
            query = query.where(ps.docstatus < 2).where(ps.status.notin(CLOSED_STATUS))
    query = query.where(attribute_filters(ps.production_item, get_attribute_values(filters)))
    if filters.get("item"):
        query = query.where(ps.production_item == filters["item"])
    if filters.get("so"):
        query = query.where(ps.sales_order == filters["so"])
    return query.run(as_dict=True)


def get_attribute_values(filters):
    """
    Returns {attribute: value} for the attribute filters
    """
    return {
        "Base Material": filters.get("bm"),
        "Tool Type": filters.get("tt"),
        "Series": filters.get("series"),
        "Special Treatment": filters.get("spl"),
    }


def sort_key(sheet, values, numeric):
    """
    Returns the sort key: priority, attributes (sizes as numbers), item, Sales Order, description
    """
    return (
        cint(sheet.priority),
        attribute_sort_key(values, SORT_ATTS, numeric),
        (sheet.production_item or "").casefold(),
        (sheet.sales_order or "").casefold(),
        (sheet.description or "").casefold(),
        sheet.name,
    )


def size_value(value):
    return None if value is None else round(flt(value), 3)
