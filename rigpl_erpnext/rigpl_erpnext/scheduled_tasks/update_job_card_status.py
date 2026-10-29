# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
"""
"Update Job Card Status" step of the manufacturing pipeline (#146). Calculates the fields that
ProcessJobCardRIGPL.validate sets for all the draft Job Cards with batched reads, and writes only
the fields that changed. A Job Card gets a full save() only when its quantities or its structure
change, because validate then also changes the RM calculated_qty and the child tables.
"""
from __future__ import unicode_literals
import time
import frappe
from frappe.utils import cint, flt
from ...utils.batch_write_utils import bulk_insert_versions, bulk_set_fields, clear_document_cache
from ...utils.item_attribute_utils import chunks
from ...utils.sales_utils import get_open_so_lines
from ...utils.stock_utils import get_quantities_for_items
from ...manufacturing_rigpl.utils.batch_qty_utils import (
    get_bin_map,
    get_first_po_items,
    get_grn_rows,
    get_item_rows,
    get_jc_rows_map,
    get_operations_map,
    get_pending_ps_ops_map,
    get_rows_by_parent,
    get_so_item_qty_map,
    get_submitted_jc_map,
)
from ...manufacturing_rigpl.utils.job_card_utils import (
    get_jc_rm_status,
    get_job_card_process_sno,
    get_job_card_qty_available,
    get_job_card_qty_text,
    get_job_card_status,
    get_moved_qty,
    get_production_priority_for_item,
    get_rm_item_codes,
    get_subcontracting_operations,
    return_job_card_qty,
    update_row_quantities,
)
from .process_sheet_update import run_write

JC_DOCTYPE = "Process Job Card RIGPL"
ROW_DOCTYPE = "Process Sheet Items"
JC_FIELDS = ["name", "docstatus", "process_sheet", "operation_id", "operation", "production_item",
    "sales_order", "sales_order_item", "sno", "s_warehouse", "t_warehouse", "transfer_entry",
    "allow_consumption_of_rm", "allow_production_of_wip_materials", "for_quantity", "total_qty",
    "qty_available", "priority", "status", "operation_serial_no", "final_operation",
    "quantity_details", "uom", "no_stock_entry", "rm_status", "rm_shortage"]
ROW_FIELDS = ["qty_available", "current_projected_qty", "projected_qty", "uom"]
TABLES = (("rm_consumed", "source_warehouse"), ("item_manufactured", "target_warehouse"))


def execute():
    st_time = time.time()
    job_cards = frappe.get_all(JC_DOCTYPE, filters={"docstatus": 0}, fields=JC_FIELDS, order_by="name")
    ctx = get_context(job_cards)
    new_values, new_rows, to_save = get_new_values(job_cards, ctx)
    changes, row_changes = write_changes(job_cards, ctx, new_values, new_rows)
    saved = save_job_cards(to_save)
    print(f"Total Number of Job Cards in Draft: {len(job_cards)}")
    print(f"Job Cards with changed fields: {len(set(changes) | set(row_changes))}")
    print(f"Job Cards saved because quantities or structure changed: {saved} of {len(to_save)}")
    print(f"Total Execution Time: {int(time.time() - st_time)} seconds")


