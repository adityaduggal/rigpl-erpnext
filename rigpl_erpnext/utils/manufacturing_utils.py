# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import re
import math
import json
from frappe import _
from frappe.utils import flt, nowdate, nowtime, get_link_to_form, get_datetime, time_diff_in_hours, getdate, get_time
from erpnext.stock.stock_balance import update_bin_qty
from rigpl_erpnext.utils.other_utils import round_up


def create_job_card(pro_sheet, row, quantity=0, enable_capacity_planning=False, auto_create=False):
    doc = frappe.new_doc("Process Job Card RIGPL")
    doc.update({
        'process_sheet': pro_sheet.name,
        'operation': row.get("operation"),
        'workstation': row.get("workstation"),
        'posting_date': nowdate(),
        's_warehouse': row.get('source_warehouse'),
        't_warehouse': row.get('target_warehouse'),
        'allow_consumption_of_rm': row.allow_consumption_of_rm,
        'allow_production_of_wip_materials': row.allow_production_of_wip_materials,
        'for_quantity': quantity or (pro_sheet.get('quantity', 0) - pro_sheet.get('produced_qty', 0)),
        'operation_id': row.get("name")
    })

    if auto_create:
        doc.flags.ignore_mandatory = True
        if enable_capacity_planning:
            doc.schedule_time_logs(row)
        get_items_from_process_sheet_for_job_card(doc, "rm_consumed")
        get_items_from_process_sheet_for_job_card(doc, "item_manufactured")
        doc.insert()
        frappe.msgprint(_("Job card {0} created").format(get_link_to_form("Process Job Card RIGPL", doc.name)))

    return doc


def check_existing_job_card(item_name, operation, docstatus=0):
    exist_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus = %s AND operation = 
    '%s' AND production_item = '%s' """ % (docstatus, operation, item_name), as_dict=1)
    return exist_jc


@frappe.whitelist()
def make_jc_from_pro_sheet_row(pro_sheet_name, pro_sheet_row_id):
    ps_doc = frappe.get_doc("Process Sheet", pro_sheet_name)
    for row in ps_doc.operations:
        if row.name == pro_sheet_row_id:
            existing_pending_job_card = check_existing_pending_job_card(pro_sheet_name, pro_sheet_row_id)
            if existing_pending_job_card:
                frappe.throw("Job Card# {} is already pending for Process Sheet {} in Row# {} and Operation {"
                             "}".format(get_link_to_form("Process Job Card RIGPL", existing_pending_job_card[
                    0].name),pro_sheet_name, row.idx, row.operation))
            else:
                create_job_card(ps_doc, row, quantity=(row.planned_qty - row.completed_qty), auto_create=True)
            break


def check_existing_pending_job_card(pro_sheet_name, pro_sheet_row_id):
    exist_pro_sheet = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus=0 AND 
    process_sheet = '%s' AND operation_id = '%s'""" % (pro_sheet_name, pro_sheet_row_id), as_dict=1)
    return exist_pro_sheet


