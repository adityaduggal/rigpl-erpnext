# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import time
import frappe
from frappe.utils import today, flt
from frappe.utils.background_jobs import enqueue
from ...utils.batch_write_utils import bulk_set_values
from ...utils.item_attribute_utils import chunks
from ...utils.sales_utils import get_open_so_lines
from ...utils.stock_utils import get_quantities_for_items
from ...manufacturing_rigpl.doctype.process_sheet.process_sheet import return_priority_psd
from ...manufacturing_rigpl.utils.process_sheet_utils import (
    get_actual_qty_before_process_in_ps,
    get_pend_psop,
    stop_operations,
)
from ...manufacturing_rigpl.utils.manufacturing_utils import (
    get_manufacturing_qty_settings,
    get_qty_to_manufacture,
)
from ...manufacturing_rigpl.utils.job_card_utils import (
    create_job_card,
    get_draft_job_cards,
    match_existing_job_cards,
)

COMMIT_EVERY = 100


def enqueue_process_sheet_update():
    enqueue(execute, queue="long", timeout=1500)


def execute():
    st_time = time.time()
    create_new_process_sheets()
    consolidate_transfer_operations()
    update_process_sheet_priority()
    total_time = int(time.time() - st_time)
    print(f"Total Time taken = {total_time} seconds")


def get_item_rows(item_names):
    """
    Returns {item: row with the fields that get_quantities_for_items needs}
    """
    rows = {}
    for chunk in chunks(item_names):
        for row in frappe.get_all(
            "Item",
            filters={"name": ("in", chunk)},
            fields=["name", "made_to_order", "valuation_rate", "lead_time_days"],
        ):
            rows[row.name] = row
    return rows


def run_write(savepoint, write, error_title):
    """
    Runs `write` and returns True. When it fails, rolls back to the savepoint, logs the error
    and returns False, so that one bad document does not stop the job.
    """
    frappe.db.savepoint(savepoint)
    try:
        write()
        return True
    except Exception:
        frappe.db.rollback(save_point=savepoint)
        frappe.log_error(title=error_title)
        print(f"{error_title}: {frappe.get_traceback().splitlines()[-1]}")
        return False


def consolidate_transfer_operations():
    """
    Gets all the Pending Operations in Process Sheets and Consolidates the transfer entries
    So the latest Process Sheet gets all the transfer quantity and all transfer entries of
    old Process Sheets are stopped
    """
    st_time = time.time()
    pend_ps_ops = get_pend_psop(tf_ent=1)
    print(f"Total Pending Operations to be Analysed = {len(pend_ps_ops)}")
    groups = {}
    for opr in pend_ps_ops:
        groups.setdefault((opr.production_item, opr.operation), []).append(opr)
    item_rows = get_item_rows({item for item, _op in groups})
    groups = {
        key: rows for key, rows in groups.items()
        if key[0] in item_rows and item_rows[key[0]].made_to_order != 1
    }
    if not groups:
        return
    plan = get_consolidation_plan(groups, item_rows)

    stopped = stop_operations(plan.stop, show_message=False)
    bulk_set_values(
        "BOM Operation", "planned_qty", plan.planned_qty,
        {opr.name: opr.planned_qty for rows in groups.values() for opr in rows},
    )
    for jc_name in plan.delete:
        print(f"Deleting {jc_name}")
        run_write(
            "delete_jc", lambda: frappe.delete_doc("Process Job Card RIGPL", jc_name, for_reload=True),
            f"Job Card {jc_name} not deleted",
        )
    writes = 0
    for jc_name, qty in plan.jc_qty.items():
        def change_qty():
            jcd = frappe.get_doc("Process Job Card RIGPL", jc_name)
            jcd.for_quantity = qty
            jcd.time_logs = []
            jcd.save()
        if run_write("jc_qty", change_qty, f"Job Card {jc_name} qty not changed to {qty}"):
            print(f"Changed Qty for JCR# {jc_name} to {qty}")
        writes = commit_if_needed(writes, st_time)
    for opr, qty in plan.create:
        def make_jc():
            psd = frappe.get_doc("Process Sheet", opr.ps_name)
            create_job_card(pro_sheet=psd, row=opr, quantity=qty, auto_create=1)
        if run_write(
            "create_jc", make_jc,
            f"Job Card not created for {opr.production_item} {opr.operation} {opr.ps_name}",
        ):
            print(f"Created JCR for Operation {opr.operation} for {opr.production_item} for "
                f"Process Sheet {opr.ps_name} for Quantity = {qty}")
        writes = commit_if_needed(writes, st_time)
    frappe.db.commit()
    print(f"Total Ops Stopped = {len(plan.stop)} (Deleted {len(stopped)} JCRs) and Operations "
        f"Changed = {len(plan.planned_qty)} and Unchanged Operations = {plan.unchanged} and "
        f"Created JCRs = {len(plan.create)} and Total Time Taken = "
        f"{int(time.time() - st_time)} seconds")


