# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals

import json
from datetime import date

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt

from ...utils.batch_write_utils import bulk_set_values
from ...utils.item_attribute_utils import chunks
from ...utils.stock_utils import get_quantities_for_item
from .job_card_utils import (
    check_existing_job_card,
    create_job_card,
    get_bin,
    get_existing_job_cards,
    update_job_card_total_qty,
)
from .manufacturing_utils import (
    check_jc_needed_for_ps,
    convert_rule_to_mysql_statement,
    convert_wip_rule_to_mysql_statement,
    get_bom_template_from_item,
    update_planned_qty,
    update_qty_for_prod,
)


def get_last_operation_for_psheet(psdoc, no_cons_ld_time):
    """
    Returns the Last Operation for a Process Sheet Doc
    no_cons_ld_time is Boolean basically if Not Consider Operation in Lead time is a check in
    operation master also if the BOM template has checked it can be used
    """
    op_names = [opr.operation for opr in psdoc.operations]
    if len(op_names) < 2:
        return None
    last_op, prev_op = op_names[-1], op_names[-2]
    op_flags = dict(
        frappe.get_all(
            "Operation",
            filters={"name": ("in", [last_op, prev_op])},
            fields=["name", "dont_consider_in_lead_time"],
            as_list=True,
        )
    )
    bop = frappe.qb.DocType("BOM Operation")
    bt_flags = dict(
        frappe.qb.from_(bop)
        .select(bop.operation, Sum(bop.dont_consider_in_lead_time))
        .where(bop.parenttype == "BOM Template RIGPL")
        .where(bop.parent == psdoc.bom_template)
        .where(bop.operation.isin([last_op, prev_op]))
        .groupby(bop.operation)
        .run()
    )
    return pick_last_operation(op_names, op_flags, bt_flags, no_cons_ld_time)


def pick_last_operation(op_names, op_flags, bt_flags, no_cons_ld_time):
    """
    Returns the Last Operation from the operation names of a Process Sheet in order
    op_flags is {operation: Dont Consider in Lead Time of the Operation} and bt_flags is
    {operation: sum of the same flag in the BOM Template}
    """
    tot_operations = len(op_names)
    if tot_operations < 2:
        return None
    val = tot_operations - 1
    last_op, prev_op = op_names[val], op_names[val - 1]
    if no_cons_ld_time == op_flags.get(last_op) or no_cons_ld_time == flt(bt_flags.get(last_op)):
        if no_cons_ld_time == op_flags.get(prev_op) or no_cons_ld_time == flt(bt_flags.get(prev_op)):
            return op_names[val - 2]
        else:
            return op_names[val - 1]
    else:
        return op_names[val]


def get_actual_qty_before_process_in_ps(psd, itd, operation, qty_dict=None, subcon=None, bin_qty=None):
    """
    Returns the qty of the item in production before `operation` of the Process Sheet. When
    checking many sheets, pass `qty_dict` (get_quantities_for_items), `subcon`
    ({operation: is_subcontracting}) and `bin_qty` ({(item, warehouse): actual_qty}).
    """
    def is_subcontracting(op_name):
        if subcon is not None:
            return subcon.get(op_name)
        return frappe.get_value("Operation", op_name, "is_subcontracting")

    def actual_qty(warehouse):
        if bin_qty is not None:
            return flt(bin_qty.get((itd.name, warehouse)))
        return flt(get_bin(item_code=itd.name, warehouse=warehouse).get("actual_qty"))

    qty_before_process, op_idx, add_po = 0, 0, 0
    self_subcon_op = is_subcontracting(operation)
    if qty_dict is None:
        qty_dict = get_quantities_for_item(it_doc=itd)
    for d in psd.operations:
        if d.operation == operation:
            op_idx = d.idx
    if op_idx > 0:
        qty_before_process += qty_dict["planned_qty"]
        if op_idx > 1:
            # Sum of all quantities before the operation is actual qty for all process source warehouse
            s_wh_list = []
            for d in psd.operations:
                if self_subcon_op == 1:
                    add_po = 0
                if d.idx <= op_idx:
                    oth_subcon = is_subcontracting(d.operation)
                    if d.transfer_entry == 1:
                        if d.source_warehouse not in s_wh_list:
                            s_wh_list.append(d.source_warehouse)
                    if oth_subcon == 1:
                        # IF subcontracting is there then add on_po qty to the process
                        add_po = 1
            for w_house in s_wh_list:
                qty_before_process += actual_qty(w_house)
            if add_po == 1:
                qty_before_process += qty_dict["on_po"]
    return qty_before_process