def delete_job_card(pro_sheet_doc, trash_can=1):
    if trash_can == 0:
        ignore_on_trash = True
    else:
        ignore_on_trash = False
    for row in pro_sheet_doc.operations:
        pro_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus < 1 AND operation_id 
        = '%s'""" % row.name, as_dict=1)
        if pro_jc:
            frappe.delete_doc('Process Job Card RIGPL', pro_jc[0].name, for_reload=ignore_on_trash)


def create_submit_ste_from_job_card(jc_doc):
    if jc_doc.no_stock_entry != 1:
        remarks = 'STE for Process Job Card # {}'.format(jc_doc.name)
        item_table = []
        it_dict = {}
        it_dict.setdefault("item_code", jc_doc.production_item)
        it_dict.setdefault("allow_zero_valuation_rate", 1)
        it_dict.setdefault("s_warehouse", jc_doc.s_warehouse)
        it_dict.setdefault("t_warehouse", jc_doc.t_warehouse)
        it_dict.setdefault("qty", jc_doc.total_completed_qty)
        item_table.append(it_dict.copy())
        for d in jc_doc.time_logs:
            if d.rejected_qty > 0 and jc_doc.s_warehouse:
                it_dict = {}
                it_dict.setdefault("item_code", jc_doc.production_item)
                it_dict.setdefault("allow_zero_valuation_rate", 1)
                it_dict.setdefault("qty", d.salvage_qty)
                it_dict.setdefault("s_warehouse", jc_doc.s_warehouse)
                it_dict.setdefault("t_warehouse", "")
                item_table.append(it_dict.copy())
            if d.salvage_qty > 0:
                it_dict = {}
                it_dict.setdefault("item_code", jc_doc.production_item)
                it_dict.setdefault("allow_zero_valuation_rate", 1)
                it_dict.setdefault("qty", d.salvage_qty)
                if jc_doc.s_warehouse:
                    it_dict.setdefault("s_warehouse", jc_doc.s_warehouse)
                it_dict.setdefault("t_warehouse", d.salvage_warehouse)
                item_table.append(it_dict.copy())
        if jc_doc.rm_consumed:
            for row in jc_doc.rm_consumed:
                if row.qty > 0:
                    it_dict = {}
                    it_dict.setdefault("item_code", row.item_code)
                    it_dict.setdefault("allow_zero_valuation_rate", 1)
                    it_dict.setdefault("qty", row.qty)
                    it_dict.setdefault("s_warehouse", row.source_warehouse)
                    it_dict.setdefault("t_warehouse", row.target_warehouse)
                    item_table.append(it_dict.copy())
        if jc_doc.item_manufactured:
            for row in jc_doc.item_manufactured:
                if row.qty > 0:
                    it_dict = {}
                    it_dict.setdefault("item_code", row.item_code)
                    it_dict.setdefault("allow_zero_valuation_rate", 1)
                    it_dict.setdefault("qty", row.qty)
                    it_dict.setdefault("s_warehouse", row.source_warehouse)
                    it_dict.setdefault("t_warehouse", row.target_warehouse)
                    item_table.append(it_dict.copy())
        ste_type = 'Repack'
        ste = frappe.new_doc("Stock Entry")
        ste.flags.ignore_permissions = True
        for i in item_table:
            ste.append("items", i)
        ste.update({
            "posting_date": jc_doc.posting_date,
            "posting_time": jc_doc.posting_time,
            "stock_entry_type": ste_type,
            "set_posting_time": 1,
            "process_job_card": jc_doc.name,
            "remarks": remarks
        })
        ste.save()
        ste.submit()
        frappe.msgprint(_("Stock Entry {} created").format(get_link_to_form("Stock Entry", ste.name)))
    else:
        frappe.msgprint("No Stock Entry Created")


def cancel_delete_ste(jc_doc, trash_can=1):
    if jc_doc.no_stock_entry != 1:
        if trash_can == 0:
            ignore_on_trash = True
        else:
            ignore_on_trash = False

        ste_jc = frappe.db.sql("""SELECT name FROM `tabStock Entry` WHERE process_job_card = '%s'""" %
                               jc_doc.name, as_dict=1)
        if ste_jc:
            ste_doc = frappe.get_doc("Stock Entry", ste_jc[0].name)
            ste_doc.flags.ignore_permissions = True
            if ste_doc.docstatus == 1:
                ste_doc.cancel()
            frappe.delete_doc('Stock Entry', ste_jc[0].name, for_reload=ignore_on_trash)
        sle_dict = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` WHERE voucher_type = 'Stock Entry' AND 
        voucher_no = '%s'""" % ste_jc[0].name, as_dict=1)
        for sle in sle_dict:
            frappe.delete_doc('Stock Ledger Entry', sle.name, for_reload=ignore_on_trash)
    else:
        frappe.msgprint("No Stock Entry Cancelled")


def get_items_from_process_sheet_for_job_card(document, table_name):
    document.set(table_name, [])
    pro_sheet = frappe.get_doc("Process Sheet", document.process_sheet)
    for d in pro_sheet.operations:
        if d.name == document.operation_id:
            document.operation = d.operation
    for d in frappe.get_all("Process Sheet Items", fields=["*"], filters={'parenttype': 'Process Sheet',
            'parent': document.process_sheet, 'parentfield': table_name}, order_by='idx'):
        child = document.append(table_name, {
            "idx": d.idx,
            "item_code": d.item_code,
            "description": d.description,
            "source_warehouse": d.source_warehouse,
            "target_warehouse": d.target_warehouse,
            "uom": d.uom
        })


def check_qty_job_card(row, calculated_qty, qty, uom, bypass=0):
    uom_doc = frappe.get_doc('UOM', uom)
    error_title = "Error for Raw Material Quantity Entered"
    warning_title = "Warning for Raw Material Quantity Entered"
    if uom_doc.variance_allowed > 0:
        variance = uom_doc.variance_allowed / 100
        upper_limit = (1+variance)*flt(calculated_qty)
        lower_limit = (1-variance)*flt(calculated_qty)
        if flt(qty) > upper_limit or flt(qty) < lower_limit:
            message = "Entered Quantity {} in Row# {} for {} is Not in Range and must be between {} and {}".\
                format(row.qty, row.idx, row.parent, lower_limit, upper_limit)
            if bypass == 0:
                frappe.throw(message, title=error_title)
            else:
                frappe.msgprint(message, title=warning_title)
    else:
        calculated_qty = convert_qty_per_uom(calculated_qty, row.item_code)
        if flt(qty) != calculated_qty:
            message = "Entered Quantity = {} is Not Equal to the Calculated Qty = {} for RM Size = {} in Row# {}".\
                format(row.qty, row.calculated_qty, row.item_code, row.idx)
            if bypass == 0:
                frappe.throw(message, title=error_title)
            else:
                frappe.msgprint(message, title=warning_title)


