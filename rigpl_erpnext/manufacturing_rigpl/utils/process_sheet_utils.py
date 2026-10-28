# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals

from datetime import date

import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import flt

from ...utils.stock_utils import get_quantities_for_item
from .job_card_utils import (
    check_existing_job_card,
    create_job_card,
    get_bin,
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


def get_actual_qty_before_process_in_ps(psd, itd, operation):
    qty_before_process, op_idx, add_po = 0, 0, 0
    self_subcon_op = frappe.get_value("Operation", operation, "is_subcontracting")
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
                    oth_subcon = frappe.get_value(
                        "Operation", d.operation, "is_subcontracting"
                    )
                    if d.transfer_entry == 1:
                        if d.source_warehouse not in s_wh_list:
                            s_wh_list.append(d.source_warehouse)
                    if oth_subcon == 1:
                        # IF subcontracting is there then add on_po qty to the process
                        add_po = 1
            for w_house in s_wh_list:
                qty_before_process += flt(
                    get_bin(item_code=itd.name, warehouse=w_house).get("actual_qty")
                )
            if add_po == 1:
                qty_before_process += qty_dict["on_po"]
    return qty_before_process


def get_pend_psop(it_name=None, operation=None, tf_ent=None):
    cond = ""
    if it_name:
        cond += " AND ps.production_item = '%s'" % it_name
    if operation:
        cond += " AND pso.operation = '%s'" % operation
    if tf_ent == 1:
        cond += " AND pso.transfer_entry = 1"
    elif tf_ent == 0:
        cond += " AND pso.transfer_entry = 0"

    return frappe.db.sql(
        """SELECT ps.name as ps_name, pso.name AS name, pso.operation, pso.planned_qty,
        pso.completed_qty, pso.status AS op_status, ps.status, ps.production_item, pso.operation, ps.sales_order_item,
        pso.allow_consumption_of_rm, pso.transfer_entry, pso.idx, (pso.planned_qty - pso.completed_qty) as op_pen_qty,
        pso.workstation, pso.source_warehouse, pso.target_warehouse, pso.final_operation,
        pso.allow_production_of_wip_materials
        FROM `tabProcess Sheet` ps, `tabBOM Operation` pso WHERE ps.docstatus = 1 AND pso.parent = ps.name
        AND pso.parenttype = 'Process Sheet' AND pso.status NOT IN ('Completed', 'Short Closed', 'Stopped', 'Obsolete')
        AND pso.planned_qty > pso.completed_qty %s
        ORDER BY ps.production_item, pso.operation, ps.creation"""
        % cond,
        as_dict=1,
    )


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
    """
    changes_made = 0
    obsolete = 1
    opd = frappe.get_doc("BOM Operation", op_name)
    if psd is None:
        psd = frappe.get_doc("Process Sheet", ps_name)
    if btd is None:
        btd = frappe.get_doc("BOM Template RIGPL", psd.bom_template)
    for op in btd.operations:
        if op.operation == opd.operation:
            obsolete = 0
            break
    if obsolete == 1:
        if opd.status != "Obsolete":
            opd.status = "Obsolete"
            changes_made = 1

    jcr = frappe.qb.DocType("Process Job Card RIGPL")
    jc_comp = (
        frappe.qb.from_(jcr)
        .select(
            Sum(jcr.total_completed_qty).as_("comp_qty"),
            Sum(jcr.short_close_operation).as_("sc_op"),
            Sum(jcr.transfer_entry).as_("transfer"),
            Sum(jcr.qty_available).as_("avail_qty"),
        )
        .where(jcr.docstatus == 1)
        .where(jcr.operation_id == op_name)
        .where(jcr.process_sheet == ps_name)
        .run(as_dict=True)
    )
    jc = jc_comp[0]
    comp_qty = flt(jc.comp_qty)
    sclose = flt(jc.sc_op)
    if jc.comp_qty:
        if comp_qty != opd.completed_qty:
            opd.completed_qty = jc.comp_qty
            changes_made = 1
        if comp_qty >= opd.planned_qty:
            if opd.status != "Completed":
                opd.status = "Completed"
                changes_made = 1
        else:
            if sclose >= 1:
                if opd.status != "Short Closed":
                    opd.status = "Short Closed"
                    changes_made = 1
            else:
                if psd.status != "Stopped":
                    if opd.status != "In Progress" and obsolete != 1:
                        opd.status = "In Progress"
                        changes_made = 1
                else:
                    if opd.status != "Stopped" and obsolete != 1:
                        opd.status = "Stopped"
                        changes_made = 1
    else:
        if opd.completed_qty > 0:
            opd.completed_qty = 0
            changes_made = 1
        if psd.status != "Stopped":
            if obsolete != 1:
                if sclose >= 1:
                    if opd.completed_qty < opd.planned_qty:
                        if opd.status != "Short Closed":
                            opd.status = "Short Closed"
                            changes_made = 1
                    else:
                        if opd.status != "Completed":
                            opd.status = "Completed"
                            changes_made = 1
                else:
                    if opd.status != "Pending":
                        opd.status = "Pending"
                        changes_made = 1
        else:
            if obsolete != 1:
                if opd.status != "Stopped":
                    opd.status = "Stopped"
                    changes_made = 1
    if changes_made == 1:
        opd.save()
    return changes_made


def update_process_sheet_quantities(ps_doc):
    update_planned_qty(item_code=ps_doc.production_item, warehouse=ps_doc.fg_warehouse)
    for rm in ps_doc.rm_consumed:
        update_qty_for_prod(
            item_code=rm.item_code,
            warehouse=rm.source_warehouse,
            table_name="rm_consumed",
        )


def make_jc_for_process_sheet(ps_doc):
    jcr_needed = check_jc_needed_for_ps(ps_doc)
    if jcr_needed == 1:
        btd = frappe.get_doc("BOM Template RIGPL", ps_doc.bom_template)
        for row in ps_doc.operations:
            if (
                row.status == "Pending"
                or row.status == "In Progress"
                or row.status is None
            ):
                existing_job_card = check_existing_job_card(
                    item_name=ps_doc.production_item,
                    operation=row.operation,
                    so_detail=ps_doc.sales_order_item,
                    ps_doc=ps_doc,
                )
                if not existing_job_card:
                    create_job_card(ps_doc, row, auto_create=True)
                    update_process_sheet_operations(ps_doc.name, row.name, psd=ps_doc, btd=btd)
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


@frappe.whitelist()
def stop_ps_operation(op_id, psd):
    opd = frappe.get_doc("BOM Operation", op_id)
    allowed = get_process_sheet_permission(psd)
    if allowed == 1:
        jcl = frappe.get_all(
            "Process Job Card RIGPL", filters={"docstatus": 0, "operation_id": op_id}, pluck="name"
        )
        for jc in jcl:
            frappe.delete_doc("Process Job Card RIGPL", jc, for_reload=True)
            frappe.msgprint(f"Deleted {jc}")
        opd.status = "Stopped"
        opd.save()
    else:
        frappe.throw(f"Don't Have Permission to Stop Process")


@frappe.whitelist()
def stop_process_sheet(ps_name):
    ps_doc = frappe.get_doc("Process Sheet", ps_name)
    allowed = get_process_sheet_permission(ps_doc)
    if allowed == 1:
        if ps_doc.status == "In Progress":
            if ps_doc.produced_qty >= ps_doc.quantity:
                ps_doc.status = "Completed"
            else:
                ps_doc.status = "Stopped"
            # Delete Job Cards for Process Sheeet
            jc_list = frappe.get_all(
                "Process Job Card RIGPL",
                filters={"docstatus": 0, "process_sheet": ps_doc.name},
                pluck="name",
            )
            for jc in jc_list:
                frappe.delete_doc("Process Job Card RIGPL", jc, for_reload=True)
        ps_doc.save()
        for d in ps_doc.operations:
            if d.status == "In Progress" or d.status == "Pending":
                d.status = "Stopped"
        update_process_sheet_quantities(ps_doc)
        btd = frappe.get_doc("BOM Template RIGPL", ps_doc.bom_template)
        for op in ps_doc.operations:
            update_process_sheet_operations(ps_doc.name, op.name, psd=ps_doc, btd=btd)
    else:
        frappe.throw(
            "Don't Have Permission to Stop or Unstop Process Sheet {}".format(ps_name)
        )


@frappe.whitelist()
def unstop_process_sheet(ps_name):
    ps_doc = frappe.get_doc("Process Sheet", ps_name)
    allowed = get_process_sheet_permission(ps_doc)
    if allowed == 1:
        if ps_doc.produced_qty < ps_doc.quantity:
            ps_doc.status = "In Progress"
        else:
            if ps_doc.short_closed_qty > 0:
                ps_doc.status = "Short Closed"
            else:
                ps_doc.status = "Completed"
        # Recompute each operation from its Job Cards, then read the new values back, so that the
        # save below does not write the old values again
        for op in ps_doc.operations:
            update_process_sheet_operations(ps_doc.name, op.name)
        new_values = {
            d.name: d
            for d in frappe.get_all(
                "BOM Operation",
                filters={"parenttype": "Process Sheet", "parent": ps_doc.name},
                fields=["name", "status", "completed_qty"],
            )
        }
        for op in ps_doc.operations:
            if op.name in new_values:
                op.status = new_values[op.name].status
                op.completed_qty = new_values[op.name].completed_qty
            if op.status not in ("Completed", "Short Closed", "Obsolete"):
                if op.completed_qty > 0:
                    op.status = "In Progress"
                else:
                    op.status = "Pending"
                existing_job_card = check_existing_job_card(
                    item_name=ps_doc.production_item,
                    operation=op.operation,
                    so_detail=ps_doc.sales_order_item,
                    ps_doc=ps_doc,
                )
                if not existing_job_card:
                    create_job_card(ps_doc, op, auto_create=True)
        ps_doc.save()
        update_process_sheet_quantities(ps_doc)
    else:
        frappe.throw(
            "Don't Have Permission to Un-Stop Process Sheet {}".format(ps_name)
        )


def get_process_sheet_permission(ps_doc):
    user = frappe.session.user
    usr_roles = set(
        frappe.get_all("Has Role", filters={"parenttype": "User", "parent": user}, pluck="role")
    )
    if "System Manager" in usr_roles:
        return 1
    perm_filters = {"parenttype": "DocType", "parent": ps_doc.doctype, "cancel": 1}
    custom_perm_cancel = frappe.get_all("Custom DocPerm", filters=perm_filters, pluck="role")
    if custom_perm_cancel:
        for role in custom_perm_cancel:
            if role in usr_roles:
                return 1
    else:
        std_perm_cancel = frappe.get_all("DocPerm", filters=perm_filters, pluck="role")
        for role in std_perm_cancel:
            if role in usr_roles:
                return 1
    return 0


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