def get_pend_psop(it_name=None, operation=None, tf_ent=None):
    """
    Returns the pending operations of submitted Process Sheets, by item, operation and the
    creation of the Process Sheet
    """
    ps = frappe.qb.DocType("Process Sheet")
    pso = frappe.qb.DocType("BOM Operation")
    query = (
        frappe.qb.from_(ps)
        .join(pso).on((pso.parent == ps.name) & (pso.parenttype == "Process Sheet"))
        .select(
            ps.name.as_("ps_name"), pso.name.as_("name"), pso.operation, pso.planned_qty,
            pso.completed_qty, pso.status.as_("op_status"), ps.status, ps.production_item,
            ps.sales_order_item, pso.allow_consumption_of_rm, pso.transfer_entry, pso.idx,
            (pso.planned_qty - pso.completed_qty).as_("op_pen_qty"), pso.workstation,
            pso.source_warehouse, pso.target_warehouse, pso.final_operation,
            pso.allow_production_of_wip_materials,
        )
        .where(ps.docstatus == 1)
        .where(pso.status.notin(["Completed", "Short Closed", "Stopped", "Obsolete"]))
        .where(pso.planned_qty > pso.completed_qty)
        .orderby(ps.production_item)
        .orderby(pso.operation)
        .orderby(ps.creation)
    )
    if it_name:
        query = query.where(ps.production_item == it_name)
    if operation:
        query = query.where(pso.operation == operation)
    if tf_ent in (0, 1):
        query = query.where(pso.transfer_entry == tf_ent)
    return query.run(as_dict=True)


def get_psop_trans_pend_qty(it_name, operation):
    qty_dict = frappe.db.sql(
        """SELECT SUM(psop.planned_qty - psop.completed_qty) as pend_qty,
    COUNT(psop.name) as no_of_ops FROM `tabProcess Sheet` ps, `tabBOM Operation` psop
    WHERE ps.docstatus = 1 AND psop.parent = ps.name AND psop.parenttype = 'Process Sheet' AND
    psop.transfer_entry = 1 AND psop.status NOT IN ('Completed', 'Short Closed', 'Stopped', 'Obsolete')
    AND ps.status NOT IN ('Stopped', 'Short Closed') AND ps.production_item = '%s'
    AND psop.operation = '%s'"""
        % (it_name, operation),
        as_dict=1,
    )
    return qty_dict


def update_process_sheet_operations(ps_name, op_name, psd=None, btd=None):
    """
    Updates the status and completed qty of one operation from its submitted Job Cards.
    `psd` and `btd` are the Process Sheet and its BOM Template, when the caller has them loaded.
    Returns 1 when the operation changed.
    """
    if psd is None:
        psd = frappe.get_doc("Process Sheet", ps_name)
    template_ops = [op.operation for op in btd.operations] if btd is not None else None
    new = update_ps_operations(psd, op_names=[op_name], template_ops=template_ops)
    return 1 if op_name in new and new[op_name].changed else 0