def calculated_value_from_formula(rm_item_dict, fg_item_name, fg_qty=0, so_detail=None, process_sheet_name=None):
    qty_dict = frappe._dict({})
    qty_list = []
    bom_temp_name = get_bom_template_from_item(frappe.get_doc("Item", fg_item_name), so_detail=so_detail)
    bom_temp_doc = frappe.get_doc("BOM Template RIGPL", bom_temp_name)
    formula = replace_java_chars(bom_temp_doc.formula)
    fg_item_doc = frappe.get_doc('Item', fg_item_name)
    if not fg_item_doc.variant_of:
        ps_doc = frappe.get_doc("Process Sheet", process_sheet_name)
        special_item_attr_doc = get_special_item_attribute_doc(fg_item_name, ps_doc.sales_order_item, docstatus=1)
        fg_att_dict = get_special_item_attributes(fg_item_name, special_item_attr_doc[0].name)
    else:
        fg_att_dict = get_attributes(fg_item_name)
    for d in rm_item_dict:
        rm_att_dict = get_attributes(d.name or d.item_code)
        qty = calculate_formula(rm_att_dict, fg_att_dict, formula, fg_qty)
        qty = convert_qty_per_uom(qty, d.item)
        qty_dict["rm_item_code"] = d.name or d.item_code
        qty_dict["fg_item_code"] = fg_item_name
        qty_dict["qty"] = qty
        qty_list.append(qty_dict.copy())
    return qty_list


def validate_qty_decimal(document, table_name):
    for row in document.get(table_name):
        row.qty = convert_qty_per_uom(row.qty, row.item_code)


def convert_qty_per_uom(qty, item_name):
    uom_name = frappe.get_value("Item", item_name, "stock_uom")
    uom_whole_number = frappe.get_value("UOM", uom_name, "must_be_whole_number")
    if uom_whole_number == 1:
        qty = int(flt(qty))
    else:
        qty = flt(qty)
    return qty


def find_item_quantities(item_dict):
    availability = []
    for d in item_dict:
        one_item_availability = frappe.db.sql("""SELECT name, warehouse, item_code, stock_uom, valuation_rate, 
        actual_qty FROM `tabBin` WHERE docstatus = 0 AND item_code = '%s'""" % (d.name or d.item_code), as_dict=1)
        if one_item_availability:
            for available in one_item_availability:
                availability.append(available)
    return availability


def update_item_table(item_dict, table_name, document):
    table_dict = {}
    for d in item_dict:
        table_dict["item_code"] = d.name
        table_dict["description"] = d.description
        document.append(table_name, table_dict.copy())


def disallow_templates(doc, item_doc):
    if item_doc.has_variants == 1:
        frappe.throw('Template {} is not allowed in BOM {}'.format(item_doc.name, doc.name))


def get_req_wip_sizes_from_template(bom_temp_name, fg_item, rm_item, table_name, allow_zero_rol=None):
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
                att_cond += convert_wip_rule_to_mysql_statement(d.rule, fg_item, rm_item)
                att_join += " LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent AND %s.parenttype = 'Item' " \
                            "AND %s.attribute = '%s'" % (att_table, att_table, att_table, att_table, d.attribute)

        query = """SELECT it.name, it.description FROM `tabItem` it LEFT JOIN `tabItem Reorder` rol ON 
        rol.parenttype = 'Item' AND rol.parent = it.name %s WHERE it.disabled = 0 AND it.end_of_life >= CURDATE() %s %s
        """ % (att_join, att_cond, rol_cond)
        it_dict = frappe.db.sql(query, as_dict=1)
    else:
        it_dict = {}
    return it_dict


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


def convert_wip_rule_to_mysql_statement(rule, fg_item, rm_item, process_sheet_name=None):
    new_rule = replace_java_to_mysql(rule)
    fg_item_doc = frappe.get_doc("Item", fg_item)
    if not fg_item_doc.variant_of:
        ps_doc = frappe.get_doc("Process Sheet", process_sheet_name)
        special_item_attr_doc = get_special_item_attribute_doc(it_name, ps_doc.sales_order_item, docstatus=1)
        fg_att_dict = get_special_item_attributes(it_name, special_item_attr_doc[0].name)
    else:
        fg_att_dict = get_attributes(fg_item)
    rm_att_dict = get_attributes(rm_item)
    res = re.findall(r'\w+', rule)
    for word in res:
        if word[:3] == 'fg_':
            for d in fg_att_dict:
                if d.attribute == word[3:]:
                    new_rule = new_rule.replace(word, d.attribute_value)
        elif word[:3] == 'rm_':
            for d in rm_att_dict:
                if d.attribute == word[3:]:
                    new_rule = new_rule.replace(word, d.attribute_value)
        if word[:4] == 'wip_':
            new_rule = new_rule.replace(word, word[4:] + '.attribute_value')
    new_rule = ' AND ' + new_rule
    return new_rule


