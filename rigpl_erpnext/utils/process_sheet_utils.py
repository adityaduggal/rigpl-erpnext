# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from datetime import date
from frappe.utils import flt
from .manufacturing_utils import *
from .job_card_utils import check_existing_job_card, create_job_card, update_job_card_total_qty


def update_process_sheet_op_planned_qty(ps_name, op_name):
    # This is needed because the stock might decrease from the one in FG like Round Tool Bits etc
    ch_made = 0
    opd = frappe.get_doc("BOM Operation", op_name)
    psd = frappe.get_doc("Process Sheet", ps_name)
    if opd.transfer_entry == 1:
        # Check the Job Cards for this Operation in Draft and other PS op with same Operation and Transfer Entry
        # Total pending in All Job Cards should be equal to the qty available + prior incoming if any.
        # Total Pending = Qty Availlable + Pending in Production Job Cards
        pass


def update_process_sheet_operations(ps_name, op_name):
    changes_made = 0
    obsolete = 1
    opd = frappe.get_doc("BOM Operation", op_name)
    psd = frappe.get_doc("Process Sheet", ps_name)
    btd = frappe.get_doc("BOM Template RIGPL", psd.bom_template)
    for op in btd.operations:
        if op.operation == opd.operation:
            obsolete = 0
            break
    if obsolete == 1:
        if opd.status != "Obsolete":
            opd.status = "Obsolete"
            changes_made = 1

    jc_comp = frappe.db.sql("""SELECT SUM(total_completed_qty) AS comp_qty, SUM(short_close_operation) AS sc_op,
    SUM(transfer_entry) AS transfer, SUM(qty_available) AS avail_qty
    FROM `tabProcess Job Card RIGPL` WHERE docstatus = 1 AND operation_id = '%s' 
    AND process_sheet = '%s'""" %(op_name, ps_name), as_dict=1)
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
                    if opd.status != "Short Closed":
                        opd.status = "Short Closed"
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
        update_qty_for_prod(item_code=rm.item_code, warehouse=rm.source_warehouse, table_name="rm_consumed")


def make_jc_for_process_sheet(ps_doc):
    for row in ps_doc.operations:
        if row.status == "Pending" or row.status == "In Progress":
            existing_job_card = check_existing_job_card(item_name=ps_doc.production_item, operation=row.operation,
                                                        so_detail=ps_doc.sales_order_item, ps_doc=ps_doc)
            if not existing_job_card:
                create_job_card(ps_doc, row, auto_create=True)
                update_process_sheet_operations(ps_doc.name, row.name)
            else:
                # Update the Total Quantity for All the Job Cards which are existing
                for jc in existing_job_card:
                    jcd = frappe.get_doc("Process Job Card RIGPL", jc.name)
                    update_job_card_total_qty(jcd)
                    jcd.save()


def disallow_templates(doc, item_doc):
    if item_doc.has_variants == 1:
        frappe.throw('Template {} is not allowed in BOM {}'.format(item_doc.name, doc.name))


def get_req_sizes_from_template(bom_temp_name, item_type_list, table_name, allow_zero_rol=None, ps_name=None):
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
            if d.allowed_values != 'No':
                att_cond += " AND %s.attribute_value = '%s'" % (att_table, d.allowed_values)
                att_join += " LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent " \
                            "AND %s.parenttype = 'Item' AND %s.attribute = '%s'" % \
                            (att_table, att_table, att_table, att_table, d.attribute)
        else:
            for item in item_type_list:
                att_cond += convert_rule_to_mysql_statement(d.rule, item, process_sheet_name=ps_name)
                att_join += " LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent AND %s.parenttype = " \
                            "'Item' AND %s.attribute = '%s'" % (att_table, att_table, att_table, att_table, d.attribute)

    query = """SELECT it.name, it.description FROM `tabItem` it LEFT JOIN `tabItem Reorder` rol ON 
    it.parenttype = 'Item' AND it.parent = it.name %s WHERE it.disabled = 0 AND it.end_of_life >= CURDATE() %s %s""" \
            % (att_join, att_cond, rol_cond)
    it_dict = frappe.db.sql(query, as_dict=1)
    return it_dict