def update_ps_operations(psd, op_names=None, template_ops=None):
    """
    Updates the status and completed qty of the operations `op_names` (all operations when None)
    of the Process Sheet `psd` from their submitted Job Cards, with 3 queries and 1 write for each
    changed value. `template_ops` are the operation names of the BOM Template, when the caller has
    them. The rows of `psd.operations` get the new values.
    Returns {op_name: {status, completed_qty, changed}}.
    """
    filters = {"parenttype": "Process Sheet", "parent": psd.name}
    if op_names is not None:
        if not op_names:
            return {}
        filters["name"] = ("in", op_names)
    op_rows = frappe.get_all(
        "BOM Operation",
        filters=filters,
        fields=["name", "operation", "status", "completed_qty", "planned_qty"],
    )
    if not op_rows:
        return {}
    if template_ops is None:
        template_ops = frappe.get_all(
            "BOM Operation",
            filters={"parenttype": "BOM Template RIGPL", "parent": psd.bom_template},
            pluck="operation",
        )
    jcr = frappe.qb.DocType("Process Job Card RIGPL")
    totals = {
        row.operation_id: row
        for row in (
            frappe.qb.from_(jcr)
            .select(
                jcr.operation_id,
                Sum(jcr.total_completed_qty).as_("comp_qty"),
                Sum(jcr.short_close_operation).as_("sc_op"),
            )
            .where(jcr.docstatus == 1)
            .where(jcr.process_sheet == psd.name)
            .where(jcr.operation_id.isin([op.name for op in op_rows]))
            .groupby(jcr.operation_id)
            .run(as_dict=True)
        )
    }
    template_ops = set(template_ops)
    new_values = {}
    for opd in op_rows:
        completed_qty, status = get_operation_values(
            opd, totals.get(opd.name), psd.status, template_ops
        )
        new_values[opd.name] = frappe._dict(
            status=status,
            completed_qty=completed_qty,
            changed=(status, completed_qty) != (opd.status, opd.completed_qty),
        )

    for field in ("completed_qty", "status"):
        bulk_set_values(
            "BOM Operation",
            field,
            {name: values[field] for name, values in new_values.items()},
            {opd.name: opd[field] for opd in op_rows},
        )
    for row in psd.operations:
        if row.name in new_values:
            row.status = new_values[row.name].status
            row.completed_qty = new_values[row.name].completed_qty
    return new_values


def get_operation_values(opd, jc, ps_status, template_ops):
    """
    Returns (completed_qty, status) of the Process Sheet operation `opd` from `jc`, the sums of
    its submitted Job Cards (None when there are none).
    """
    completed_qty, status = opd.completed_qty, opd.status
    obsolete = 0 if opd.operation in template_ops else 1
    if obsolete == 1:
        status = "Obsolete"

    comp_qty = flt(jc.comp_qty) if jc else 0
    sclose = flt(jc.sc_op) if jc else 0
    if comp_qty:
        completed_qty = comp_qty
        if comp_qty >= opd.planned_qty:
            status = "Completed"
        elif sclose >= 1:
            status = "Short Closed"
        elif obsolete != 1:
            status = "In Progress" if ps_status != "Stopped" else "Stopped"
    else:
        completed_qty = 0
        if obsolete != 1:
            if ps_status != "Stopped":
                if sclose >= 1:
                    status = "Short Closed" if completed_qty < opd.planned_qty else "Completed"
                else:
                    status = "Pending"
            else:
                status = "Stopped"
    return completed_qty, status


def update_process_sheet_quantities(ps_doc):
    update_planned_qty(item_code=ps_doc.production_item, warehouse=ps_doc.fg_warehouse)
    for rm in ps_doc.rm_consumed:
        update_qty_for_prod(
            item_code=rm.item_code,
            warehouse=rm.source_warehouse,
            table_name="rm_consumed",
        )