def convert_rule_to_mysql_statement(rule, it_dict, process_sheet_name=None):
    new_rule = replace_java_to_mysql(rule)
    it_name = it_dict.get("known_item")
    it_doc = frappe.get_doc("Item", it_name)
    if not it_doc.variant_of:
        ps_doc = frappe.get_doc("Process Sheet", process_sheet_name)
        special_item_attr_doc = get_special_item_attribute_doc(it_name, ps_doc.sales_order_item, docstatus=1)
        known_it_att_dict = get_special_item_attributes(it_name, special_item_attr_doc[0].name)
    else:
        known_it_att_dict = get_attributes(it_name)
    known_type = it_dict.get(it_name)
    unknown_type = it_dict.get("unknown_type")
    res = re.findall(r'\w+', rule)
    for word in res:
        if word[:len(known_type) + 1] == known_type + '_':
            for d in known_it_att_dict:
                if d.attribute == word[len(known_type)+1:]:
                    new_rule = new_rule.replace(word, d.attribute_value)

        if word[:len(unknown_type) + 1] == unknown_type + '_':
            new_rule = new_rule.replace(word, word[len(unknown_type) + 1:] + '.attribute_value')
    new_rule = ' AND ' + new_rule
    return new_rule


def get_special_item_attributes(it_name, special_item_attribute):
    attribute_dict = frappe.db.sql("""SELECT idx, name, attribute, attribute_value, numeric_values 
        FROM `tabItem Variant Attribute` WHERE parent = '%s' AND parenttype = 'Made to Order Item Attributes' ORDER BY 
        idx""" % special_item_attribute, as_dict=1)
    return attribute_dict


def get_attributes(item_name, so_detail=None):
    attribute_dict = frappe.db.sql("""SELECT idx, name, attribute, attribute_value, numeric_values 
        FROM `tabItem Variant Attribute` WHERE parent = '%s' AND parenttype = 'Item' ORDER BY idx""" % item_name,
                                   as_dict=1)
    return attribute_dict


def get_bom_template_from_item(item_doc, so_detail=None):
    bom_template = {}
    if item_doc.variant_of:
        it_att_dict = get_attributes(item_doc.name)
        bom_template = get_bom_temp_from_it_att(item_doc, it_att_dict)
        if not bom_template:
            frappe.throw("No BOM Template found for Item: {}".format(item_doc.name))
    else:
        # Find Item Attributes in Special Item Table or Create a New Special Item Table and ask user to fill it.
        if so_detail:
            special_attributes = get_special_item_attribute_doc(item_doc.name, so_detail, docstatus=1)
            if not special_attributes:
                sp_att_draft = get_special_item_attribute_doc(item_doc.name, so_detail, docstatus=0)
                if sp_att_draft:
                    frappe.throw("Special Item Attributes not Submitted please fill and Submit {}".
                                 format(get_link_to_form("Made to Order Item Attributes", sp_att_draft[0].name)))
                else:
                    create_new_special_attributes(item_doc.name, so_detail)
                    frappe.msgprint("Fill the Special Item Attributes and Try Again")
            else:
                # Get Special Attributes from the Table and then find bom template
                it_att_dict = get_special_item_attributes(item_doc.name, special_attributes[0].name)
                bom_template = get_bom_temp_from_it_att(item_doc, it_att_dict)
        else:
            frappe.throw("{} item seems like a Special Item hence Sales Order is Mandatory for the same.".format(
                item_doc.name))
    return bom_template


def create_new_special_attributes(it_name, so_detail):
    special = frappe.new_doc("Made to Order Item Attributes")
    special.item_code = it_name
    special.sales_order_item = so_detail
    special.sales_order = frappe.get_value("Sales Order Item", so_detail, "parent")
    special.description = frappe.get_value("Sales Order Item", so_detail, "description")
    special.insert()
    frappe.db.commit()
    frappe.msgprint(_("Special Item Attributes {0} created").format(get_link_to_form("Made to Order Item Attributes",
                                                                                    special.name)))


def get_special_item_attribute_doc(it_name, so_detail, docstatus=1):
    return frappe.db.sql("""SELECT name FROM `tabMade to Order Item Attributes` WHERE docstatus = %s AND item_code = 
    '%s' AND sales_order_item = '%s'""" % (docstatus, it_name, so_detail), as_dict=1)