def get_consolidation_plan(groups, item_rows):
    """
    Returns what consolidate_transfer_operations must change, for all the groups of pending
    transfer operations {(item, operation): [operations, oldest Process Sheet first]}. Only the
    newest operation of a group stays open; it gets the qty that is in production before it.
    """
    last_ops = [rows[-1] for rows in groups.values()]
    ps_rows = get_light_process_sheets({opr.ps_name for opr in last_ops})
    qty_maps = get_quantities_for_items(item_rows[item] for item, _op in groups)
    subcon = dict(frappe.get_all("Operation", fields=["name", "is_subcontracting"], as_list=True))
    bin_qty = get_bin_actual_qty(
        {(opr.production_item, row.source_warehouse)
         for opr in last_ops for row in ps_rows[opr.ps_name].operations if row.transfer_entry == 1}
    )
    jc_by_pair, jc_rm = get_draft_job_cards(
        [item for item, _op in groups], [op for _item, op in groups]
    )

    plan = frappe._dict(stop={}, planned_qty={}, delete=[], jc_qty={}, create=[], unchanged=0)
    for (item, operation), rows in groups.items():
        for opr in rows[:-1]:
            print(f"Stopped Operation {operation} for {item} for Process Sheet {opr.ps_name}")
            plan.stop[opr.name] = opr.op_status
        last = rows[-1]
        psd = ps_rows[last.ps_name]
        exist_jcr = match_existing_job_cards(
            psd.operations, operation, jc_by_pair.get((item, operation), []), jc_rm, psd.rm_codes
        )
        if len(exist_jcr) > 1:
            # Keep the oldest Job Card
            print(f"For Item: {item} and Operation: {operation} there are {len(exist_jcr)} Job Cards. "
                "Keeping the oldest one.")
            plan.delete += [jc.name for jc in exist_jcr[1:]]
            exist_jcr = exist_jcr[:1]
        op_qty = get_actual_qty_before_process_in_ps(
            psd=psd, itd=item_rows[item], operation=operation, qty_dict=qty_maps[item],
            subcon=subcon, bin_qty=bin_qty,
        )
        if op_qty <= 0:
            # Since no Qty in For Operation hence stop all the Operations
            print(f"Stopped Operation {operation} for {item} for Process Sheet {last.ps_name} as "
                "No Qty in Manufacturing before this Operation")
            plan.stop[last.name] = last.op_status
        elif op_qty != last.op_pen_qty:
            plan.planned_qty[last.name] = op_qty + last.completed_qty
            if exist_jcr:
                jc_name = exist_jcr[0].name
                operation_id = {jc.name: jc.operation_id for jc in jc_by_pair[(item, operation)]}
                if operation_id.get(jc_name) == last.name:
                    plan.jc_qty[jc_name] = op_qty
                else:
                    plan.delete.append(jc_name)
            else:
                plan.create.append((last, op_qty))
        elif not exist_jcr:
            plan.unchanged += 1
            plan.create.append((last, op_qty))
        else:
            plan.unchanged += 1
    return plan