def make_jc_for_process_sheet(ps_doc, template_ops=None):
    """
    Creates the missing Job Cards of the open operations. `template_ops` are the operation names
    of the BOM Template, when the caller has them.
    """
    jcr_needed = check_jc_needed_for_ps(ps_doc)
    if jcr_needed == 1:
        open_rows = {
            row.name: row for row in ps_doc.operations
            if row.status in ("Pending", "In Progress", None)
        }
        existing = get_existing_job_cards(
            ps_doc.production_item,
            [row.operation for row in open_rows.values()],
            so_detail=ps_doc.sales_order_item,
            ps_doc=ps_doc,
        )
        created_ops = []
        for row in ps_doc.operations:
            if row.name in open_rows:
                existing_job_card = existing.get(row.operation)
                if not existing_job_card:
                    # A second row with the same operation uses the Job Card just made
                    existing[row.operation] = [create_job_card(ps_doc, row, auto_create=True)]
                    created_ops.append(row.name)
                else:
                    # Update the Total Quantity for All the Job Cards which are existing
                    for jc in existing_job_card:
                        jcd = frappe.get_doc("Process Job Card RIGPL", jc.name)
                        update_job_card_total_qty(jcd)
                        jcd.save()
            else:
                frappe.msgprint(
                    f"For Row# {row.idx} Status= {row.status} hence No Job Card Created"
                )
        update_ps_operations(ps_doc, op_names=created_ops, template_ops=template_ops)
    else:
        frappe.msgprint(f"No Job Card is Needed for {ps_doc.name}")


def disallow_templates(doc, item_doc):
    if item_doc.has_variants == 1:
        frappe.throw(
            "Template {} is not allowed in BOM {}".format(item_doc.name, doc.name)
        )


def get_req_sizes_from_template(
    bom_temp_name, item_type_list, table_name, allow_zero_rol=None, ps_name=None
):
    # Item Type List is in Format [{known_item: 'Item Name', known_type = 'fg'},{known_item: "Item Name2",
    # known_type="rm"}]
    if allow_zero_rol == 1:
        rol_cond = ""
    else:
        rol_cond = " AND rol.warehouse_reorder_level > 0"
    bt_doc = frappe.get_doc("BOM Template RIGPL", bom_temp_name)
    att_join = ""
    att_cond = ""
    for d in bt_doc.get(table_name):
        att_table = d.attribute.replace(" ", "")
        if d.is_numeric != 1:
            if d.allowed_values != "No":
                att_cond += " AND %s.attribute_value = '%s'" % (
                    att_table,
                    d.allowed_values,
                )
                att_join += (
                    " LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent "
                    "AND %s.parenttype = 'Item' AND %s.attribute = '%s'"
                    % (att_table, att_table, att_table, att_table, d.attribute)
                )
        else:
            for item in item_type_list:
                att_cond += convert_rule_to_mysql_statement(
                    d.rule, item, process_sheet_name=ps_name
                )
                att_join += (
                    " LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent AND %s.parenttype = "
                    "'Item' AND %s.attribute = '%s'"
                    % (att_table, att_table, att_table, att_table, d.attribute)
                )

    query = """SELECT it.name, it.description FROM `tabItem` it LEFT JOIN `tabItem Reorder` rol ON
    it.parenttype = 'Item' AND it.parent = it.name %s WHERE it.disabled = 0 AND it.end_of_life >= CURDATE() %s %s""" % (
        att_join,
        att_cond,
        rol_cond,
    )
    it_dict = frappe.db.sql(query, as_dict=1)
    return it_dict