def get_bom_temp_from_it_att(item_doc, att_dict):
    found = 0
    all_bt = frappe.get_all("BOM Template RIGPL")
    for bt in all_bt:
        if found == 1:
            break
        bt_doc = frappe.get_doc("BOM Template RIGPL", bt.name)
        total_score = len(bt_doc.fg_restrictions)
        match_score = 0
        exit_bt = 0
        for bt_rule in bt_doc.fg_restrictions:
            if exit_bt == 0:
                for att in att_dict:
                    if bt_rule.is_numeric == 1 and att.numeric_values == 1:
                        formula = replace_java_chars(bt_rule.rule)
                        formula_values = get_formula_values(att_dict, formula, "fg")
                        dont_calculate_formula = 0
                        for key in formula_values.keys():
                            if key not in formula:
                                dont_calculate_formula = 1
                                break
                        if dont_calculate_formula == 0:
                            calculated_value = calculate_formula_values(formula, formula_values)
                        else:
                            break
                        if calculated_value == 1:
                            match_score += 1
                            break
                    else:
                        if att.attribute == bt_rule.attribute:
                            if att.attribute_value == bt_rule.allowed_values:
                                match_score += 1
                                break
                            else:
                                exit_bt = 1
                                break
        if match_score == total_score:
            found = 1
            return bt.name


def update_fields_from_template(doc, bt_doc):
    doc.rm_cost_as_per = bt_doc.rm_cost_as_per
    doc.with_operations = bt_doc.with_operations
    doc.transfer_material_against = bt_doc.transfer_material_against
    doc.routing = bt_doc.routing


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


def replace_java_to_mysql(string):
    replace_dict = {
        'false': 'False',
        'true': 'True',
        '&&': ' and ',
        '||': ' or ',
        '&gt;': '>',
        '&lt;': '<',
        '==': '=',
        '!=': '!='
    }

    for k, v in replace_dict.items():
        string = string.replace(k, v)
    return string


def replace_java_chars(string):
    replace_dict = {
        'false': 'False',
        'true': 'True',
        '&&': ' and ',
        '||': ' or ',
        '&gt;': '>',
        '&lt;': '<'
    }

    for k, v in replace_dict.items():
        string = string.replace(k, v)
    return string


def calculate_operation_time(doc, rt_dict, fg_it_doc, rm_it_dict):
    if fg_it_doc.variant_of:
        fg_attributes = get_attributes(fg_it_doc.name)
    for d in doc.operations:
        formula_values = frappe._dict({})
        for op in rt_dict:
            if op.time_based_on_formula == 1 and d.operation == op.operation:
                op_time_formula_edited = replace_java_chars(op.operation_time_formula)
                formula_values = formula_values.update(get_formula_values(fg_attributes, op_time_formula_edited, "fg"))
                for rm in rm_it_dict:
                    rm_attributes = get_attributes(rm.name)
                    formula_values = formula_values.update(get_formula_values(rm_attributes, op_time_formula_edited,
                                                                              "rm"))
                operation_time = calculate_formula_values(op_time_formula_edited, formula_values)
                d.time_in_mins = int(operation_time * doc.quantity / d.batch_size)
            elif op.time_based_on_formula != 1:
                d.time_in_mins = int(op.time_in_mins * doc.quantity / d.batch_size)


def calculate_batch_size(doc, rt_dict, fg_it_doc, rm_it_dict):
    fg_attributes = get_attributes(fg_it_doc.name)
    for d in doc.operations:
        formula_values = frappe._dict({})
        for op in rt_dict:
            if op.batch_size_based_on_formula == 1 and d.operation == op.operation:
                batch_edited_formula = replace_java_chars(op.batch_size_formula)
                formula_values = formula_values.update(get_formula_values(fg_attributes, batch_edited_formula, "fg"))
                for rm in rm_it_dict:
                    rm_attributes = get_attributes(rm.name)
                    formula_values = formula_values.update(get_formula_values(rm_attributes, batch_edited_formula,
                                                                              "rm"))
                batch_size = calculate_formula_values(batch_edited_formula, formula_values)
                batch_size = convert_qty_per_uom(batch_size, fg_it_doc.name)
                d.batch_size = batch_size


def get_formula_values(att_dict, formula, type_of_dict):
    values = {}
    for att in att_dict:
        if (type_of_dict + '_' + att.attribute) in formula:
            values[(type_of_dict + '_' + att.attribute)] = flt(att.attribute_value)
    return values


def calculate_formula(rm_att_dict, fg_att_dict, formula, fg_quantity):
    formula_values = frappe._dict({})
    formula_values['qty'] = fg_quantity
    formula_values = formula_values.update(get_formula_values(rm_att_dict, formula, "rm"))
    formula_values = formula_values.update(get_formula_values(fg_att_dict, formula, "fg"))
    calc_qty = calculate_formula_values(formula, formula_values)
    return calc_qty


