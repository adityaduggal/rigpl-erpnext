# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import math
import re

import frappe
from erpnext.stock.stock_balance import update_bin_qty
from frappe import _
from frappe.utils import flt
from rohit_common.utils.rohit_common_utils import replace_java_chars

from ...utils.item_utils import get_item_attributes
from ...utils.other_utils import auto_round_down, auto_round_up, round_up
from ...utils.sales_utils import get_pending_so_qty_from_soitem
from ...utils.stock_utils import get_quantities_for_item


def get_planned_qty(item_name):
    planned = 0
    planned_dict = frappe._dict({})
    work_orders = frappe.db.sql(
        """SELECT SUM(qty - produced_qty) as wo_plan FROM `tabWork Order`
    WHERE docstatus = 1 AND status != 'Stopped' AND production_item = '%s'"""
        % item_name,
        as_list=1,
    )

    psheet = frappe.db.sql(
        """SELECT production_item as item, SUM(quantity - produced_qty) as ps_plan
    FROM `tabProcess Sheet` WHERE docstatus = 1 AND status != 'Short Closed' AND status != 'Stopped'
    AND status != 'Completed' AND production_item = '%s'"""
        % item_name,
        as_dict=1,
    )
    if flt(work_orders[0][0]) > 0:
        planned += work_orders[0][0]

    if psheet[0].item:
        planned += psheet[0].ps_plan
    planned_dict["item"] = item_name
    planned_dict["planned"] = planned

    return planned_dict


def get_items_from_process_sheet_for_job_card(document, table_name):
    document.set(table_name, [])
    pro_sheet = frappe.get_doc("Process Sheet", document.process_sheet)
    for d in pro_sheet.operations:
        if d.name == document.operation_id:
            document.operation = d.operation
    for d in frappe.get_all(
        "Process Sheet Items",
        fields=["*"],
        filters={
            "parenttype": "Process Sheet",
            "parent": document.process_sheet,
            "parentfield": table_name,
        },
        order_by="idx",
    ):
        child = document.append(
            table_name,
            {
                "idx": d.idx,
                "item_code": d.item_code,
                "description": d.description,
                "source_warehouse": d.source_warehouse,
                "target_warehouse": d.target_warehouse,
                "uom": d.uom,
            },
        )


def get_priority_for_stock_prd(it_name, qty_dict, qty_before_process=0):
    # This would give priority from 20 and above for a factor. Factor to be like for SO only
    # factor = calc_rol * vr / qty
    factor = 0
    resd_prd = qty_dict["reserved_for_prd"]
    rol_vr_lead_factor = (
        qty_dict["calculated_rol"]
        * (qty_dict["valuation_rate"] + 1)
        * qty_dict["lead_time"]
    )
    bal_fin = qty_dict["finished_qty"] - qty_dict["on_so"]
    bal_aft_prd = bal_fin - resd_prd + qty_before_process
    if bal_fin < 0:
        bal_fin = 0
    if bal_aft_prd < 0:
        bal_aft_prd = 0
    if resd_prd == 0:
        factor = rol_vr_lead_factor / (bal_fin + 1)
    else:
        factor = rol_vr_lead_factor / (bal_aft_prd + 1)
    if resd_prd == 0:
        if factor > 1000000:
            return 30
        elif factor > 500000:
            return 31
        elif factor > 250000:
            return 32
        elif factor > 150000:
            return 33
        elif factor > 100000:
            return 34
        elif factor > 50000:
            return 35
        elif factor > 25000:
            return 36
        elif factor > 10000:
            return 37
        elif factor > 5000:
            return 38
        else:
            return 39
    else:
        if factor > 1000000:
            return 20
        elif factor > 500000:
            return 21
        elif factor > 250000:
            return 22
        elif factor > 150000:
            return 23
        elif factor > 100000:
            return 24
        elif factor > 50000:
            return 25
        elif factor > 25000:
            return 26
        elif factor > 10000:
            return 27
        elif factor > 5000:
            return 28
        else:
            return 29