def get_req_wip_sizes_from_template(
    bom_temp_name, fg_item, rm_item, table_name, process_sheet_name, allow_zero_rol=None
):
    if allow_zero_rol == 1:
        rol_cond = ""
    else:
        rol_cond = " AND rol.warehouse_reorder_level > 0"
    bt_doc = frappe.get_doc("BOM Template RIGPL", bom_temp_name)
    if bt_doc.get(table_name):
        att_join = ""
        att_cond = ""
        for d in bt_doc.get(table_name):
            att_table = d.attribute.replace(" ", "")
            if d.is_numeric != 1:
                if d.allowed_values != "No":
                    att_cond += " AND %s.attribute_value = '%s'" % (
                        att_table,
                        d.allowed_values,
                    )
                    att_join += (
                        " LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent "
                        "AND %s.parenttype = 'Item' AND %s.attribute = '%s'"
                        % (att_table, att_table, att_table, att_table, d.attribute)
                    )
            else:
                att_cond += convert_wip_rule_to_mysql_statement(
                    d.rule, fg_item, rm_item, process_sheet_name
                )
                att_join += (
                    " LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent "
                    "AND %s.parenttype = 'Item' AND %s.attribute = '%s'"
                    % (att_table, att_table, att_table, att_table, d.attribute)
                )

        query = """SELECT it.name, it.description FROM `tabItem` it LEFT JOIN `tabItem Reorder` rol ON
        rol.parenttype = 'Item' AND rol.parent = it.name %s WHERE it.disabled = 0 AND it.end_of_life >= CURDATE() %s %s
        """ % (
            att_join,
            att_cond,
            rol_cond,
        )
        it_dict = frappe.db.sql(query, as_dict=1)
    else:
        it_dict = {}
    return it_dict


def update_item_table(item_dict, table_name, document):
    table_dict = {}
    for d in item_dict:
        table_dict["item_code"] = d.name
        table_dict["description"] = d.description
        document.append(table_name, table_dict.copy())


def get_produced_qty(item_code, so_item=None):
    prod_qty = 0
    it_doc = frappe.get_doc("Item", item_code)
    if it_doc.include_item_in_manufacturing == 1:
        if it_doc.made_to_order == 1:
            if not so_item:
                frappe.throw(
                    "{} is Made to Order but No SO is defined".format(
                        frappe.get_desk_link("Item", item_code)
                    )
                )
            else:
                qty_list = frappe.db.sql(
                    """SELECT name, quantity, produced_qty FROM `tabProcess Sheet`
                    WHERE docstatus < 2 AND production_item = '%s'
                    AND sales_order_item = '%s'"""
                    % (item_code, so_item),
                    as_dict=1,
                )
                prod_qty = 0
                if qty_list:
                    for qty in qty_list:
                        prod_qty += qty.quantity
        else:
            qty_list = frappe.db.sql(
                """SELECT name, quantity , produced_qty FROM `tabProcess Sheet`
                WHERE docstatus < 2 AND production_item = '%s' """
                % item_code,
                as_dict=1,
            )
            prod_qty = 0
            if qty_list:
                for qty in qty_list:
                    prod_qty += qty.quantity
    return prod_qty


def create_ps_from_so_item(so_row):
    ps_doc = frappe.new_doc("Process Sheet")
    ps_doc.flags.ignore_mandatory = True
    ps_doc.production_item = so_row.item_code
    ps_doc.description = so_row.description
    ps_doc.date = date.today()
    ps_doc.quantity = so_row.qty
    ps_doc.sales_order = so_row.parent
    ps_doc.sales_order_item = so_row.name
    ps_doc.sno = so_row.idx
    ps_doc.status = "Draft"
    ps_doc.insert()
    frappe.msgprint(
        "Created {} for Row# {}".format(
            frappe.get_desk_link("Process Sheet", ps_doc.name), so_row.idx
        )
    )


def get_ps_for_change(ps_name, ptype):
    """
    Returns the Process Sheet `ps_name` after it checks that the user has `ptype` permission on it.
    """
    if not isinstance(ps_name, str):
        frappe.throw(_("Process Sheet must be a name"), title=_("Invalid Arguments"))
    ps_doc = frappe.get_doc("Process Sheet", ps_name)
    frappe.has_permission("Process Sheet", ptype, ps_doc, throw=True)
    return ps_doc


def delete_draft_job_cards(filters, show_message=True):
    """
    Deletes the draft Job Cards that match `filters` and returns their names. delete_doc is
    used for each one, because it also checks the links and deletes the child rows.
    """
    jc_list = frappe.get_all(
        "Process Job Card RIGPL", filters=dict(filters, docstatus=0), pluck="name"
    )
    for jc in jc_list:
        frappe.delete_doc("Process Job Card RIGPL", jc, for_reload=True)
    if jc_list and show_message:
        frappe.msgprint(_("Deleted {0}").format(", ".join(jc_list)))
    return jc_list