def calculate_formula_values(formula, formula_values_dict):
    original_keys = formula_values_dict.keys()
    try:
        calc_value = eval(formula, formula_values_dict, formula_values_dict)
    except Exception as e:
        frappe.throw("\n\n".join(map(str, [formula, {k: v for k, v in formula_values_dict.items() if k in
                                                     original_keys}, e])))
    return calc_value


def calculate_operation_cost(document):
    for d in document.operations:
        d.hour_rate = get_workstation_hr_cost(d.workstation)
        d.operating_cost = int(d.hour_rate * d.time_in_mins / 60)


def get_workstation_hr_cost(workstation):
    wk_doc = frappe.get_doc("Workstation", workstation)
    return wk_doc.hour_rate


def update_produced_qty(jc_doc, status="Submit"):
    # This function would update the produced qty in Process Sheet from Process Job Card and Close if needed
    pro_sheet = frappe.get_doc("Process Sheet", jc_doc.process_sheet)
    min_qty, max_qty = get_min_max_ps_qty(pro_sheet.quantity)
    bal_qty = pro_sheet.produced_qty - pro_sheet.produced_qty
    if min_qty - pro_sheet.produced_qty < 0:
        min_bal_qty = 0
    else:
        min_bal_qty = min_qty - pro_sheet.produced_qty
    max_bal_qty = max_qty - pro_sheet.produced_qty
    pro_sheet = frappe.get_doc("Process Sheet", jc_doc.process_sheet)
    if min_bal_qty < jc_doc.total_completed_qty < max_bal_qty:
        frappe.msgprint("Balance Ordered Qty = {} but Manufactured Qty = {} for Job Card# {} for Item Code: {}. Check "
                        "Short Close Operation to Short Close the Operation".format(bal_qty,
                                jc_doc.total_completed_qty, jc_doc.name, jc_doc.production_item))

    for ps_r in pro_sheet.operations:
        if ps_r.name == jc_doc.operation_id:
            if status == "Submit":
                tc_comp_qty = jc_doc.total_completed_qty
                frappe.db.set_value("BOM Operation", ps_r.name, "completed_qty", tc_comp_qty if tc_comp_qty > 0 else 0)
                if tc_comp_qty >= ps_r.planned_qty or jc_doc.short_close_operation == 1:
                    frappe.db.set_value("BOM Operation", ps_r.name, "status", "Completed")
                else:
                    frappe.db.set_value("BOM Operation", ps_r.name, "status", "In Progress")
            else:
                tc_comp_qty = jc_doc.total_completed_qty
                frappe.db.set_value("BOM Operation", ps_r.name, "completed_qty", tc_comp_qty if tc_comp_qty > 0 else 0)
                if tc_comp_qty < ps_r.planned_qty or jc_doc.short_close_operation == 1:
                    frappe.db.set_value("BOM Operation", row.name, "status", "In Progress")

            if ps_r.idx == 1 and status == "Submit":
                tc_comp_qty = pro_sheet.produced_qty + jc_doc.total_completed_qty
                frappe.db.set_value("Process Sheet", pro_sheet.name, "produced_qty", tc_comp_qty if tc_comp_qty > 0
                else 0)
                frappe.db.set_value("Process Sheet", pro_sheet.name, "status", "In Progress")
            elif ps_r.idx == 1 and status == 'Cancel':
                tc_comp_qty = pro_sheet.produced_qty - jc_doc.total_completed_qty
                frappe.db.set_value("Process Sheet", pro_sheet.name, "produced_qty", tc_comp_qty if tc_comp_qty > 0
                else 0)


def close_process_sheet(ps_doc):
    pass


def update_qty_for_prod(item_code, warehouse, table_name):
    update_bin_qty(item_code, warehouse, {"reserved_qty_for_production": get_qty_for_prod(item_code, warehouse,
                                                                                          table_name)})


def get_qty_for_prod(item_code, warehouse, table_name):
    qty_res_for_prod = frappe.db.sql("""SELECT SUM(psi.calculated_qty - psi.qty) FROM `tabProcess Sheet Items` psi, 
    `tabProcess Sheet` ps 
    WHERE ps.name = psi.parent AND psi.parenttype = 'Process Sheet' AND ps.docstatus = 1 AND psi.parentfield = '%s' AND
    ps.status NOT IN ("Stopped", "Completed") AND psi.donot_consider_rm_for_production != 1 AND psi.item_code = '%s' 
    AND psi.source_warehouse = '%s'""" % (table_name, item_code, warehouse))

    return flt(qty_res_for_prod[0][0]) if qty_res_for_prod else 0