def get_qty_to_manufacture(it_doc):
    """
    Returns Min and Max Quantity to Manufacture
    """
    base_multiplier = flt(
        frappe.get_value("RIGPL Settings", "RIGPL Settings", "base_rol_multiplier")
    )
    max_months = flt(
        frappe.get_value(
            "RIGPL Settings", "RIGPL Settings", "max_months_for_manufacturing_qty"
        )
    )
    if max_months <= 0:
        max_months = 3
    if base_multiplier <= 0:
        base_multiplier = 1
    qty_dict = get_quantities_for_item(it_doc)
    # print(qty_dict)
    calc_rol = qty_dict["calculated_rol"]
    lead = qty_dict["lead_time"] if qty_dict["lead_time"] > 0 else 30
    soq = qty_dict["on_so"]
    poq = qty_dict["on_po"]
    prd = qty_dict["reserved_for_prd"]
    fgq = qty_dict["finished_qty"] + qty_dict["dead_qty"]
    wipq = qty_dict["wip_qty"]
    plan = qty_dict["planned_qty"]
    rol = qty_dict["re_order_level"]
    rol_multiplier = base_multiplier * calc_rol * lead / 30
    qty_on_docs = soq + prd - fgq - wipq - plan - poq
    reqd_qty = max(rol_multiplier + qty_on_docs, 0)
    max_reqd_qty = max((max_months * rol_multiplier) + qty_on_docs, 0)
    if rol > 0:
        reqd_qty = auto_round_down(reqd_qty)
        max_reqd_qty = auto_round_up(max_reqd_qty)
    else:
        reqd_qty = round(reqd_qty)
        max_reqd_qty = round(max_reqd_qty)
    return reqd_qty, max_reqd_qty


def convert_qty_per_uom(qty, item_name):
    uom_name = frappe.get_value("Item", item_name, "stock_uom")
    uom_whole_number = frappe.get_value("UOM", uom_name, "must_be_whole_number")
    if uom_whole_number == 1:
        qty = int(flt(qty))
    else:
        qty = flt(qty)
    return qty


def get_oal_field(btd, table):
    for d in btd.get(table):
        if d.renamed_field_name == "oal":
            return d.attribute


def get_oal_frm_item_code(item_code, qty, oal_field, so_detail=None):
    itd = frappe.get_doc("Item", item_code)
    if itd.made_to_order == 1:
        spl = get_special_item_attribute_doc(item_name=item_code, so_detail=so_detail)
        it_dict = get_special_item_attributes(
            it_name=item_code, special_item_attribute=spl[0].name
        )
    else:
        it_dict = get_item_attributes(item_code)
    for d in it_dict:
        if d.attribute == oal_field:
            return qty * flt(d.attribute_value)


def find_item_quantities(item_dict):
    availability = []
    for d in item_dict:
        one_item_availability = frappe.db.sql(
            """SELECT name, warehouse, item_code, stock_uom, valuation_rate,
        actual_qty,
        (SELECT SUM(reserved_qty_for_production) FROM `tabBin` WHERE docstatus = 0 AND item_code = '%s') as prd_qty,
        (SELECT SUM(reserved_qty) FROM `tabBin` WHERE docstatus = 0 AND item_code = '%s') as on_so,
        (SELECT SUM(ordered_qty) FROM `tabBin` WHERE docstatus = 0 AND item_code = '%s') as on_po,
        (SELECT SUM(planned_qty) FROM `tabBin` WHERE docstatus = 0 AND item_code = '%s') as planned
        FROM `tabBin` WHERE docstatus = 0
        AND item_code = '%s'"""
            % (
                (d.get("name") or d.get("item_code")),
                (d.get("name") or d.get("item_code")),
                (d.get("name") or d.get("item_code")),
                (d.get("name") or d.get("item_code")),
                (d.get("name") or d.get("item_code")),
            ),
            as_dict=1,
        )
        # If Item is for Job Work then need to get the PO Items for that as well since on_po is wrong in that case
        # In that case get the quantity of the Material in Sub-Contracting Warehouse
        subcon = frappe.db.sql(
            """SELECT bn.item_code, bn.actual_qty, wh.name FROM `tabBin` bn, `tabWarehouse` wh
        WHERE wh.name = bn.warehouse AND wh.is_subcontracting_warehouse = 1 AND bn.actual_qty > 0
        AND bn.item_code = '%s'"""
            % d.get("item_code"),
            as_dict=1,
        )

        if one_item_availability:
            if subcon:
                for available in one_item_availability:
                    available.on_po += subcon[0].actual_qty
            for available in one_item_availability:
                availability.append(available)
    return availability


