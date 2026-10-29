# -*- coding: utf-8 -*-
#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
"""
Batch reads for the manufacturing jobs (#160). Each function takes a list of names and runs a
fixed number of queries for each chunk of names.
"""
from __future__ import unicode_literals

import frappe
from frappe.utils import flt

from ...utils.item_attribute_utils import chunks

ITEM_FIELDS = ["name", "made_to_order", "sales_job_work", "stock_uom", "valuation_rate",
    "lead_time_days"]
OPERATION_FIELDS = ["name", "parent", "idx", "operation", "source_warehouse", "transfer_entry",
    "allow_consumption_of_rm", "allow_production_of_wip_materials", "final_operation"]
JC_ROW_FIELDS = ["name", "parent", "parentfield", "idx", "item_code", "source_warehouse",
    "target_warehouse", "qty_available", "current_projected_qty", "projected_qty", "uom",
    "calculated_qty"]


def get_item_rows(item_names):
    """
    Returns {item: row} with the fields that get_quantities_for_items and the Job Card jobs need
    """
    rows = {}
    for chunk in chunks(item_names):
        for row in frappe.get_all("Item", filters={"name": ("in", chunk)}, fields=ITEM_FIELDS):
            rows[row.name] = row
    return rows


def get_rows_by_parent(doctype, parenttype, parents, fields, parentfield=None):
    """
    Returns {parent: [child rows by idx]}
    """
    rows = {}
    filters = {"parenttype": parenttype}
    if parentfield:
        filters["parentfield"] = parentfield
    for chunk in chunks(parents):
        filters["parent"] = ("in", chunk)
        for row in frappe.get_all(doctype, filters=filters, fields=fields, order_by="idx"):
            rows.setdefault(row.parent, []).append(row)
    return rows


def get_operations_map(parents, parenttype):
    """
    Returns {parent: [BOM Operation rows by idx]} for Process Sheets or BOM Templates
    """
    return get_rows_by_parent("BOM Operation", parenttype, parents, OPERATION_FIELDS, "operations")


def get_jc_rows_map(job_cards):
    """
    Returns {Job Card: {parentfield: [Process Sheet Items rows by idx]}} for rm_consumed and
    item_manufactured
    """
    result = {}
    by_parent = get_rows_by_parent("Process Sheet Items", "Process Job Card RIGPL", job_cards,
        JC_ROW_FIELDS)
    for parent, rows in by_parent.items():
        for row in rows:
            result.setdefault(parent, {}).setdefault(row.parentfield, []).append(row)
    return result


def get_bin_map(items):
    """
    Returns ({(item, warehouse): Bin row}, {item: totals}) for find_item_quantities. The totals are
    the sums of all the Bins of the item (prd_qty, on_so, on_po, planned) and subcon_qty, the
    actual qty of the first subcontracting Bin with stock.
    """
    bn = frappe.qb.DocType("Bin")
    wh = frappe.qb.DocType("Warehouse")
    bins, totals = {}, {}
    for chunk in chunks(items):
        for row in (
            frappe.qb.from_(bn)
            .join(wh).on(bn.warehouse == wh.name)
            .select(
                bn.item_code, bn.warehouse, bn.actual_qty, bn.stock_uom, bn.reserved_qty,
                bn.ordered_qty, bn.planned_qty, bn.reserved_qty_for_production,
                wh.is_subcontracting_warehouse,
            )
            .where(bn.item_code.isin(chunk))
            .run(as_dict=True)
        ):
            bins[(row.item_code, row.warehouse)] = row
            tot = totals.setdefault(row.item_code, frappe._dict(
                prd_qty=0, on_so=0, on_po=0, planned=0, subcon_qty=None))
            tot.prd_qty += flt(row.reserved_qty_for_production)
            tot.on_so += flt(row.reserved_qty)
            tot.on_po += flt(row.ordered_qty)
            tot.planned += flt(row.planned_qty)
            if tot.subcon_qty is None and row.is_subcontracting_warehouse and row.actual_qty > 0:
                tot.subcon_qty = row.actual_qty
    return bins, totals