def get_req_wip_sizes_from_template(bom_temp_name, fg_item, rm_item, table_name, process_sheet_name,
                                    allow_zero_rol=None):
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
                if d.allowed_values != 'No':
                    att_cond += " AND %s.attribute_value = '%s'" % (att_table, d.allowed_values)
                    att_join += " LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent " \
                                "AND %s.parenttype = 'Item' AND %s.attribute = '%s'" % \
                                (att_table, att_table, att_table, att_table, d.attribute)
            else:
                att_cond += convert_wip_rule_to_mysql_statement(d.rule, fg_item, rm_item, process_sheet_name)
                att_join += " LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent AND %s.parenttype = 'Item' " \
                            "AND %s.attribute = '%s'" % (att_table, att_table, att_table, att_table, d.attribute)

        query = """SELECT it.name, it.description FROM `tabItem` it LEFT JOIN `tabItem Reorder` rol ON 
        rol.parenttype = 'Item' AND rol.parent = it.name %s WHERE it.disabled = 0 AND it.end_of_life >= CURDATE() %s %s
        """ % (att_join, att_cond, rol_cond)
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
    it_doc = frappe.get_doc("Item", item_code)
    if it_doc.include_item_in_manufacturing == 1:
        if it_doc.made_to_order == 1:
            if not so_item:
                frappe.throw("{} is Made to Order but No SO is defined".format(frappe.get_desk_link("Item", item_code)))
            else:
                qty_list = frappe.db.sql("""SELECT name, quantity, produced_qty FROM `tabProcess Sheet`
                    WHERE docstatus < 2 AND production_item = '%s' 
                    AND sales_order_item = '%s'""" % (item_code, so_item), as_dict=1)
                prod_qty = 0
                if qty_list:
                    for qty in qty_list:
                        prod_qty += qty.quantity
        else:
            qty_list = frappe.db.sql("""SELECT name, quantity , produced_qty FROM `tabProcess Sheet`
                WHERE docstatus < 2 AND production_item = '%s' """ % item_code, as_dict=1)
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
    frappe.msgprint("Created {} for Row# {}".format(frappe.get_desk_link("Process Sheet", ps_doc.name), so_row.idx))


@frappe.whitelist()
def stop_ps_operation(op_id, psd):
    opd = frappe.get_doc("BOM Operation", op_id)
    allowed = get_process_sheet_permission(psd)
    if allowed == 1:
        jcl = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus=0 
        AND operation_id = '%s'""" % op_id, as_dict=1)
        if jcl:
            for jc in jcl:
                frappe.delete_doc("Process Job Card RIGPL", jc.name, for_reload=True)
                frappe.msgprint(f"Deleted {jc.name}")
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
            jc_list = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus=0 
            AND process_sheet = '%s'""" % ps_name, as_dict=1)
            if jc_list:
                for jc in jc_list:
                    frappe.delete_doc("Process Job Card RIGPL", jc.name, for_reload=True)
        ps_doc.save()
        for d in ps_doc.operations:
            opd = frappe.get_doc("BOM Operation", d.name)
            if d.status == "In Progress" or d.status == "Pending":
                d.status = "Stopped"
        update_process_sheet_quantities(ps_doc)
        for op in ps_doc.operations:
            update_process_sheet_operations(ps_doc.name, op.name)
    else:
        frappe.throw("Don't Have Permission to Stop or Unstop Process Sheet {}".format(ps_name))


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
        for op in ps_doc.operations:
            update_process_sheet_operations(ps_doc.name, op.name)
            if op.status != "Completed" or op.status != "Short Closed" or op.status != "Obsolete":
                if op.completed_qty > 0:
                    op.status = "In Progress"
                else:
                    op.status = "Pending"
                existing_job_card = check_existing_job_card(item_name=ps_doc.production_item, operation=op.operation,
                                                        so_detail=ps_doc.sales_order_item, ps_doc=ps_doc)
                if not existing_job_card:
                    create_job_card(ps_doc, op, auto_create=True)
        ps_doc.save()
        update_process_sheet_quantities(ps_doc)
    else:
        frappe.throw("Don't Have Permission to Un-Stop Process Sheet {}".format(ps_name))


def get_process_sheet_permission(ps_doc):
    user = frappe.session.user
    usr_role_list = frappe.db.sql("""SELECT role FROM `tabHas Role` WHERE parenttype = 'User' 
    AND parent = '%s'""" % user, as_list=1)
    is_sys_mgr = any("System Manager" in sublist for sublist in usr_role_list)
    if is_sys_mgr == 1:
        return 1
    custom_perm_cancel = frappe.db.sql("""SELECT role, parent, cancel FROM `tabCustom DocPerm` 
    WHERE parenttype = 'DocType' AND parent = '%s' AND cancel=1""" % ps_doc.doctype, as_dict=1)
    if custom_perm_cancel:
        for role in custom_perm_cancel:
            cancel_allowed = any(role.role in sublist for sublist in usr_role_list)
            if cancel_allowed == 1:
                return 1
    else:
        std_perm_cancel = frappe.db.sql("""SELECT role, parent, cancel FROM `tabDocPerm` 
        WHERE parenttype = 'DocType' AND parent = '%s' AND cancel=1""" % ps_doc.doctype, as_dict=1)
        for role in std_perm_cancel:
            cancel_allowed = any(role.role in sublist for sublist in usr_role_list)
            if cancel_allowed == 1:
                return 1
    return 0


@frappe.whitelist()
def get_bom_template_from_item_name(doctype, txt, searchfield, start, page_len, filters, as_dict):
    so_detail = filters.get("so_detail")
    it_doc = frappe.get_doc("Item", filters.get("it_name"))
    bt_list = get_bom_template_from_item(it_doc, so_detail)
    if not bt_list:
        frappe.throw("NO BOM Template Found")
    elif len(bt_list) == 1:
        bt_list = "('" + bt_list[0] + "')"
    else:
        bt_list = tuple(bt_list)
    query = """SELECT name, title, remarks FROM `tabBOM Template RIGPL` WHERE name in {}""".format(bt_list)
    return frappe.db.sql(query, as_dict=as_dict)