def update_planned_qty(item_code, warehouse):
    update_bin_qty(item_code, warehouse, {
        "planned_qty": get_planned_qty_process(item_code, warehouse)
    })


def get_planned_qty_process(item_code, warehouse):
    planned_qty = frappe.db.sql(""" SELECT IF(SUM(quantity - produced_qty) > 0, SUM(quantity - produced_qty), 0) FROM 
    `tabProcess Sheet` WHERE production_item = %s and fg_warehouse = %s and status not in ("Stopped", "Completed") 
    AND docstatus=1 AND quantity > produced_qty""", (item_code, warehouse))

    return flt(planned_qty[0][0]) if planned_qty else 0


def update_psheet_operation_status(document, status=None, for_value=None):
    if not status:
        status = ""
    if for_value == 'all':
        for d in document.operations:
            d.status = status
            frappe.db.set_value("BOM Operation", d.name, "status", status)


def check_warehouse_in_child_tables(document, table_name=None, type_of_table=None):
    for row in document.get(table_name):
        if type_of_table == 'Consume':
            row.target_warehouse = ""
            if not row.source_warehouse:
                frappe.throw('Source Warehouse is Mandatory for Row# {}'.format(row.idx))
        elif type_of_table == 'Production':
            row.source_warehouse = ""
            if not row.target_warehouse:
                frappe.throw('Target Warehouse is Mandatory for Row# {}'.format(row.idx))


def update_warehouse_from_bt(pro_sheet_doc):
    bt_doc = frappe.get_doc("BOM Template RIGPL", pro_sheet_doc.bom_template)
    for row in pro_sheet_doc.operations:
        for bt_row in bt_doc.operations:
            if row.operation == bt_row.operation and row.idx == bt_row.idx:
                if not row.source_warehouse:
                    row.source_warehouse = bt_row.source_warehouse
                if not row.target_warehouse:
                    row.target_warehouse = bt_row.target_warehouse


def validate_job_card_time_logs(document):
    total_mins = 0
    total_comp_qty = 0
    total_rej_qty = 0
    posting_date = getdate('1900-01-01')
    posting_time = get_time('00:00:00')
    now_time = get_datetime(nowtime())
    if document.get('time_logs'):
        tl_tbl = document.get('time_logs')
        for i in range(0, len(tl_tbl)):
            if i > 0:
                if get_datetime(tl_tbl[i].from_time) < get_datetime(tl_tbl[i-1].to_time):
                    frappe.throw("Row# {}: From Time Cannot be Less than To Time in Row# {}".format(tl_tbl[i].idx,
                                                                                                    tl_tbl[i-1].idx))
            if get_datetime(tl_tbl[i].to_time) > now_time:
                frappe.throw("To Time is in Future for Row# {}".format(tl_tbl[i].idx))
            if tl_tbl[i].completed_qty == 0:
                frappe.throw("Zero Quantity Not Allowed for Row# {}".format(tl_tbl[i].idx))
            if get_datetime(tl_tbl[i].from_time) > get_datetime(tl_tbl[i].to_time):
                frappe.throw(_("Row {0}: From time must be less than to time").format(tl_tbl[i].idx))
            data = get_overlap_for(document, tl_tbl[i])
            if data:
                frappe.throw(_("Row {0}: From Time and To Time of {1} is overlapping with {2}").format(tl_tbl[i],
                        document.name, data.name))
            if tl_tbl[i].from_time and tl_tbl[i].to_time:
                if getdate(tl_tbl[i].to_time) > posting_date:
                    posting_date = getdate(tl_tbl[i].to_time)
                    posting_time = get_time(tl_tbl[i].to_time)
                if int(time_diff_in_hours(tl_tbl[i].to_time, tl_tbl[i].from_time) * 60) != tl_tbl[i].time_in_mins:
                    tl_tbl[i].time_in_mins = int(time_diff_in_hours(tl_tbl[i].to_time, tl_tbl[i].from_time) * 60)
                total_mins += int(tl_tbl[i].time_in_mins)
                if document.total_time_in_mins != int(total_mins):
                    document.total_time_in_mins = int(total_mins)
            if tl_tbl[i].completed_qty > 0:
                total_comp_qty += tl_tbl[i].completed_qty
            if flt(tl_tbl[i].rejected_qty) > 0:
                total_rej_qty += tl_tbl[i].rejected_qty
            if flt(tl_tbl[i].salvage_qty) > 0:
                total_rej_qty += tl_tbl[i].salvage_qty
                if not tl_tbl[i].salvage_warehouse:
                    frappe.throw("Salvage Warehouse is Mandatory if Salvage Qty > 0 for Row # {}".format(tl_tbl[i].idx))
                else:
                    wh_doc = frappe.get_doc("Warehouse", tl_tbl[i].salvage_warehouse)
                    if wh_doc.warehouse_type != "Rejected":
                        roles_list = frappe.get_roles(frappe.session.user)
                        if 'System Manager' not in roles_list:
                            frappe.throw("Only System Manager allowed to Send Salvage Material to Non-Rejected "
                                         "Warehouse in Row# {}".format(tl_tbl[i].idx))

            if document.total_rejected_qty != total_rej_qty:
                document.total_rejected_qty = total_rej_qty
            if document.total_completed_qty != total_comp_qty:
                document.total_completed_qty = total_comp_qty
            if document.posting_date != posting_date and document.manual_posting_date_and_time != 1:
                document.posting_date = posting_date
            if document.posting_time != posting_time and document.manual_posting_date_and_time != 1:
                document.posting_time = str(posting_time)
            if document.manual_posting_date_and_time == 1:
                if get_datetime(document.posting_date + " " + document.posting_time) > get_datetime(nowtime()):
                    frappe.throw("Future Posting Date is Not Allowed for {}".format(document.name))
    else:
        frappe.throw("Time Logs Mandatory for Process Job Card {}".format(document.name))