def convert_wip_rule_to_mysql_statement(
    rule, fg_item, rm_item, process_sheet_name=None
):
    new_rule = replace_java_to_mysql(rule)
    fg_item_doc = frappe.get_doc("Item", fg_item)
    if not fg_item_doc.variant_of:
        ps_doc = frappe.get_doc("Process Sheet", process_sheet_name)
        special_item_attr_doc = get_special_item_attribute_doc(
            item_name=fg_item, so_detail=ps_doc.sales_order_item, docstatus=1
        )
        fg_att_dict = get_special_item_attributes(
            fg_item, special_item_attr_doc[0].name
        )
    else:
        fg_att_dict = get_item_attributes(fg_item)
    rm_att_dict = get_item_attributes(rm_item)
    res = re.findall(r"\w+", rule)
    for word in res:
        if word[:3] == "fg_":
            for d in fg_att_dict:
                if d.attribute == word[3:]:
                    new_rule = new_rule.replace(word, d.attribute_value)
        elif word[:3] == "rm_":
            for d in rm_att_dict:
                if d.attribute == word[3:]:
                    new_rule = new_rule.replace(word, d.attribute_value)
        if word[:4] == "wip_":
            new_rule = new_rule.replace(word, word[4:] + ".attribute_value")
    new_rule = " AND " + new_rule
    return new_rule


def convert_rule_to_mysql_statement(rule, it_dict, process_sheet_name=None):
    new_rule = replace_java_to_mysql(rule)
    it_name = it_dict.get("known_item")
    it_doc = frappe.get_doc("Item", it_name)
    if not it_doc.variant_of:
        ps_doc = frappe.get_doc("Process Sheet", process_sheet_name)
        special_item_attr_doc = get_special_item_attribute_doc(
            item_name=it_name, so_detail=ps_doc.sales_order_item, docstatus=1
        )
        known_it_att_dict = get_special_item_attributes(
            it_name, special_item_attr_doc[0].name
        )
    else:
        known_it_att_dict = get_item_attributes(it_name)
    known_type = it_dict.get(it_name)
    unknown_type = it_dict.get("unknown_type")
    res = re.findall(r"\w+", rule)
    for word in res:
        if word[: len(known_type) + 1] == known_type + "_":
            for d in known_it_att_dict:
                if d.attribute == word[len(known_type) + 1 :]:
                    new_rule = new_rule.replace(word, d.attribute_value)

        if word[: len(unknown_type) + 1] == unknown_type + "_":
            new_rule = new_rule.replace(
                word, word[len(unknown_type) + 1 :] + ".attribute_value"
            )
    new_rule = " AND " + new_rule
    return new_rule


def get_special_item_attributes(it_name, special_item_attribute):
    attribute_dict = frappe.db.sql(
        """SELECT idx, name, attribute, attribute_value, numeric_values
        FROM `tabItem Variant Attribute` WHERE parent = '%s' AND parenttype = 'Made to Order Item Attributes' ORDER BY
        idx"""
        % special_item_attribute,
        as_dict=1,
    )
    return attribute_dict


