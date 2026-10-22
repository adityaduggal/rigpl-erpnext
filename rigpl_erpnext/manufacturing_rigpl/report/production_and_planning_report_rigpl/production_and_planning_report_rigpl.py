# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.query_builder.functions import CustomFunction, IfNull, Sum
from frappe.utils import cint, flt, getdate, nowdate
from pypika.terms import Criterion

from ....manufacturing_rigpl.utils.job_card_utils import get_last_jc_for_so_items
from ....utils.item_attribute_utils import (
    attribute_filters,
    attribute_sort_key,
    chunks,
    get_attribute_map,
)
from ....utils.report_utils import blank_zeros

Round = CustomFunction("ROUND", ["value", "digits"])

VIEWS = ("mach_eff", "summary", "production_planning", "order_wise_summary", "op_time_analysis")
SIZE_ATTS = ["d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm"]
ATTS = ["Base Material", "Tool Type", "Special Treatment", "Series"] + SIZE_ATTS
PLANNING_SORT_ATTS = ATTS[:7]
OP_TIME_ATTS = ["Base Material", "Tool Type", "Series"] + SIZE_ATTS


def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data


def get_columns(filters):
    if filters.get("summary") == 1:
        return [
            "Employee Name::150",
            "Workstation:Link/Workstation:150",
            "Item Code:Link/Item:100",
            "Description::300",
            "Planned Qty:Float:100",
            "Completed Qty:Float:100",
            "Rejected Qty:Float:100",
            "Operation::200",
            "Total Time (mins):Float:80",
            "Time Per Pc:Float:80",
            "JC#:Link/Process Job Card RIGPL:100",
        ]
    elif filters.get("production_planning") == 1:
        return [
            {
                "label": "JC#",
                "fieldname": "name",
                "fieldtype": "Link",
                "options": "Process Job Card RIGPL",
                "hidden": 0,
                "width": 100,
            },
            "Status::60",
            "RM Status:Percent:50",
            "RM Shortage:Int:80",
            "SO#:Link/Sales Order:150",
            "Item:Link/Item:120",
            "Priority:Int:50",
            "Remarks::100",
            "BM::60",
            "TT::60",
            "SPL::60",
            "Series::60",
            "D1:Float:50",
            "W1:Float:50",
            "L1:Float:50",
            "D2:Float:50",
            "L2:Float:50",
            "Description::400",
            "Operation:Link/Operation:100",
            "Allocated Machine:Link/Workstation:150",
            "Total Planned:Float:80",
            "Planned Qty:Float:80",
            "Qty Avail:Float:80",
            "Creation:Datetime:120",
        ]
    elif filters.get("order_wise_summary") == 1:
        return [
            "SO#:Link/Sales Order:150",
            "SO Date:Date:80",
            "Item:Link/Item:120",
            "Description::450",
            "Pending:Float:60",
            "Ordered:Float:60",
            "JC#:Link/Process Job Card RIGPL:80",
            "PS#::150",
            "Status::60",
            "Operation:Link/Operation:100",
            "Priority:Int:50",
            "Planned Qty:Float:80",
            "Qty Avail:Float:80",
            "Remarks::400",
        ]
    elif filters.get("op_time_analysis") == 1:
        return [
            "Posting Date:Date:80",
            "Employee Name::150",
            "Workstation:Link/Workstation:150",
            "Item Code:Link/Item:100",
            "BM::60",
            "TT::60",
            "Series::60",
            "D1:Float:50",
            "W1:Float:50",
            "L1:Float:50",
            "D2:Float:50",
            "L2:Float:50",
            "Planned Qty:Float:100",
            "Completed Qty:Float:100",
            "Rejected Qty:Float:100",
            "Operation::200",
            "Total Time (mins):Float:80",
            "Time Per Pc:Float:80",
            "Cost Per Pc:Currency:100",
            "JC#:Link/Process Job Card RIGPL:100",
            "Description::300",
        ]
    elif filters.get("mach_eff") == 1:
        if filters.get("mach_eff_type") == "Total":
            return [
                "Workstation:Link/Workstation:150",
                "Total Days:Int:80",
                "Total Hours:Int:100",
                "Hours Worked:Float:100",
                "Efficiency:Percent:100",
                "Disabled:Int:50",
            ]
        else:
            return [
                "Workstation:Link/Workstation:150",
                "Date:Date:80",
                "Total Hours:Int:100",
                "Hours Worked:Float:100",
                "Efficiency:Percent:100",
                "Disabled:Int:50",
            ]
    else:
        frappe.throw("Select one of the Check Boxes.")