def get_overlap_for(document, row, check_next_available_slot=False):
    production_capacity = 1

    if document.workstation:
        production_capacity = frappe.get_cached_value("Workstation", document.workstation, 'production_capacity') or 1
        validate_overlap_for = " and jc.workstation = %(workstation)s "
    else:
        validate_overlap_for = ""

    extra_cond = ''
    if check_next_available_slot:
        extra_cond = " or (%(from_time)s <= jctl.from_time and %(to_time)s <= jctl.to_time)"

    existing = frappe.db.sql("""SELECT jc.name AS name, jctl.to_time FROM `tabJob Card Time Log` jctl, 
    `tabProcess Job Card RIGPL` jc 
    WHERE jctl.parent = jc.name AND jctl.parenttype = 'Process Job Card RIGPL' AND ((%(from_time)s > 
    jctl.from_time and %(from_time)s < jctl.to_time) OR (%(to_time)s > jctl.from_time and %(to_time)s < 
    jctl.to_time) OR (%(from_time)s <= jctl.from_time AND %(to_time)s >= jctl.to_time) {}) AND jctl.name != %(name)s 
    AND jc.name != %(parent)s and jc.docstatus < 2 {} 
    ORDER BY jctl.to_time desc limit 1""".format(extra_cond, validate_overlap_for), {"from_time": row.from_time,
        "to_time": row.to_time, "name": row.name or "No Name", "parent": row.parent or "No Name",
        "employee": document.employee, "workstation": document.workstation}, as_dict=True)
    if existing and production_capacity > len(existing):
        return

    return existing[0] if existing else None


def check_produced_qty_jc(doc):
    if not doc.s_warehouse:
        min_qty, max_qty = get_min_max_ps_qty(doc.for_quantity)
        if (min_qty > doc.total_completed_qty and doc.short_close_operation == 1) or doc.total_completed_qty > max_qty:
            frappe.throw("For Job Card# {} allowed quantities to Manufacture is between {} and {}. So if you "
                         "are producing lower quantities then you cannot short close the Operation".format(doc.name,
                                                                                                    min_qty, max_qty))
    else:
        if doc.qty_available < (doc.total_completed_qty + doc.total_rejected_qty):
            frappe.throw("For Job Card# {} Qty Available for Item Code: {} in Warehouse: {} is {} but you are trying "
                         "to process {} quantities. Please correct this error.".\
                         format(doc.name, doc.production_item, doc.s_warehouse, doc.qty_available,
                                (doc.total_completed_qty + doc.total_rejected_qty)))


def get_min_max_ps_qty(qty):
    manuf_settings = frappe.get_single("Manufacturing Settings")
    over_prod = manuf_settings.overproduction_percentage_for_work_order
    max_qty = math.ceil(qty * (1 + over_prod/100))
    min_qty = math.floor(qty * (1 - over_prod/100))
    return min_qty, max_qty


def update_pro_sheet_rm_from_jc(jc_doc, status="Submit"):
    pro_sheet_doc = frappe.get_doc("Process Sheet", jc_doc.process_sheet)
    for rm in jc_doc.rm_consumed:
        for row in pro_sheet_doc.rm_consumed:
            if row.item_code == rm.item_code:
                if status == "Submit":
                    tc_qty = int(row.qty + rm.qty)
                else:
                    tc_qty = int(row.qty - rm.qty)
                if row.calculated_qty > tc_qty:
                    frappe.db.set_value("Process Sheet Items", row.name, "qty", tc_qty if tc_qty > 0 else 0)
                else:
                    frappe.db.set_value("Process Sheet Items", row.name, "qty", row.calculated_qty)
        update_qty_for_prod(row.item_code, row.source_warehouse, table_name="rm_consumed")