def get_bom_template_from_item(item_doc, so_detail=None, no_error=0):
    bom_template = {}
    if item_doc.variant_of:
        it_att_dict = get_item_attributes(item_doc.name)
        bom_template = get_bom_temp_from_it_att(item_doc, it_att_dict)
        if not bom_template:
            if no_error == 0:
                frappe.throw("No BOM Template found for Item: {}".format(item_doc.name))
            else:
                return []
    else:
        # Find Item Attributes in Special Item Table or Create a New Special Item Table and ask user to fill it.
        if so_detail:
            special_attributes = get_special_item_attribute_doc(
                item_name=item_doc.name, so_detail=so_detail, docstatus=1
            )
            if not special_attributes:
                sp_att_draft = get_special_item_attribute_doc(
                    item_name=item_doc.name, so_detail=so_detail, docstatus=0
                )
                if sp_att_draft:
                    frappe.throw(
                        "Special Item Attributes not Submitted please fill and Submit {}".format(
                            frappe.get_desk_link(
                                "Made to Order Item Attributes", sp_att_draft[0].name
                            )
                        )
                    )
                else:
                    create_new_special_attributes(item_doc.name, so_detail)
                    frappe.msgprint("Fill the Special Item Attributes and Try Again")
            else:
                # Get Special Attributes from the Table and then find bom template
                it_att_dict = get_special_item_attributes(
                    item_doc.name, special_attributes[0].name
                )
                bom_template = get_bom_temp_from_it_att(item_doc, it_att_dict)
        else:
            frappe.throw(
                "{} item seems like a Special Item hence Sales Order is Mandatory for the same.".format(
                    item_doc.name
                )
            )
    return bom_template


def create_new_special_attributes(it_name, so_detail):
    special = frappe.new_doc("Made to Order Item Attributes")
    special.item_code = it_name
    special.sales_order_item = so_detail
    special.sales_order = frappe.get_value("Sales Order Item", so_detail, "parent")
    special.description = frappe.get_value("Sales Order Item", so_detail, "description")
    special.sno = frappe.get_value("Sales Order Item", so_detail, "idx")
    special.insert()
    frappe.db.commit()
    frappe.msgprint(
        _("{} created").format(
            frappe.get_desk_link("Made to Order Item Attributes", special.name)
        )
    )


def get_special_item_attribute_doc(item_name, so_detail, docstatus=1):
    return frappe.db.sql(
        """SELECT name FROM `tabMade to Order Item Attributes` WHERE docstatus = %s AND item_code =
    '%s' AND sales_order_item = '%s'"""
        % (docstatus, item_name, so_detail),
        as_dict=1,
    )


def get_bom_temp_from_it_att(item_doc, att_dict):
    bt_list = []
    all_bt = frappe.get_all("BOM Template RIGPL", order_by="name")
    for bt in all_bt:
        bt_doc = frappe.get_doc("BOM Template RIGPL", bt.name)
        total_score = len(bt_doc.fg_restrictions)
        match_score = 0
        exit_bt = 0
        # Before checking the formula always check if the attributes are there in the Item Attributes
        for bt_row in bt_doc.fg_restrictions:
            exists = 0
            for att in att_dict:
                if bt_row.attribute == att.attribute:
                    exists = 1
                    break
            if exists == 0:
                exit_bt = 1
        if exit_bt == 0:
            for bt_rule in bt_doc.fg_restrictions:
                if exit_bt == 1:
                    break
                for att in att_dict:
                    if (
                        bt_rule.is_numeric == 1
                        and att.numeric_values == 1
                        and exit_bt != 1
                    ):
                        formula = replace_java_chars(bt_rule.rule)
                        formula_values = get_formula_values(att_dict, formula, "fg")
                        dont_calculate_formula = 0
                        for key in formula_values.keys():
                            if key not in formula:
                                dont_calculate_formula = 1
                                break
                        if dont_calculate_formula == 0:
                            calculated_value = calculate_formula_values(
                                formula, formula_values
                            )
                        else:
                            break
                        if calculated_value == 1:
                            match_score += 1
                            break
                    else:
                        if att.attribute == bt_rule.attribute and exit_bt != 1:
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
        "false": "False",
        "true": "True",
        "&&": " and ",
        "||": " or ",
        "&gt;": ">",
        "&lt;": "<",
        "==": "=",
        "!=": "!=",
    }

    for k, v in replace_dict.items():
        string = string.replace(k, v)
    return string