def get_data(filters):
    view = get_view(filters)
    if view == "summary":
        return get_summary_data(filters, view)
    if view == "production_planning":
        return get_planning_data(filters, view)
    if view == "order_wise_summary":
        return get_order_wise_data(filters)
    if view == "op_time_analysis":
        return get_op_time_data(filters, view)
    return get_machine_efficiency_data(filters, view)


def get_view(filters):
    """
    Returns the checked view and checks its mandatory filters
    """
    views = [view for view in VIEWS if cint(filters.get(view))]
    if not views:
        frappe.throw("One checkbox is needed to be checked")
    elif len(views) > 1:
        frappe.throw("Only 1 checkbox should be checked")
    view = views[0]
    if view == "op_time_analysis" and not filters.get("operation"):
        frappe.throw("For Operation Time Analysis Operation is Mandatory")
    if view == "mach_eff" and not filters.get("mach_eff_type"):
        frappe.throw("For Machine Efficiency Select Total or Daily in Type of Report")
    return view


def get_summary_data(filters, view):
    jc = frappe.qb.DocType("Process Job Card RIGPL")
    return [
        blank_zeros(row)
        for row in (
            frappe.qb.from_(jc)
            .select(
                jc.employee_name, jc.workstation, jc.production_item, jc.description,
                jc.for_quantity, jc.total_completed_qty, jc.total_rejected_qty, jc.operation,
                jc.total_time_in_mins, Round(time_per_pc(jc), 2), jc.name,
            )
            .where(jc.docstatus == 1)
            .where(get_jc_conditions(jc, filters, view))
            .orderby(jc.workstation)
            .orderby(jc.production_item)
            .run()
        )
    ]


def get_planning_data(filters, view):
    jc = frappe.qb.DocType("Process Job Card RIGPL")
    it = frappe.qb.DocType("Item")
    job_cards = (
        frappe.qb.from_(jc)
        .join(it)
        .on(it.name == jc.production_item)
        .select(
            jc.name, jc.status, jc.rm_status, jc.rm_shortage, jc.sales_order, jc.production_item,
            jc.priority, jc.operation_serial_no, jc.remarks, jc.description, jc.operation,
            jc.workstation, jc.total_qty, jc.for_quantity, jc.qty_available, jc.creation,
        )
        .where(jc.docstatus == 0)
        .where(jc.status.notin(["Completed", "Cancelled"]))
        .where(get_jc_conditions(jc, filters, view))
        .where(attribute_filters(jc.production_item, get_attribute_values(filters)))
        .run(as_dict=True)
    )
    att_map = get_attribute_map([d.production_item for d in job_cards], ATTS)
    numeric = set(SIZE_ATTS)
    job_cards.sort(
        key=lambda d: (
            cint(d.priority),
            cint(d.operation_serial_no),
            attribute_sort_key(att_map.get(d.production_item, {}), PLANNING_SORT_ATTS, numeric),
            d.name,
        )
    )
    data = []
    for d in job_cards:
        row = [
            d.name, d.status, d.rm_status, d.rm_shortage, d.sales_order or "X", d.production_item,
            d.priority, d.remarks or "X"
        ]
        row += get_attribute_cells(att_map.get(d.production_item, {}), ATTS)
        row += [
            d.description, d.operation, d.workstation, d.total_qty, d.for_quantity,
            d.qty_available, d.creation
        ]
        data.append(blank_zeros(row))
    return data