def get_context(job_cards):
    """
    Returns the batched inputs of all the draft Job Cards, in a fixed number of queries for each
    chunk of names
    """
    ctx = frappe._dict()
    ctx.ps = {}
    for chunk in chunks({jc.process_sheet for jc in job_cards}):
        for row in frappe.get_all("Process Sheet", filters={"name": ("in", chunk)},
                fields=["name", "sales_order", "sales_order_item", "sno", "bom_template"]):
            ctx.ps[row.name] = row
    ctx.ps_ops = get_operations_map(ctx.ps, "Process Sheet")
    ctx.bt_ops = get_operations_map({ps.bom_template for ps in ctx.ps.values() if ps.bom_template},
        "BOM Template RIGPL")
    ctx.rows = get_jc_rows_map([jc.name for jc in job_cards])
    ctx.ps_tables = {}
    for ps, rows in get_rows_by_parent(ROW_DOCTYPE, "Process Sheet", ctx.ps, ["parent", "parentfield"]).items():
        ctx.ps_tables[ps] = {row.parentfield for row in rows}
    ctx.item_rows = get_item_rows({jc.production_item for jc in job_cards})
    ctx.qty = get_quantities_for_items(ctx.item_rows.values())
    ctx.so_lines = get_open_so_lines(list(ctx.item_rows))
    row_items = {row.item_code for tables in ctx.rows.values() for rows in tables.values() for row in rows}
    ctx.bins, ctx.bin_totals = get_bin_map(set(ctx.item_rows) | row_items)

    mto_so_items = {jc.sales_order_item for jc in job_cards if jc.sales_order_item and jc.s_warehouse}
    ctx.submitted = get_submitted_jc_map(mto_so_items)
    ctx.so_qty = get_so_item_qty_map(mto_so_items)
    ctx.subcon_ops = get_subcontracting_operations(
        {sjc.operation for rows in ctx.submitted.values() for sjc in rows})
    ctx.first_po_item = get_first_po_items(
        [sjc.name for rows in ctx.submitted.values() for sjc in rows if sjc.operation in ctx.subcon_ops])
    ctx.grn_rows = get_grn_rows(set(ctx.first_po_item.values()))

    ctx.pending = get_pending_ps_ops_map(ctx.item_rows, {jc.operation for jc in job_cards})
    ctx.ps_rm = {}
    rm_ps = {op.name for ops in ctx.pending.values() for op in ops if op.allow_consumption_of_rm == 1}
    for chunk in chunks(rm_ps):
        ctx.ps_rm.update(get_rm_item_codes(chunk, "Process Sheet"))
    return ctx


def get_new_values(job_cards, ctx):
    """
    Returns ({Job Card: {field: new value}}, {row: {field: new value}}, [Job Cards to save]).
    The quantities of all the Job Cards come first, because the priority of a Job Card uses the
    quantities of the other Job Cards of the item.
    """
    meta, row_meta = frappe.get_meta(JC_DOCTYPE), frappe.get_meta(ROW_DOCTYPE)
    to_save, views = [], {}
    for jc in job_cards:
        view = get_job_card_view(jc, ctx)
        if view is None:
            to_save.append(jc.name)
        else:
            views[jc.name] = view
    open_jcs = get_open_job_cards_by_item(job_cards, views)

    new_values, new_rows = {}, {}
    for name, view in views.items():
        item = ctx.item_rows[view.production_item]
        view.priority = get_production_priority_for_item(
            view.production_item, view, it_doc=item, qty_dict=ctx.qty[item.name],
            so_lines=ctx.so_lines.get(item.name, []), open_jcs=open_jcs.get(item.name, []),
        )
        ps_sheet = [
            op for op in ctx.pending.get((view.production_item, view.operation), [])
            if not view.sales_order_item or op.sales_order_item == view.sales_order_item
        ]
        tot_qty, for_qty = return_job_card_qty(view, ps_sheet=ps_sheet, ps_rm_codes=ctx.ps_rm,
            qty_available=view.qty_available)
        if flt(tot_qty) != view.total_qty or flt(for_qty) != view.for_quantity:
            to_save.append(name)
            continue
        view.status = get_job_card_status(view)
        view.quantity_details = get_job_card_qty_text(ctx.qty[item.name])
        if view.s_warehouse == view.t_warehouse:
            view.no_stock_entry = 1
        for table, warehouse_field in TABLES:
            update_row_quantities(view[table], warehouse_field, ctx.bins, ctx.bin_totals)
            for row in view[table]:
                new_rows[row.name] = {f: cast(row_meta, f, row[f]) for f in ROW_FIELDS}
        view.rm_status, view.rm_shortage = get_jc_rm_status(view)
        new_values[name] = {
            f: cast(meta, f, view[f]) for f in ("qty_available", "priority", "status",
                "operation_serial_no", "final_operation", "quantity_details", "no_stock_entry",
                "rm_status", "rm_shortage")
        }
    return new_values, new_rows, to_save