def get_light_process_sheets(ps_names):
    """
    Returns {Process Sheet: _dict(name, operations, rm_codes)} with the fields that the
    consolidation needs, in 2 queries for each chunk
    """
    sheets = {name: frappe._dict(name=name, operations=[], rm_codes=[]) for name in ps_names}
    for chunk in chunks(ps_names):
        for row in frappe.get_all(
            "BOM Operation",
            filters={"parenttype": "Process Sheet", "parent": ("in", chunk)},
            fields=["parent", "name", "idx", "operation", "transfer_entry", "source_warehouse",
                "allow_consumption_of_rm"],
            order_by="idx",
        ):
            sheets[row.parent].operations.append(row)
        for row in frappe.get_all(
            "Process Sheet Items",
            filters={"parenttype": "Process Sheet", "parentfield": "rm_consumed", "parent": ("in", chunk)},
            fields=["parent", "item_code"],
            order_by="idx",
        ):
            sheets[row.parent].rm_codes.append(row.item_code)
    return sheets


def get_bin_actual_qty(pairs):
    """
    Returns {(item, warehouse): actual_qty} for the pairs, in 1 query for each chunk of items
    """
    pairs = {(item, wh) for item, wh in pairs if wh}
    result = {}
    for chunk in chunks(item for item, _wh in pairs):
        for row in frappe.get_all(
            "Bin",
            filters={"item_code": ("in", chunk), "warehouse": ("in", list({wh for _it, wh in pairs}))},
            fields=["item_code", "warehouse", "actual_qty"],
        ):
            result[(row.item_code, row.warehouse)] = flt(row.actual_qty)
    return result


def commit_if_needed(writes, st_time):
    writes += 1
    if writes % COMMIT_EVERY == 0:
        print(f"Committing Changes after {writes} Changes and Time Taken = "
            f"{int(time.time() - st_time)} seconds")
        frappe.db.commit()
    return writes


def update_process_sheet_priority():
    """
    Gets all the process sheets in Draft or Submitted and updates its priority.
    """
    st_time = time.time()
    ps_list = frappe.get_all(
        "Process Sheet",
        filters=[
            ["docstatus", "<", 2],
            ["status", "is", "set"],
            ["status", "not in", ["Completed", "Short Closed", "Stopped"]],
        ],
        fields=["name", "docstatus", "status", "priority", "production_item", "quantity",
            "sales_order_item"],
        order_by="creation asc",
    )
    item_rows = get_item_rows({psd.production_item for psd in ps_list})
    qty_maps = get_quantities_for_items(item_rows.values())
    so_lines = get_open_so_lines(list(item_rows))
    new_priority, new_status = {}, {}
    for psd in ps_list:
        itd = item_rows.get(psd.production_item)
        if itd is None:
            continue
        new_priority[psd.name] = return_priority_psd(
            psd, itd, qty_dict=qty_maps[itd.name], so_lines=so_lines.get(itd.name, [])
        )
        if psd.docstatus == 0 and psd.status != "Draft":
            new_status[psd.name] = "Draft"
        elif psd.docstatus == 1 and psd.status == "Draft":
            new_status[psd.name] = "Submitted"
    changes = bulk_set_values(
        "Process Sheet", "priority", new_priority, {psd.name: psd.priority for psd in ps_list}
    )
    for name, old, new in changes:
        print(f"Updated Priority for {name} from {old} to {new}")
    status_changes = bulk_set_values(
        "Process Sheet", "status", new_status, {psd.name: psd.status for psd in ps_list}
    )
    for name, _old, new in status_changes:
        print(f"Updated Status for {name} to {new}")
    frappe.db.commit()
    print(f"Total No of Process Sheets where Priority has been Updated = {len(changes)}")
    print(f"Total Time for Updating Priority = {int(time.time() - st_time)} seconds")


