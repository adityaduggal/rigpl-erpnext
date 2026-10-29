# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
"""
Daily check of the Bin quantities that come from open documents. Each (item, warehouse)
quantity is calculated with one grouped query for each source, and all wrong fields of a Bin
are fixed in one write.

A document submitted between the read and the write can get a stale value. The next run
fixes it.
"""
from __future__ import unicode_literals

import time
from typing import Dict, List, Optional, Set, Tuple

import frappe
from erpnext.stock.stock_balance import update_bin_qty
from frappe.query_builder.functions import IfNull, Sum
from frappe.utils import cint, flt
from pypika.terms import Case, Criterion
from rohit_common.utils.background_doc_processing import enqueue_once

from ...utils.batch_write_utils import bulk_set_fields
from ...utils.item_attribute_utils import chunks

BIN_QTY_FIELDS = ("reserved_qty", "ordered_qty", "indented_qty", "planned_qty",
    "reserved_qty_for_production")
BIN_READ_FIELDS = ("name", "item_code", "warehouse", "actual_qty", "reserved_qty_for_sub_contract",
    "projected_qty") + BIN_QTY_FIELDS

QtyMap = Dict[Tuple[str, str], Dict[str, float]]


def enqueue_ex():
    enqueue_once("rigpl_erpnext.rigpl_erpnext.scheduled_tasks.check_update_bin_values.execute", queue="long", timeout=1500)


def execute():
    st_time = time.time()
    changed, created = check_bins()
    print(f"Wrong Bins = {changed}, New Bins = {created}, Total Time = "
        f"{int(time.time() - st_time)} seconds")


def check_bins(item_codes: Optional[List[str]] = None) -> Tuple[int, int]:
    """
    Sets the Bin quantities from open documents for the stock items (or only `item_codes`)
    and fixes every wrong projected qty. Returns (changed Bins, created Bins).
    """
    precision = cint(frappe.db.get_default("float_precision")) or 3
    expected = get_expected_qty(item_codes)
    bins = {row.name: row for row in get_item_bins(item_codes)}
    loaded = {(row.item_code, row.warehouse) for row in bins.values()}
    not_loaded = {item_code for (item_code, wh), qty_dict in expected.items()
        if (item_code, wh) not in loaded and any(flt(qty, precision) for qty in qty_dict.values())}
    for row in get_bins_of_items(not_loaded):
        bins[row.name] = row
    # The other Bins keep their quantities and only get the projected qty fixed
    for row in get_bins_with_wrong_projected(item_codes):
        if row.name not in bins:
            bins[row.name] = row
            expected[(row.item_code, row.warehouse)] = {f: row[f] for f in BIN_QTY_FIELDS}

    changes = {}
    for row in bins.values():
        change = get_bin_change(row, expected.pop((row.item_code, row.warehouse), {}), precision)
        if change:
            changes[row.name] = change
            print(f"Bin {row.name} for {row.item_code} in {row.warehouse}: " + ", ".join(
                f"{field} {flt(row[field], precision)} -> {qty}" for field, qty in change.items()))
    bulk_set_fields("Bin", changes, bins, add_versions=False)

    created = 0
    for (item_code, warehouse), qty_dict in expected.items():
        if any(flt(qty, precision) for qty in qty_dict.values()):
            print(f"New Bin for {item_code} in {warehouse}: {qty_dict}")
            update_bin_qty(item_code, warehouse, qty_dict)
            created += 1
    return len(changes), created


def get_bin_change(row, expected_qty: Dict[str, float], precision: int) -> Dict[str, float]:
    """
    Returns {field: correct value} for the wrong fields of a Bin row. A missing expected qty
    is 0. projected_qty is calculated as in erpnext Bin.set_projected_qty.
    """
    new = {field: flt(expected_qty.get(field), precision) for field in BIN_QTY_FIELDS}
    new["projected_qty"] = flt(flt(row.actual_qty) + new["ordered_qty"] + new["indented_qty"]
        + new["planned_qty"] - new["reserved_qty"] - new["reserved_qty_for_production"]
        - flt(row.reserved_qty_for_sub_contract), precision)
    return {field: qty for field, qty in new.items() if qty != flt(row[field], precision)}