def calculate_operation_time(ps_doc, rt_dict, fg_it_doc, rm_it_dict):
    if fg_it_doc.variant_of:
        fg_attributes = get_item_attributes(fg_it_doc.name)
    elif fg_it_doc.made_to_order == 1:
        special_item_attr_doc = get_special_item_attribute_doc(
            item_name=fg_it_doc.name, so_detail=ps_doc.sales_order_item, docstatus=1
        )
        fg_attributes = get_special_item_attributes(
            fg_it_doc.name, special_item_attr_doc[0].name
        )
    else:
        frappe.throw(
            "{} selected is neither a Variant nor Made to Order Item".format(
                frappe.get_desk_link()
            )
        )
    for d in ps_doc.operations:
        formula_values = frappe._dict({})
        for op in rt_dict:
            if op.time_based_on_formula == 1 and d.operation == op.operation:
                op_time_formula_edited = replace_java_chars(op.operation_time_formula)
                formula_values = formula_values.update(
                    get_formula_values(fg_attributes, op_time_formula_edited, "fg")
                )
                for rm in rm_it_dict:
                    rm_attributes = get_item_attributes(rm.name)
                    formula_values = formula_values.update(
                        get_formula_values(rm_attributes, op_time_formula_edited, "rm")
                    )
                operation_time = calculate_formula_values(
                    op_time_formula_edited, formula_values
                )
                d.time_in_mins = int(operation_time * ps_doc.quantity / d.batch_size)
            elif op.time_based_on_formula != 1:
                d.time_in_mins = int(op.time_in_mins * ps_doc.quantity / d.batch_size)


def calculate_batch_size(ps_doc, rt_dict, fg_it_doc, rm_it_dict):
    if ps_doc.sales_order_item:
        special_item_attr_doc = get_special_item_attribute_doc(
            item_name=fg_it_doc.name, so_detail=ps_doc.sales_order_item, docstatus=1
        )
        fg_attributes = get_special_item_attributes(
            fg_it_doc.name, special_item_attr_doc[0].name
        )
    else:
        fg_attributes = get_item_attributes(fg_it_doc.name)
    for d in ps_doc.operations:
        formula_values = frappe._dict({})
        for op in rt_dict:
            if op.batch_size_based_on_formula == 1 and d.operation == op.operation:
                batch_edited_formula = replace_java_chars(op.batch_size_formula)
                formula_values = formula_values.update(
                    get_formula_values(fg_attributes, batch_edited_formula, "fg")
                )
                for rm in rm_it_dict:
                    rm_attributes = get_item_attributes(rm.name)
                    formula_values = formula_values.update(
                        get_formula_values(rm_attributes, batch_edited_formula, "rm")
                    )
                batch_size = calculate_formula_values(
                    batch_edited_formula, formula_values
                )
                batch_size = convert_qty_per_uom(batch_size, fg_it_doc.name)
                d.batch_size = batch_size


def get_formula_values(att_dict, formula, type_of_dict=None):
    values = {}
    for att in att_dict:
        if type_of_dict:
            if (type_of_dict + "_" + att.attribute) in formula:
                values[(type_of_dict + "_" + att.attribute)] = flt(att.attribute_value)
        else:
            if att.attribute in formula:
                values[att.attribute] = flt(att.attribute_value)
    return values