def get_job_card_view(jc, ctx):
    """
    Returns a copy of the Job Card with its child rows, the new qty_available, operation_serial_no
    and final_operation. Returns None when validate would change its structure (Process Sheet,
    operation, warehouses or child tables), so the Job Card needs a full save.
    """
    ps = ctx.ps.get(jc.process_sheet)
    item = ctx.item_rows.get(jc.production_item)
    if ps is None or item is None or not ps.bom_template:
        return None
    ps_ops = ctx.ps_ops.get(ps.name, [])
    op = next((row for row in ps_ops if row.name == jc.operation_id), None)
    if op is None:
        return None
    rows = ctx.rows.get(jc.name, {})
    view = frappe._dict(jc)
    view.rm_consumed = [frappe._dict(row) for row in rows.get("rm_consumed", [])]
    view.item_manufactured = [frappe._dict(row) for row in rows.get("item_manufactured", [])]
    synced = {
        "sales_order": ps.sales_order, "sales_order_item": ps.sales_order_item, "sno": ps.sno,
        "operation": op.operation, "allow_consumption_of_rm": op.allow_consumption_of_rm,
        "allow_production_of_wip_materials": op.allow_production_of_wip_materials,
        "uom": item.stock_uom,
    }
    if any(jc[field] != value for field, value in synced.items()):
        return None
    for table, allowed in (("rm_consumed", op.allow_consumption_of_rm),
            ("item_manufactured", op.allow_production_of_wip_materials)):
        # validate clears a table that is not allowed, and copies an empty one from the Process Sheet
        if view[table] and allowed != 1:
            return None
        if not view[table] and allowed == 1 and table in ctx.ps_tables.get(ps.name, ()):
            return None
    if jc.allow_consumption_of_rm == 1 and jc.s_warehouse:
        return None
    if (jc.transfer_entry == 1 and not jc.s_warehouse) or op.transfer_entry != jc.transfer_entry:
        return None

    bn = ctx.bins.get((jc.production_item, jc.s_warehouse))
    moved_qty = None
    if jc.s_warehouse and jc.sales_order_item:
        moved_qty = get_moved_qty(jc, ctx.submitted.get(jc.sales_order_item, []), ctx.subcon_ops,
            ctx.first_po_item, ctx.grn_rows)
    view.qty_available = flt(get_job_card_qty_available(
        jc, bin_qty=flt(bn.actual_qty) if bn else 0, ps_operations=ps_ops,
        sales_job_work=item.sales_job_work, so_qty=ctx.so_qty.get(jc.sales_order_item),
        moved_qty=moved_qty,
    ))
    view.operation_serial_no, view.final_operation = get_job_card_process_sno(
        jc, bt_operations=ctx.bt_ops.get(ps.bom_template, []))
    return view


def get_open_job_cards_by_item(job_cards, views):
    """
    Returns {item: [draft Job Cards]} like get_open_job_cards_for_item (the last operation first),
    with the new quantities of the Job Cards that are calculated here
    """
    by_item = {}
    for jc in job_cards:
        by_item.setdefault(jc.production_item, []).append(views.get(jc.name, jc))
    for rows in by_item.values():
        rows.sort(key=lambda row: cint(row.operation_serial_no), reverse=True)
    return by_item


def cast(meta, field, value):
    """Returns the value as the database keeps it, so that an unchanged value compares equal."""
    fieldtype = meta.get_field(field).fieldtype
    if fieldtype in ("Int", "Check"):
        return cint(value)
    if fieldtype in ("Float", "Currency", "Percent"):
        return flt(value, 9)
    return value


def write_changes(job_cards, ctx, new_values, new_rows):
    """
    Writes the changed Job Card fields and rows with 1 Version for each changed Job Card, which
    also lists the changed rows
    """
    old_values = {jc.name: {f: jc[f] for f in new_values.get(jc.name, {})} for jc in job_cards}
    old_rows, row_parent = {}, {}
    for parent, tables in ctx.rows.items():
        for table, rows in tables.items():
            for row in rows:
                old_rows[row.name] = {f: row[f] for f in ROW_FIELDS}
                row_parent[row.name] = (parent, table, row.idx)
    changes = bulk_set_fields(JC_DOCTYPE, new_values, old_values, add_versions=False)
    row_changes = bulk_set_fields(ROW_DOCTYPE, new_rows, old_rows, add_versions=False)

    diffs = {name: {"changed": diff, "row_changed": []} for name, diff in changes.items()}
    for row_name, diff in row_changes.items():
        parent, table, idx = row_parent[row_name]
        diffs.setdefault(parent, {"changed": [], "row_changed": []})["row_changed"].append(
            [table, idx, row_name, diff])
    clear_document_cache(JC_DOCTYPE, [row_parent[name][0] for name in row_changes])
    bulk_insert_versions(JC_DOCTYPE, diffs)
    return changes, row_changes


def save_job_cards(names):
    """
    Saves the Job Cards whose quantities or structure changed, so validate recalculates them.
    Returns the number of Job Cards saved.
    """
    saved = 0
    for name in names:
        if run_write("jc_status_save", lambda: frappe.get_doc(JC_DOCTYPE, name).save(),
                f"Update Job Card Status: {name} failed"):
            saved += 1
    return saved