def create_new_process_sheets():
    """
    Checks for Requirement of Process Sheet for Each Item Sorted by ROL and Valuation Rate
    Multiplier in descending order
    """
    st_time = time.time()
    value = flt(frappe.get_cached_value("RIGPL Settings", "RIGPL Settings", "auto_process_sheet_value"))
    if value == 0:
        value = 10000
    it_dict = get_manufacturing_items()
    print(f"Total Items Being Considered for Auto Process Sheet = {len(it_dict)}")
    qty_maps = get_quantities_for_items(it_dict)
    settings = get_manufacturing_qty_settings()
    needed = []
    for itm in it_dict:
        qty_dict = qty_maps[itm.name]
        qty, _max_qty = get_qty_to_manufacture(itm, qty_dict=qty_dict, settings=settings)
        if qty * flt(itm.valuation_rate) >= value:
            needed.append((itm, qty))
        elif qty > 0 and qty_dict.on_so > 0:
            # Create PS only if SO qty is MORE than qty in Stock or WIP or PO
            total_process_qty = (qty_dict.on_po + qty_dict.planned_qty +
                qty_dict.finished_qty + qty_dict.wip_qty + qty_dict.dead_qty +
                qty_dict.planned_qty - qty_dict.reserved_for_prd)
            if qty_dict.on_so > total_process_qty:
                needed.append((itm, qty))

    drafts = get_draft_process_sheets([itm.name for itm, _qty in needed])
    created, writes, err_it = 0, 0, []
    for itm, qty in needed:
        vr_rol = flt(itm.valuation_rate) * flt(itm.wh_rol)
        ex_ps = drafts.get(itm.name)
        if ex_ps:
            if ex_ps.quantity == qty:
                continue
            def change_qty():
                psd = frappe.get_doc("Process Sheet", ex_ps.name)
                psd.quantity = qty
                psd.save()
            if run_write("ps_qty", change_qty, f"Process Sheet {ex_ps.name} qty not changed to {qty}"):
                print(f"Updated {ex_ps.name} Changed Quantity from {ex_ps.quantity} to {qty} for "
                    f"{itm.name} VR*ROL = {vr_rol}")
        else:
            def make_ps():
                psd = frappe.new_doc("Process Sheet")
                psd.production_item = itm.name
                psd.date = today()
                psd.quantity = qty
                psd.status = "Draft"
                psd.insert()
                print(f"Created {psd.name} for {itm.name} for Qty= {qty} VR*ROL = {vr_rol}")
            if run_write("ps_new", make_ps, f"Process Sheet not created for {itm.name} Qty = {qty}"):
                created += 1
            else:
                err_it.append(itm.name)
        writes = commit_if_needed(writes, st_time)
    frappe.db.commit()
    print(f"List of Items where New Process Sheet cannot be Made \n {err_it}")
    print(f"Total Process Sheets Created = {created}")
    print(f"Total Time for Creation of Process Sheets = {int(time.time() - st_time)} seconds")


def get_manufacturing_items():
    """
    Returns the manufacturing variants, the highest valuation rate * ROL first. An item with
    more than one Item Reorder row comes once, with its first row.
    """
    it = frappe.qb.DocType("Item")
    rol = frappe.qb.DocType("Item Reorder")
    vr_rol = it.valuation_rate * rol.warehouse_reorder_level
    rows = (
        frappe.qb.from_(it)
        .left_join(rol).on((rol.parent == it.name) & (rol.parenttype == "Item"))
        .select(
            it.name, it.valuation_rate, it.lead_time_days, it.made_to_order,
            rol.warehouse_reorder_level.as_("wh_rol"),
        )
        .where((it.disabled == 0) & (it.include_item_in_manufacturing == 1))
        .where((it.has_variants == 0) & it.variant_of.isnotnull())
        .orderby(vr_rol, order=frappe.qb.desc)
        .orderby(it.valuation_rate, order=frappe.qb.desc)
        .orderby(rol.warehouse_reorder_level, order=frappe.qb.desc)
        .orderby(it.name)
        .run(as_dict=True)
    )
    seen, items = set(), []
    for row in rows:
        if row.name not in seen:
            seen.add(row.name)
            items.append(row)
    return items


def get_draft_process_sheets(item_names):
    """
    Returns {item: its oldest draft Process Sheet (name, quantity)}
    """
    drafts = {}
    for chunk in chunks(item_names):
        for row in frappe.get_all(
            "Process Sheet",
            filters={"docstatus": 0, "production_item": ("in", chunk)},
            fields=["name", "production_item", "quantity"],
            order_by="creation asc",
        ):
            drafts.setdefault(row.production_item, row)
    return drafts