def get_submitted_jc_map(so_items):
    """
    Returns {sales_order_item: [submitted Job Cards]} for the completed and GRN qty of made to
    order Job Cards
    """
    jc = frappe.qb.DocType("Process Job Card RIGPL")
    result = {}
    for chunk in chunks(so_items):
        for row in (
            frappe.qb.from_(jc)
            .select(
                jc.name, jc.operation, jc.sales_order_item, jc.s_warehouse, jc.t_warehouse,
                jc.total_completed_qty, jc.status,
            )
            .where(jc.docstatus == 1)
            .where(jc.sales_order_item.isin(chunk))
            .run(as_dict=True)
        ):
            result.setdefault(row.sales_order_item, []).append(row)
    return result


def get_first_po_items(job_cards):
    """
    Returns {Job Card: its first submitted Purchase Order Item}, like get_grn_qty
    """
    po = frappe.qb.DocType("Purchase Order")
    poi = frappe.qb.DocType("Purchase Order Item")
    first_po_item = {}
    for chunk in chunks(job_cards):
        for reference_dn, po_item in (
            frappe.qb.from_(po)
            .join(poi).on(poi.parent == po.name)
            .select(poi.reference_dn, poi.name)
            .where(po.docstatus == 1)
            .where(poi.reference_dn.isin(chunk))
            .where(poi.reference_dt == "Process Job Card RIGPL")
            .run()
        ):
            first_po_item.setdefault(reference_dn, po_item)
    return first_po_item


def get_grn_rows(po_items):
    """
    Returns {Purchase Order Item: [(qty, warehouse)]} of the submitted Purchase Receipts
    """
    pr = frappe.qb.DocType("Purchase Receipt")
    pri = frappe.qb.DocType("Purchase Receipt Item")
    grn_rows = {}
    for chunk in chunks(po_items):
        for po_item, grn_qty, warehouse in (
            frappe.qb.from_(pr)
            .join(pri).on(pri.parent == pr.name)
            .select(pri.purchase_order_item, pri.qty, pri.warehouse)
            .where(pr.docstatus == 1)
            .where(pri.purchase_order_item.isin(chunk))
            .run()
        ):
            grn_rows.setdefault(po_item, []).append((grn_qty, warehouse))
    return grn_rows


def get_so_item_qty_map(so_items):
    """
    Returns {Sales Order Item: qty}
    """
    result = {}
    for chunk in chunks(so_items):
        result.update(frappe.get_all(
            "Sales Order Item", filters={"name": ("in", chunk)}, fields=["name", "qty"], as_list=True
        ))
    return result


def get_pending_ps_ops_map(items, operations):
    """
    Returns {(item, operation): [pending operations of submitted Process Sheets]}, the oldest
    Process Sheet first, like return_job_card_qty
    """
    ps = frappe.qb.DocType("Process Sheet")
    pso = frappe.qb.DocType("BOM Operation")
    operations = list(set(operations))
    result = {}
    if not operations:
        return result
    for chunk in chunks(items):
        for row in (
            frappe.qb.from_(ps)
            .join(pso).on(pso.parent == ps.name)
            .select(
                ps.name, ps.production_item, ps.sales_order_item, pso.operation, pso.planned_qty,
                pso.completed_qty, ps.creation, pso.allow_consumption_of_rm, pso.status,
                pso.transfer_entry, pso.name.as_("op_name"),
            )
            .where(ps.docstatus == 1)
            .where(pso.parenttype == "Process Sheet")
            .where(pso.completed_qty < pso.planned_qty)
            .where(pso.status != "Completed")
            .where(pso.status.notin(["Short Closed", "Stopped", "Obsolete"]))
            .where(ps.production_item.isin(chunk))
            .where(pso.operation.isin(operations))
            .orderby(ps.creation)
            .run(as_dict=True)
        ):
            result.setdefault((row.production_item, row.operation), []).append(row)
    return result