def calculated_value_from_formula(
    rm_item_dict,
    fg_item_name,
    bom_template_name,
    fg_qty=0,
    process_sheet_name=None,
    is_wip=0,
):
    qty_dict = frappe._dict({})
    qty_list = []
    # bom_temp_name = get_bom_template_from_item(frappe.get_doc("Item", fg_item_name), so_detail=so_detail)
    bom_temp_doc = frappe.get_doc("BOM Template RIGPL", bom_template_name)
    formula = replace_java_chars(bom_temp_doc.formula)
    fg_item_doc = frappe.get_doc("Item", fg_item_name)
    if not fg_item_doc.variant_of:
        ps_doc = frappe.get_doc("Process Sheet", process_sheet_name)
        special_item_attr_doc = get_special_item_attribute_doc(
            item_name=fg_item_name, so_detail=ps_doc.sales_order_item, docstatus=1
        )
        fg_att_dict = get_special_item_attributes(
            fg_item_name, special_item_attr_doc[0].name
        )
    else:
        fg_att_dict = get_item_attributes(fg_item_name)
    for d in rm_item_dict:
        rm_att_dict = get_item_attributes(d.get("name") or d.get("item_code"))
        qty = calculate_formula(
            rm_att=rm_att_dict,
            fg_att=fg_att_dict,
            formula=formula,
            fg_qty=fg_qty,
            bt_name=bom_template_name,
            is_wip=is_wip,
        )
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
    formula_values["qty"] = fg_qty
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
        if "compile" in formula:
            calc_value = eval(formula)
            calc_value = eval(calc_value, formula_values_dict, formula_values_dict)
        else:
            calc_value = eval(formula, formula_values_dict, formula_values_dict)
    except Exception as e:
        frappe.throw(
            "\n\n".join(
                map(
                    str,
                    [
                        formula,
                        {
                            k: v
                            for k, v in formula_values_dict.items()
                            if k in original_keys
                        },
                        e,
                    ],
                )
            )
        )
    return calc_value


def calculate_operation_cost(document):
    for d in document.operations:
        d.hour_rate = get_workstation_hr_cost(d.workstation)
        d.operating_cost = int(d.hour_rate * d.time_in_mins / 60)


def get_workstation_hr_cost(workstation):
    wk_doc = frappe.get_doc("Workstation", workstation)
    return wk_doc.hour_rate


def check_jc_needed_for_ps(psd):
    if psd.sales_order_item:
        pend_qty = get_pending_so_qty_from_soitem(psd.sales_order_item)
        if pend_qty > 0:
            return 1
        else:
            return 0
    else:
        return 1