def get_order_wise_data(filters):
    so = frappe.qb.DocType("Sales Order")
    soi = frappe.qb.DocType("Sales Order Item")
    it = frappe.qb.DocType("Item")
    pend_qty = soi.qty - IfNull(soi.delivered_qty, 0)
    query = (
        frappe.qb.from_(so)
        .join(soi)
        .on(soi.parent == so.name)
        .join(it)
        .on(it.name == soi.item_code)
        .select(
            so.name, so.transaction_date, soi.item_code, soi.description,
            pend_qty.as_("pend_qty"), soi.qty, soi.name.as_("so_item"),
        )
        .where(so.docstatus == 1)
        .where(pend_qty > 0)
        .where(so.status != "Closed")
        .where(so.transaction_date <= nowdate())
        .where(it.made_to_order == 1)
        .orderby(so.transaction_date)
        .orderby(so.name)
        .orderby(soi.item_code)
        .orderby(soi.description)
    )
    if filters.get("sales_order"):
        query = query.where(so.name == filters["sales_order"])
    so_rows = query.run(as_dict=True)
    so_items = [d.so_item for d in so_rows]
    ps_links = get_process_sheet_links(so_items)
    last_jcs = get_last_jc_for_so_items(so_items)
    data = []
    for d in so_rows:
        jc = last_jcs.get(d.so_item)
        row = [d.name, d.transaction_date, d.item_code, d.description, d.pend_qty, d.qty]
        if jc:
            row += [
                jc.name, ps_links.get(d.so_item, ""), jc.status, jc.operation, jc.priority,
                jc.for_quantity, jc.qty_available, jc.remarks
            ]
        else:
            row += ["", ps_links.get(d.so_item, ""), "NO JC", "", 0, 0, 0, "Not in Production"]
        data.append(blank_zeros(row))
    return data


def get_process_sheet_links(so_items):
    """
    Returns {so_item: links to its Process Sheets, one per line}
    """
    links = {}
    for chunk in chunks(so_items):
        ps = frappe.qb.DocType("Process Sheet")
        rows = (
            frappe.qb.from_(ps)
            .select(ps.name, ps.sales_order_item)
            .where(ps.docstatus != 2)
            .where(ps.sales_order_item.isin(chunk))
            .orderby(ps.creation)
            .run(as_dict=True)
        )
        for d in rows:
            link = """<a href="#Form/Process Sheet/%s" target="_blank">%s</a>""" % (d.name, d.name)
            links[d.sales_order_item] = links.get(d.sales_order_item, "") + link + "\n"
    return links


def get_op_time_data(filters, view):
    jc = frappe.qb.DocType("Process Job Card RIGPL")
    ws = frappe.qb.DocType("Workstation")
    tlog = frappe.qb.DocType("Job Card Time Log")
    it = frappe.qb.DocType("Item")
    job_cards = (
        frappe.qb.from_(jc)
        .join(ws)
        .on(ws.name == jc.workstation)
        .join(tlog)
        .on(tlog.parent == jc.name)
        .join(it)
        .on(it.name == jc.production_item)
        .select(
            jc.posting_date, jc.employee_name, jc.workstation, jc.production_item,
            jc.for_quantity, jc.total_completed_qty, jc.total_rejected_qty, jc.operation,
            jc.total_time_in_mins, Round(time_per_pc(jc), 2).as_("time_per_pc"),
            Round(time_per_pc(jc) * ws.hour_rate / 60, 2).as_("cost_per_pc"), jc.name,
            jc.description,
        )
        .where(jc.docstatus == 1)
        .where(tlog.parenttype == "Process Job Card RIGPL")
        .where(tlog.from_time.isnotnull())
        .where(tlog.to_time.isnotnull())
        .where(get_jc_conditions(jc, filters, view))
        .where(attribute_filters(jc.production_item, get_attribute_values(filters)))
        .orderby(jc.posting_date)
        .orderby(jc.workstation)
        .orderby(jc.production_item)
        .run(as_dict=True)
    )
    att_map = get_attribute_map([d.production_item for d in job_cards], OP_TIME_ATTS)
    data = []
    for d in job_cards:
        row = [d.posting_date, d.employee_name, d.workstation, d.production_item]
        row += get_attribute_cells(att_map.get(d.production_item, {}), OP_TIME_ATTS)
        row += [
            d.for_quantity, d.total_completed_qty, d.total_rejected_qty, d.operation,
            d.total_time_in_mins, d.time_per_pc, d.cost_per_pc, d.name, d.description
        ]
        data.append(blank_zeros(row))
    return data