def get_expected_qty(item_codes: Optional[List[str]] = None) -> QtyMap:
    """
    Returns {(item_code, warehouse): {bin field: qty}} from the open documents. The
    formulas for reserved, ordered and indented qty are from erpnext/stock/stock_balance.py,
    for all items at once.
    """
    expected = {}
    for field, query in (
        ("reserved_qty", get_so_item_reserved_query(item_codes)),
        ("reserved_qty", get_packed_item_reserved_query(item_codes)),
        ("ordered_qty", get_ordered_query(item_codes)),
        ("indented_qty", get_indented_query(item_codes)),
        ("planned_qty", get_process_sheet_planned_query(item_codes)),
        ("planned_qty", get_work_order_planned_query(item_codes)),
        ("reserved_qty_for_production", get_reserved_for_production_query(item_codes)),
    ):
        for item_code, warehouse, qty in query.run():
            qty_dict = expected.setdefault((item_code, warehouse), {})
            qty_dict[field] = flt(qty_dict.get(field)) + flt(qty)
    return expected


def join_stock_items(query, item_field, item_codes: Optional[List[str]]):
    """Keeps only the rows of the job's items: enabled stock items, not templates or made to order."""
    item = frappe.qb.DocType("Item")
    query = query.inner_join(item).on(item.name == item_field).where(
        (item.disabled == 0) & (item.made_to_order == 0) & (item.is_stock_item == 1)
        & (item.has_variants == 0)
    )
    if item_codes is not None:
        query = query.where(item.name.isin(item_codes or [""]))
    return query


def get_so_item_reserved_query(item_codes):
    """stock_balance.get_reserved_qty, Sales Order Item part."""
    so, soi = frappe.qb.DocType("Sales Order"), frappe.qb.DocType("Sales Order Item")
    query = (
        frappe.qb.from_(soi).inner_join(so).on(so.name == soi.parent)
        .select(soi.item_code, soi.warehouse,
            Sum(soi.stock_qty * (soi.qty - soi.delivered_qty) / soi.qty))
        .where((so.docstatus == 1) & so.status.notin(["On Hold", "Closed"])
            & (IfNull(soi.delivered_by_supplier, 0) == 0) & (soi.qty > soi.delivered_qty))
        .groupby(soi.item_code, soi.warehouse)
    )
    return join_stock_items(query, soi.item_code, item_codes)


def get_packed_item_reserved_query(item_codes):
    """stock_balance.get_reserved_qty, Packed Item part."""
    so, soi = frappe.qb.DocType("Sales Order"), frappe.qb.DocType("Sales Order Item")
    pi = frappe.qb.DocType("Packed Item")
    query = (
        frappe.qb.from_(pi).inner_join(so).on(so.name == pi.parent)
        .inner_join(soi).on(soi.name == pi.parent_detail_docname)
        .select(pi.item_code, pi.warehouse, Sum(pi.qty * (soi.qty - soi.delivered_qty) / soi.qty))
        .where((pi.parenttype == "Sales Order") & (pi.item_code != pi.parent_item)
            & (so.docstatus == 1) & so.status.notin(["On Hold", "Closed"])
            & (IfNull(soi.delivered_by_supplier, 0) == 0) & (soi.qty > soi.delivered_qty))
        .groupby(pi.item_code, pi.warehouse)
    )
    return join_stock_items(query, pi.item_code, item_codes)


def get_ordered_query(item_codes):
    """stock_balance.get_ordered_qty."""
    po, poi = frappe.qb.DocType("Purchase Order"), frappe.qb.DocType("Purchase Order Item")
    query = (
        frappe.qb.from_(poi).inner_join(po).on(po.name == poi.parent)
        .select(poi.item_code, poi.warehouse,
            Sum((poi.qty - poi.received_qty) * poi.conversion_factor))
        .where((po.docstatus == 1) & po.status.notin(["Closed", "Delivered"])
            & (poi.qty > poi.received_qty) & (poi.delivered_by_supplier == 0))
        .groupby(poi.item_code, poi.warehouse)
    )
    return join_stock_items(query, poi.item_code, item_codes)


