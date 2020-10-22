# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import re
import math
from frappe import _
from frappe.utils import flt
from erpnext.stock.stock_balance import update_bin_qty


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
        actual_qty FROM `tabBin` WHERE docstatus = 0 AND item_code = '%s'""" % (d.get("name") or d.get("item_code")),
                                              as_dict=1)
        if one_item_availability:
            for available in one_item_availability:
                availability.append(available)
    return availability


def convert_wip_rule_to_mysql_statement(rule, fg_item, rm_item, process_sheet_name=None):
    new_rule = replace_java_to_mysql(rule)
    fg_item_doc = frappe.get_doc("Item", fg_item)
    if not fg_item_doc.variant_of:
        ps_doc = frappe.get_doc("Process Sheet", process_sheet_name)
        special_item_attr_doc = get_special_item_attribute_doc(item_name=fg_item, so_detail=ps_doc.sales_order_item,
                                                               docstatus=1)
        fg_att_dict = get_special_item_attributes(fg_item, special_item_attr_doc[0].name)
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
        special_item_attr_doc = get_special_item_attribute_doc(item_name=it_name, so_detail=ps_doc.sales_order_item,
                                                               docstatus=1)
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


def get_bom_template_from_item(item_doc, so_detail=None, no_error=0):
    bom_template = {}
    if item_doc.variant_of:
        it_att_dict = get_attributes(item_doc.name)
        bom_template = get_bom_temp_from_it_att(item_doc, it_att_dict)
        if not bom_template:
            if no_error == 0:
                frappe.throw("No BOM Template found for Item: {}".format(item_doc.name))
            else:
                return []
    else:
        # Find Item Attributes in Special Item Table or Create a New Special Item Table and ask user to fill it.
        if so_detail:
            special_attributes = get_special_item_attribute_doc(item_name=item_doc.name, so_detail=so_detail,
                                                                docstatus=1)
            if not special_attributes:
                sp_att_draft = get_special_item_attribute_doc(item_name=item_doc.name, so_detail=so_detail, docstatus=0)
                if sp_att_draft:
                    frappe.throw("Special Item Attributes not Submitted please fill and Submit {}".
                                 format(frappe.get_desk_link("Made to Order Item Attributes", sp_att_draft[0].name)))
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
    frappe.msgprint(_("{} created").format(frappe.get_desk_link("Made to Order Item Attributes", special.name)))


def get_special_item_attribute_doc(item_name, so_detail, docstatus=1):
    return frappe.db.sql("""SELECT name FROM `tabMade to Order Item Attributes` WHERE docstatus = %s AND item_code = 
    '%s' AND sales_order_item = '%s'""" % (docstatus, item_name, so_detail), as_dict=1)


def get_bom_temp_from_it_att(item_doc, att_dict):
    bt_list = []
    all_bt = frappe.get_all("BOM Template RIGPL")
    for bt in all_bt:
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
            bt_list.append(bt.name)
    return bt_list


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
        "false": "False",
        "true": "True",
        "&&": " and ",
        "||": " or ",
        "&gt;": ">",
        "&lt;": "<"
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


def get_formula_values(att_dict, formula, type_of_dict=None):
    values = {}
    for att in att_dict:
        if type_of_dict:
            if (type_of_dict + '_' + att.attribute) in formula:
                values[(type_of_dict + '_' + att.attribute)] = flt(att.attribute_value)
        else:
            if att.attribute in formula:
                values[att.attribute] = flt(att.attribute_value)
    return values


def calculated_value_from_formula(rm_item_dict, fg_item_name, bom_template_name, fg_qty=0, process_sheet_name=None,
                                  is_wip=0):
    qty_dict = frappe._dict({})
    qty_list = []
    # bom_temp_name = get_bom_template_from_item(frappe.get_doc("Item", fg_item_name), so_detail=so_detail)
    bom_temp_doc = frappe.get_doc("BOM Template RIGPL", bom_template_name)
    formula = replace_java_chars(bom_temp_doc.formula)
    fg_item_doc = frappe.get_doc('Item', fg_item_name)
    if not fg_item_doc.variant_of:
        ps_doc = frappe.get_doc("Process Sheet", process_sheet_name)
        special_item_attr_doc = get_special_item_attribute_doc(item_name=fg_item_name,
                                                               so_detail=ps_doc.sales_order_item, docstatus=1)
        fg_att_dict = get_special_item_attributes(fg_item_name, special_item_attr_doc[0].name)
    else:
        fg_att_dict = get_attributes(fg_item_name)
    for d in rm_item_dict:
        rm_att_dict = get_attributes(d.get("name") or d.get("item_code"))
        qty = calculate_formula(rm_att=rm_att_dict, fg_att=fg_att_dict, formula=formula, fg_qty=fg_qty,
                                bt_name=bom_template_name, is_wip=is_wip)
        qty = convert_qty_per_uom(qty, d.get("item"))
        qty_dict["rm_item_code"] = d.get("name") or d.get("item_code")
        qty_dict["fg_item_code"] = fg_item_name
        qty_dict["qty"] = qty
        qty_list.append(qty_dict.copy())
    return qty_list


def calculate_formula(rm_att, fg_att, formula, fg_qty, bt_name, is_wip=0):
    if is_wip == 1:
        table_pref = "wip"
    else:
        table_pref = "fg"
    bt_doc = frappe.get_doc("BOM Template RIGPL", bt_name)
    rm_att = change_att_if_needed(rm_att, bt_doc, "rm")
    fg_att = change_att_if_needed(fg_att, bt_doc, table_pref)
    formula_values = frappe._dict({})
    formula_values['qty'] = fg_qty
    formula_values = formula_values.update(get_formula_values(rm_att, formula, "rm"))
    formula_values = formula_values.update(get_formula_values(fg_att, formula, "fg"))
    calc_qty = calculate_formula_values(formula, formula_values)
    return calc_qty


def change_att_if_needed(att_list, bom_template_doc, type_of_att):
    for att in att_list:
        for restriction in bom_template_doc.get(type_of_att + "_restrictions"):
            if att.attribute == restriction.attribute:
                if restriction.rename_field == 1:
                    att.attribute = restriction.renamed_field_name
    return att_list


def calculate_formula_values(formula, formula_values_dict):
    original_keys = formula_values_dict.keys()
    try:
        print(formula)
        if "compile" in formula:
            calc_value = (eval(formula))
            calc_value = eval(calc_value, formula_values_dict, formula_values_dict)
        else:
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
    if min_bal_qty < jc_doc.total_completed_qty < max_bal_qty and bal_qty != 0:
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
                    frappe.db.set_value("BOM Operation", ps_r.name, "status", "In Progress")

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