def update_produced_qty(jc_doc, status="Submit"):
    # This function would update the produced qty in Process Sheet from Process Job Card and Close if needed
    # There are 2 places to update the Produced Qty one in the PSheet and Other in the Operation
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
        frappe.msgprint(
            "Balance Ordered Qty = {} but Manufactured Qty = {} for Job Card# {} for Item Code: {}. Check "
            "Short Close Operation to Short Close the Operation".format(
                bal_qty, jc_doc.total_completed_qty, jc_doc.name, jc_doc.production_item
            )
        )

    for ps_r in pro_sheet.operations:
        if ps_r.name == jc_doc.operation_id:
            if status == "Submit":
                tc_comp_qty = get_comp_qty_operation(ps_r.name)
                frappe.db.set_value(
                    "BOM Operation",
                    ps_r.name,
                    "completed_qty",
                    tc_comp_qty if tc_comp_qty > 0 else 0,
                )
                if pro_sheet.status == "Submitted":
                    frappe.db.set_value(
                        "Process Sheet", pro_sheet.name, "status", "In Progress"
                    )
                if tc_comp_qty >= ps_r.planned_qty or jc_doc.short_close_operation == 1:
                    frappe.db.set_value(
                        "BOM Operation", ps_r.name, "status", "Completed"
                    )
                else:
                    frappe.db.set_value(
                        "BOM Operation", ps_r.name, "status", "In Progress"
                    )
            else:
                tc_comp_qty = get_comp_qty_operation(
                    ps_r.name
                )  # jc_doc.total_completed_qty
                frappe.db.set_value(
                    "BOM Operation",
                    ps_r.name,
                    "completed_qty",
                    tc_comp_qty if tc_comp_qty > 0 else 0,
                )
                if tc_comp_qty < ps_r.planned_qty or jc_doc.short_close_operation == 1:
                    frappe.db.set_value(
                        "BOM Operation", ps_r.name, "status", "In Progress"
                    )

            if ps_r.idx == 1 and status == "Submit":
                tc_comp_qty = pro_sheet.produced_qty + jc_doc.total_completed_qty
                frappe.db.set_value(
                    "Process Sheet",
                    pro_sheet.name,
                    "produced_qty",
                    tc_comp_qty if tc_comp_qty > 0 else 0,
                )
                if tc_comp_qty >= pro_sheet.quantity:
                    frappe.db.set_value(
                        "Process Sheet", pro_sheet.name, "status", "Completed"
                    )
                elif jc_doc.short_close_operation != 1:
                    frappe.db.set_value(
                        "Process Sheet", pro_sheet.name, "status", "In Progress"
                    )
                else:
                    sc_qty = (
                        pro_sheet.quantity
                        - jc_doc.total_completed_qty
                        - pro_sheet.produced_qty
                    )
                    tc_comp_qty = pro_sheet.quantity
                    frappe.db.set_value(
                        "Process Sheet",
                        pro_sheet.name,
                        "produced_qty",
                        tc_comp_qty if tc_comp_qty > 0 else 0,
                    )
                    frappe.db.set_value(
                        "Process Sheet",
                        pro_sheet.name,
                        "short_closed_qty",
                        sc_qty if sc_qty > 0 else 0,
                    )
                    frappe.db.set_value(
                        "Process Sheet", pro_sheet.name, "status", "Short Closed"
                    )
            elif ps_r.idx == 1 and status == "Cancel":
                if jc_doc.short_close_operation != 1:
                    tc_comp_qty = pro_sheet.produced_qty - jc_doc.total_completed_qty
                    frappe.db.set_value(
                        "Process Sheet",
                        pro_sheet.name,
                        "produced_qty",
                        tc_comp_qty if tc_comp_qty > 0 else 0,
                    )
                else:
                    sc_qty = 0
                    tc_comp_qty = (
                        pro_sheet.quantity
                        - jc_doc.total_completed_qty
                        - pro_sheet.short_closed_qty
                    )
                    frappe.db.set_value(
                        "Process Sheet",
                        pro_sheet.name,
                        "produced_qty",
                        tc_comp_qty if tc_comp_qty > 0 else 0,
                    )
                    frappe.db.set_value(
                        "Process Sheet", pro_sheet.name, "short_closed_qty", 0
                    )


def get_comp_qty_operation(op_id):
    qty_dict = frappe.db.sql(
        """SELECT SUM(total_completed_qty) as tot_qty FROM `tabProcess Job Card RIGPL`
    WHERE docstatus = 1 AND operation_id = '%s'"""
        % op_id,
        as_dict=1,
    )
    if qty_dict:
        return flt(qty_dict[0].tot_qty)
    else:
        return 0


def update_qty_for_prod(item_code, warehouse, table_name):
    update_bin_qty(
        item_code,
        warehouse,
        {
            "reserved_qty_for_production": get_qty_for_prod(
                item_code, warehouse, table_name
            )
        },
    )


