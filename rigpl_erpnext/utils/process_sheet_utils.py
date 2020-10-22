# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt
from rigpl_erpnext.utils.other_utils import round_up
from .manufacturing_utils import convert_rule_to_mysql_statement, convert_wip_rule_to_mysql_statement, \
    get_bom_template_from_item


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


def get_qty_to_manufacture(it_doc):
    qty = 100
    rol = frappe.db.sql("""SELECT warehouse_reorder_level, warehouse_reorder_qty FROM `tabItem Reorder` 
    WHERE parent = '%s' AND parenttype = '%s' AND parentfield = 'reorder_levels'""" % (it_doc.name, it_doc.doctype),
                        as_dict=1)
    if not rol:
        rol = 0
    else:
        rol = flt(rol[0].warehouse_reorder_level)
    bin_dict = frappe.db.sql("""SELECT bn.warehouse, bn.item_code, bn.reserved_qty, bn.actual_qty, bn.ordered_qty,
        bn.indented_qty, bn.planned_qty, bn.reserved_qty_for_production, bn.reserved_qty_for_sub_contract, 
        wh.warehouse_type, wh.disabled FROM `tabBin` bn, `tabWarehouse` wh WHERE bn.warehouse = wh.name AND 
        bn.item_code = '%s'"""
                             % it_doc.name, as_dict=1)
    fg = 0
    wipq = 0
    con = 0
    rm = 0
    dead = 0
    rej = 0
    po = 0
    so = 0
    ind = 0
    plan = 0
    prd = 0
    lead = flt(it_doc.lead_time_days)
    if bin_dict:
        for d in bin_dict:
            so += flt(d.reserved_qty)
            po += flt(d.ordered_qty)
            ind += flt(d.indented_qty)
            plan += flt(d.planned_qty)
            prd += flt(d.reserved_qty_for_production)

            if d.warehouse_type == 'Finished Stock':
                fg += flt(d.actual_qty)
            elif d.warehouse_type == 'Work In Progress':
                wipq += flt(d.actual_qty)
            elif d.warehouse_type == 'Consumable':
                con += flt(d.actual_qty)
            elif d.warehouse_type == 'Raw Material':
                rm += flt(d.actual_qty)
            elif d.warehouse_type == 'Dead Stock':
                dead += flt(d.actual_qty)
            elif d.warehouse_type == 'Recoverable Stock':
                rej += flt(d.actual_qty)
            elif d.warehouse_type == 'Subcontracting':
                po += flt(d.actual_qty)

            if lead == 0:
                lead = 30
        reqd_qty = (rol * lead / (30 * 2)) + so + prd - fg - wipq
        if reqd_qty < 0:
            reqd_qty = 0
        elif 10 < reqd_qty < 50:
            reqd_qty = round_up(reqd_qty, 5)
        elif 50 < reqd_qty < 500:
            reqd_qty = round_up(reqd_qty, 10)
        elif 500 < reqd_qty < 1000:
            reqd_qty = round_up(reqd_qty, 50)
        elif reqd_qty > 1000:
            reqd_qty = round_up(reqd_qty, 100)

        qty = reqd_qty
    return qty


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