def get_indented_query(item_codes):
    """stock_balance.get_indented_qty: inward requests less Material Issue."""
    mr, mri = frappe.qb.DocType("Material Request"), frappe.qb.DocType("Material Request Item")
    pending = mri.stock_qty - mri.ordered_qty
    query = (
        frappe.qb.from_(mri).inner_join(mr).on(mr.name == mri.parent)
        .select(mri.item_code, mri.warehouse, Sum(
            Case().when(mr.material_request_type == "Material Issue", -pending).else_(pending)))
        .where((mr.docstatus == 1) & (mr.status != "Stopped") & (mri.stock_qty > mri.ordered_qty)
            & mr.material_request_type.isin(["Purchase", "Manufacture", "Customer Provided",
                "Material Transfer", "Material Issue"]))
        .groupby(mri.item_code, mri.warehouse)
    )
    return join_stock_items(query, mri.item_code, item_codes)


def get_process_sheet_planned_query(item_codes):
    """manufacturing_utils.get_planned_qty_process."""
    ps = frappe.qb.DocType("Process Sheet")
    query = (
        frappe.qb.from_(ps)
        .select(ps.production_item, ps.fg_warehouse, Sum(ps.quantity - ps.produced_qty))
        .where((ps.docstatus == 1) & ps.status.notin(["Stopped", "Completed", "Short Closed"])
            & (ps.quantity > ps.produced_qty))
        .groupby(ps.production_item, ps.fg_warehouse)
    )
    return join_stock_items(query, ps.production_item, item_codes)


def get_work_order_planned_query(item_codes):
    """stock_balance.get_planned_qty."""
    wo = frappe.qb.DocType("Work Order")
    query = (
        frappe.qb.from_(wo)
        .select(wo.production_item, wo.fg_warehouse, Sum(wo.qty - wo.produced_qty))
        .where((wo.docstatus == 1) & wo.status.notin(["Stopped", "Completed", "Closed"])
            & (wo.qty > wo.produced_qty))
        .groupby(wo.production_item, wo.fg_warehouse)
    )
    return join_stock_items(query, wo.production_item, item_codes)


def get_reserved_for_production_query(item_codes):
    """manufacturing_utils.get_qty_for_prod for the rm_consumed table."""
    ps, psi = frappe.qb.DocType("Process Sheet"), frappe.qb.DocType("Process Sheet Items")
    query = (
        frappe.qb.from_(psi).inner_join(ps).on(ps.name == psi.parent)
        .select(psi.item_code, psi.source_warehouse, Sum(psi.calculated_qty - psi.qty))
        .where((psi.parenttype == "Process Sheet") & (psi.parentfield == "rm_consumed")
            & (ps.docstatus == 1) & ps.status.notin(["Stopped", "Completed", "Short Closed"])
            & (psi.donot_consider_rm_for_production != 1))
        .groupby(psi.item_code, psi.source_warehouse)
    )
    return join_stock_items(query, psi.item_code, item_codes)


def get_item_bins(item_codes: Optional[List[str]] = None):
    """Bins of the job's items, other than the ones where all BIN_QTY_FIELDS are 0."""
    bn = frappe.qb.DocType("Bin")
    query = frappe.qb.from_(bn).select(*[bn[f] for f in BIN_READ_FIELDS])
    query = join_stock_items(query, bn.item_code, item_codes).where(
        Criterion.any([bn[f] != 0 for f in BIN_QTY_FIELDS]))
    return query.run(as_dict=1)


def get_bins_of_items(item_codes: Set[str]) -> List:
    bn = frappe.qb.DocType("Bin")
    rows = []
    for chunk in chunks(item_codes):
        rows += frappe.qb.from_(bn).select(*[bn[f] for f in BIN_READ_FIELDS]).where(
            bn.item_code.isin(chunk)).run(as_dict=1)
    return rows


def get_bins_with_wrong_projected(item_codes: Optional[List[str]] = None):
    bn = frappe.qb.DocType("Bin")
    query = frappe.qb.from_(bn).select(*[bn[f] for f in BIN_READ_FIELDS]).where(
        bn.projected_qty != bn.actual_qty + bn.ordered_qty + bn.indented_qty + bn.planned_qty
        - bn.reserved_qty - bn.reserved_qty_for_production - bn.reserved_qty_for_sub_contract
    )
    if item_codes is not None:
        query = query.where(bn.item_code.isin(item_codes or [""]))
    return query.run(as_dict=1)