def get_qty_for_prod_for_item(item_code, warehouse=None):
    wh_cond = ""
    if warehouse:
        wh_cond += f" AND psi.source_warehouse = {warehouse}"
    qty_res_for_prod = frappe.db.sql(
        f"""SELECT SUM(psi.calculated_qty - psi.qty) as qty_prod
        FROM `tabProcess Sheet Items` psi, `tabProcess Sheet` ps
        WHERE ps.name = psi.parent AND psi.parenttype = 'Process Sheet' AND ps.docstatus = 1
        AND psi.parentfield = 'rm_consumed' AND ps.status NOT IN ("Stopped", "Completed",
        "Short Closed") AND psi.donot_consider_rm_for_production != 1
        AND psi.item_code = '{item_code}' {wh_cond}""",
        as_dict=1,
    )

    return flt(qty_res_for_prod[0].qty_prod) if qty_res_for_prod else 0


def get_qty_for_prod(item_code, warehouse, table_name):
    qty_res_for_prod = frappe.db.sql(
        """SELECT SUM(psi.calculated_qty - psi.qty) FROM `tabProcess Sheet Items` psi,
    `tabProcess Sheet` ps
    WHERE ps.name = psi.parent AND psi.parenttype = 'Process Sheet' AND ps.docstatus = 1 AND psi.parentfield = '%s' AND
    ps.status NOT IN ("Stopped", "Completed", "Short Closed") AND psi.donot_consider_rm_for_production != 1
    AND psi.item_code = '%s' AND psi.source_warehouse = '%s'"""
        % (table_name, item_code, warehouse)
    )

    return flt(qty_res_for_prod[0][0]) if qty_res_for_prod else 0


def update_planned_qty(item_code, warehouse):
    update_bin_qty(
        item_code,
        warehouse,
        {"planned_qty": get_planned_qty_process(item_code, warehouse)},
    )


def get_planned_qty_process(item_code, warehouse):
    planned_qty = frappe.db.sql(
        """ SELECT IF(SUM(quantity - produced_qty) > 0, SUM(quantity - produced_qty), 0) FROM
    `tabProcess Sheet` WHERE production_item = %s and fg_warehouse = %s and status NOT IN
    ("Stopped", "Completed", "Short Closed") AND docstatus=1 AND quantity > produced_qty""",
        (item_code, warehouse),
    )

    return flt(planned_qty[0][0]) if planned_qty else 0


def check_warehouse_in_child_tables(document, table_name, type_of_table):
    for row in document.get(table_name):
        if type_of_table == "Consume":
            row.target_warehouse = ""
            if not row.source_warehouse:
                frappe.throw(
                    "Source Warehouse is Mandatory for Row# {}".format(row.idx)
                )
        elif type_of_table == "Production":
            row.source_warehouse = ""
            if not row.target_warehouse:
                frappe.throw(
                    "Target Warehouse is Mandatory for Row# {}".format(row.idx)
                )


def update_warehouse_from_bt(pro_sheet_doc):
    bt_doc = frappe.get_doc("BOM Template RIGPL", pro_sheet_doc.bom_template)
    for row in pro_sheet_doc.operations:
        for bt_row in bt_doc.operations:
            if row.operation == bt_row.operation and row.idx == bt_row.idx:
                if not row.source_warehouse:
                    row.source_warehouse = bt_row.source_warehouse
                if not row.target_warehouse:
                    row.target_warehouse = bt_row.target_warehouse


def get_min_max_ps_qty(qty):
    manuf_settings = frappe.get_single("Manufacturing Settings")
    over_prod = manuf_settings.overproduction_percentage_for_work_order
    max_qty = math.ceil(qty * (1 + over_prod / 100))
    min_qty = math.floor(qty * (1 - over_prod / 100))
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
                    frappe.db.set_value(
                        "Process Sheet Items",
                        row.name,
                        "qty",
                        tc_qty if tc_qty > 0 else 0,
                    )
                else:
                    frappe.db.set_value(
                        "Process Sheet Items", row.name, "qty", row.calculated_qty
                    )
        update_qty_for_prod(
            row.item_code, row.source_warehouse, table_name="rm_consumed"
        )