def get_machine_efficiency_data(filters, view):
    days = (getdate(filters.get("to_date")) - getdate(filters.get("from_date"))).days + 1
    tot_hrs = days * 24
    if days < 1:
        frappe.throw("Difference Between From and To Date should be Minimum 1 days for Machine Efficiency")
    daily = filters.get("mach_eff_type") != "Total"
    ws = frappe.qb.DocType("Workstation")
    machines = frappe.qb.from_(ws).select(ws.name, ws.disabled).run(as_dict=True)
    jc = frappe.qb.DocType("Process Job Card RIGPL")
    tlog = frappe.qb.DocType("Job Card Time Log")
    query = (
        frappe.qb.from_(jc)
        .join(tlog)
        .on(tlog.parent == jc.name)
        .join(ws)
        .on(ws.name == jc.workstation)
        .select(jc.workstation, Sum(jc.total_time_in_mins).as_("tot_mins"))
        .where(jc.docstatus == 1)
        .where(tlog.from_time.isnotnull())
        .where(get_jc_conditions(jc, filters, view))
        .groupby(jc.workstation)
        .orderby(jc.workstation)
    )
    if daily:
        query = query.select(jc.posting_date).groupby(jc.posting_date)
    worked = {}
    for d in query.run(as_dict=True):
        worked.setdefault(d.workstation, []).append(d)
    data = []
    for mc in machines:
        rows = worked.get(mc.name, [])
        if not rows:
            date_or_days = filters.get("to_date") if daily else days
            data.append([mc.name, date_or_days, 24 if daily else tot_hrs, 0, 0, mc.disabled])
        elif daily:
            for d in rows:
                worked_hrs = d.tot_mins / 60
                data.append([d.workstation, d.posting_date, 24, worked_hrs, worked_hrs / 24 * 100, mc.disabled])
        else:
            worked_hrs = rows[0].tot_mins / 60
            data.append([mc.name, days, tot_hrs, worked_hrs, worked_hrs / tot_hrs * 100, mc.disabled])
    return [blank_zeros(row) for row in data]


def get_jc_conditions(jc, filters, view):
    """
    Returns the Job Card criterion for the filters that apply to the view
    """
    conditions = []
    if view in ("summary", "op_time_analysis", "mach_eff"):
        if filters.get("from_date"):
            conditions.append(jc.posting_date >= filters["from_date"])
        if filters.get("to_date"):
            conditions.append(jc.posting_date <= filters["to_date"])
    if view != "summary":
        if filters.get("sales_order"):
            conditions.append(jc.sales_order == filters["sales_order"])
        if filters.get("jc_status") and view not in ("op_time_analysis", "mach_eff"):
            conditions.append(jc.status == filters["jc_status"])
        if filters.get("operation") and view != "mach_eff":
            conditions.append(jc.operation == filters["operation"])
        if filters.get("item"):
            conditions.append(jc.production_item == filters["item"])
    return Criterion.all(conditions)


def get_attribute_values(filters):
    """
    Returns {attribute: value} for the attribute filters
    """
    return {
        "Base Material": filters.get("bm"),
        "Tool Type": filters.get("tt"),
        "Special Treatment": filters.get("spl"),
        "Series": filters.get("series"),
    }


def get_attribute_cells(values, attributes):
    """
    Returns the cells of the attribute columns: text as it is, sizes rounded to 3 decimals
    """
    cells = []
    for attribute in attributes:
        value = values.get(attribute)
        if attribute in SIZE_ATTS and value is not None:
            value = round(flt(value), 3)
        cells.append(value)
    return cells


def time_per_pc(jc):
    return jc.total_time_in_mins / (jc.total_completed_qty + jc.total_rejected_qty)
