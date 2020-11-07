# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from datetime import date
from .manufacturing_utils import *
from .job_card_utils import check_existing_job_card, create_job_card


def update_process_sheet_quantities(ps_doc):
    update_planned_qty(item_code=ps_doc.production_item, warehouse=ps_doc.fg_warehouse)
    for rm in ps_doc.rm_consumed:
        update_qty_for_prod(item_code=rm.item_code, warehouse=rm.source_warehouse, table_name="rm_consumed")


def make_jc_for_process_sheet(ps_doc):
    for row in ps_doc.operations:
        if row.status == 'Pending':
            existing_job_card = check_existing_job_card(item_name=ps_doc.production_item, operation=row.operation,
                                                        so_detail=ps_doc.sales_order_item)
            if not existing_job_card:
                create_job_card(ps_doc, row, auto_create=True)
                frappe.db.set_value("BOM Operation", row.name, "status", "In Progress")


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
    ps_doc.insert()
    frappe.msgprint("Created {} for Row# {}".format(frappe.get_desk_link("Process Sheet", ps_doc.name), so_row.idx))


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
                    frappe.delete_doc("Process Job Card RIGPL", jc.name, for_reload=False)
        ps_doc.save()
        update_process_sheet_quantities(ps_doc)
    else:
        frappe.throw("Don't Have Permission to Stop Process Sheet {}".format(ps_name))


@frappe.whitelist()
def unstop_process_sheet(ps_name):
    ps_doc = frappe.get_doc("Process Sheet", ps_name)
    allowed = get_process_sheet_permission(ps_doc)
    if allowed == 1:
        ps_doc.status = "In Progress"
        for op in ps_doc.operations:
            existing_job_card = check_existing_job_card(item_name=ps_doc.production_item, operation=op.operation,
                                                        so_detail=ps_doc.sales_order_item)
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