def stop_operations(op_status, show_message=True):
    """
    Sets the status of the Process Sheet operations to Stopped and deletes their draft Job Cards.
    `op_status` is {operation row name: its status now}, so that only changed rows are written.
    """
    if not op_status:
        return []
    deleted = []
    for chunk in chunks(op_status):
        deleted += delete_draft_job_cards({"operation_id": ("in", chunk)}, show_message)
    bulk_set_values("BOM Operation", "status", {name: "Stopped" for name in op_status}, op_status)
    return deleted


@frappe.whitelist()
def stop_ps_operation(op_id, ps_name=None, psd=None):
    """
    Stops the operation `op_id` of the Process Sheet `ps_name` and deletes its draft Job Cards.
    `psd` (the form doc as JSON) is accepted for old callers.
    """
    if ps_name is None and psd:
        ps_name = (json.loads(psd) if isinstance(psd, str) else psd).get("name")
    ps_doc = get_ps_for_change(ps_name, "cancel")
    row = next((op for op in ps_doc.operations if op.name == op_id), None)
    if row is None:
        frappe.throw(
            _("Row {0} is not an operation of {1}").format(op_id, ps_name),
            title=_("Operation Not in Process Sheet"),
        )
    stop_operations({row.name: row.status})
    row.status = "Stopped"


@frappe.whitelist()
def stop_process_sheet(ps_name):
    ps_doc = get_ps_for_change(ps_name, "cancel")
    if ps_doc.status == "In Progress":
        if ps_doc.produced_qty >= ps_doc.quantity:
            ps_doc.status = "Completed"
        else:
            ps_doc.status = "Stopped"
        delete_draft_job_cards({"process_sheet": ps_doc.name})
    ps_doc.save()
    update_process_sheet_quantities(ps_doc)
    update_ps_operations(ps_doc)


@frappe.whitelist()
def unstop_process_sheet(ps_name):
    ps_doc = get_ps_for_change(ps_name, "cancel")
    if ps_doc.produced_qty < ps_doc.quantity:
        ps_doc.status = "In Progress"
    else:
        if ps_doc.short_closed_qty > 0:
            ps_doc.status = "Short Closed"
        else:
            ps_doc.status = "Completed"
    # Recompute each operation from its Job Cards. update_ps_operations also sets the new values
    # on ps_doc.operations, so that the save below does not write the old values again
    update_ps_operations(ps_doc)
    open_rows = []
    for op in ps_doc.operations:
        if op.status not in ("Completed", "Short Closed", "Obsolete"):
            op.status = "In Progress" if op.completed_qty > 0 else "Pending"
            open_rows.append(op)
    existing = get_existing_job_cards(
        ps_doc.production_item,
        [op.operation for op in open_rows],
        so_detail=ps_doc.sales_order_item,
        ps_doc=ps_doc,
    )
    for op in open_rows:
        if not existing.get(op.operation):
            existing[op.operation] = [create_job_card(ps_doc, op, auto_create=True)]
    ps_doc.save()
    update_process_sheet_quantities(ps_doc)


@frappe.whitelist()
def get_bom_template_from_item_name(
    doctype, txt, searchfield, start, page_len, filters, as_dict
):
    so_detail = filters.get("so_detail")
    it_doc = frappe.get_doc("Item", filters.get("it_name"))
    bt_list = get_bom_template_from_item(it_doc, so_detail)
    if not bt_list:
        frappe.throw("NO BOM Template Found")
    bt = frappe.qb.DocType("BOM Template RIGPL")
    return (
        frappe.qb.from_(bt)
        .select(bt.name, bt.title, bt.remarks)
        .where(bt.name.isin(list(bt_list)))
        .run(as_dict=as_dict)
    )


