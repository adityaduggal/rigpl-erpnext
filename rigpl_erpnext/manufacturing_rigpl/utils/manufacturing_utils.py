# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import math
import re

import frappe
from erpnext.stock.stock_balance import update_bin_qty
from frappe import _
from frappe.query_builder.functions import Count, Sum
from frappe.utils import add_years, cint, flt, nowdate
from pypika.terms import Tuple
from rohit_common.utils.rohit_common_utils import replace_java_chars

from ...utils.item_attribute_utils import attribute_filters, chunks, get_attribute_rows
from ...utils.item_utils import get_item_attributes
from ...utils.other_utils import auto_round_down, auto_round_up, round_up
from ...utils.sales_utils import get_pending_so_qty_from_soitem
from ...utils.stock_utils import get_quantities_for_item
from .batch_qty_utils import get_bin_map


def get_items_from_process_sheet_for_job_card(document, table_name, pro_sheet=None):
    """
    Copies the `table_name` rows of the Process Sheet to the Job Card. Pass `pro_sheet` when the
    caller has it loaded, so no query is needed.
    """
    document.set(table_name, [])
    if pro_sheet is None:
        pro_sheet = frappe.get_doc("Process Sheet", document.process_sheet)
    for d in pro_sheet.operations:
        if d.name == document.operation_id:
            document.operation = d.operation
    for d in pro_sheet.get(table_name):
        document.append(
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


def get_manufacturing_qty_settings():
    """
    Returns (base ROL multiplier, max months) of RIGPL Settings for get_qty_to_manufacture
    """
    base_multiplier, max_months = frappe.get_cached_value(
        "RIGPL Settings", "RIGPL Settings",
        ["base_rol_multiplier", "max_months_for_manufacturing_qty"],
    )
    base_multiplier, max_months = flt(base_multiplier), flt(max_months)
    if max_months <= 0:
        max_months = 3
    if base_multiplier <= 0:
        base_multiplier = 1
    return base_multiplier, max_months


def get_qty_to_manufacture(it_doc, qty_dict=None, settings=None):
    """
    Returns Min and Max Quantity to Manufacture. Pass `qty_dict` (get_quantities_for_items) and
    `settings` (get_manufacturing_qty_settings) when checking many items.
    """
    base_multiplier, max_months = settings or get_manufacturing_qty_settings()
    if qty_dict is None:
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
    """
    Returns a row for each Bin of the items with its actual_qty and the item totals prd_qty,
    on_so, on_po and planned. on_po adds the subcontracting warehouse stock, because on_po is wrong
    for Job Work items.
    """
    items = [d.get("name") or d.get("item_code") for d in item_dict]
    bins, totals = get_bin_map(items)
    availability = []
    for (item_code, warehouse), bin_row in bins.items():
        tot = totals[item_code]
        availability.append(frappe._dict(
            item_code=item_code,
            warehouse=warehouse,
            stock_uom=bin_row.stock_uom,
            actual_qty=bin_row.actual_qty,
            prd_qty=tot.prd_qty,
            on_so=tot.on_so,
            on_po=tot.on_po + flt(tot.subcon_qty),
            planned=tot.planned,
        ))
    return availability


def set_wip_row_quantities(wip, qty_rows):
    """
    Sets the stock quantities of an item_manufactured row from find_item_quantities rows. Only
    actual_qty is per Bin; the other quantities are item totals, the same in each Bin row.
    """
    act_qty, so_qty, po_qty, prd_qty, plan_qty = 0, 0, 0, 0, 0
    for d in qty_rows:
        if d.item_code == wip.item_code:
            wip.uom = d.stock_uom
            act_qty += d.actual_qty
            so_qty, po_qty, prd_qty, plan_qty = d.on_so, d.on_po, d.prd_qty, d.planned
    cur_proj = act_qty - so_qty - prd_qty
    wip.qty_available = act_qty
    wip.current_projected_qty = cur_proj
    wip.projected_qty = cur_proj + po_qty + plan_qty
    wip.qty = 0


def round_up_qty(qty):
    """Returns the qty rounded up to a whole number. A float error such as 26.0000001 stays 26."""
    return math.ceil(round(flt(qty), 6))


def sort_rm_rows_by_cost(rows, rates):
    """
    Sets `valuation_rate` and `rm_cost` (calculated qty x rate) on the RM rows, and sorts them with
    the lowest cost first. Rows with no rate come last. `rates` is {item_code: valuation rate}.
    """
    for row in rows:
        row.valuation_rate = flt(rates.get(row.item_code))
        row.rm_cost = flt(row.calculated_qty) * row.valuation_rate
    rows.sort(key=lambda row: (row.valuation_rate <= 0, row.rm_cost, row.item_code))
    for idx, row in enumerate(rows, start=1):
        row.idx = idx


# SQL functions that the RM and WIP rules use
RULE_FUNCTIONS = {"ceiling": math.ceil, "CEILING": math.ceil}
RULE_KEYWORDS = {"and", "or", "not", "True", "False"}


def get_known_item_attributes(item_name, process_sheet_name=None):
    """
    Returns the attribute rows of a known item of a rule. A special item (not a variant) uses the
    submitted Made to Order Item Attributes of the Sales Order Item of the Process Sheet.
    """
    if frappe.db.get_value("Item", item_name, "variant_of"):
        return get_item_attributes(item_name)
    so_detail = frappe.db.get_value("Process Sheet", process_sheet_name, "sales_order_item")
    special = get_special_item_attribute_doc(item_name=item_name, so_detail=so_detail, docstatus=1)
    return get_special_item_attributes(item_name, special[0].name)


def get_items_for_rules(restrictions, known, unknown_prefix, allow_zero_rol=None):
    """
    Returns [{name, description}] of the active items that pass all `restrictions` (the RM or WIP
    rows of a BOM Template). `known` is {prefix: attribute rows}, for example {"fg": rows}.
    A non-numeric rule filters in SQL, and "No" is not a filter. A numeric rule is checked in
    Python with the known values and the `<unknown_prefix>_` values of each item.
    """
    text_values, numeric_rules = {}, []
    for row in restrictions:
        if row.is_numeric == 1:
            numeric_rules.append(replace_java_chars(row.rule or ""))
        elif row.allowed_values != "No":
            values = split_allowed_values(row.allowed_values)
            if not values:
                return []
            text_values[row.attribute] = list(values)
    it = frappe.qb.DocType("Item")
    query = (
        frappe.qb.from_(it)
        .select(it.name, it.description)
        .where(it.disabled == 0)
        .where(it.end_of_life >= nowdate())
        .where(attribute_filters(it.name, text_values))
        .orderby(it.name)
    )
    if allow_zero_rol != 1:
        rol = frappe.qb.DocType("Item Reorder")
        query = query.where(
            it.name.isin(
                frappe.qb.from_(rol)
                .select(rol.parent)
                .where(rol.parenttype == "Item")
                .where(rol.warehouse_reorder_level > 0)
            )
        )
    items = query.run(as_dict=True)
    if not numeric_rules or not items:
        return items
    known_values = {
        f"{prefix}_{att.attribute}": flt(att.attribute_value)
        for prefix, rows in known.items()
        for att in rows
    }
    att_rows = get_attribute_rows([d.name for d in items])
    passed = []
    for item in items:
        values = dict(known_values)
        for att in att_rows.get(item.name, []):
            values[f"{unknown_prefix}_{att.attribute}"] = flt(att.attribute_value)
        if all(rule_passes(rule, values) for rule in numeric_rules):
            passed.append(item)
    return passed


def rule_passes(rule, values):
    """
    Returns True when the Python `rule` is true for `values`. A rule that needs a value that is not
    in `values` is false, as in SQL, where the missing attribute value is NULL.
    """
    names = set(re.findall(r"[A-Za-z_]\w*", rule)) - set(RULE_FUNCTIONS) - RULE_KEYWORDS
    if names - values.keys():
        return False
    return bool(calculate_formula_values(rule, dict(values, **RULE_FUNCTIONS)))


def get_special_item_attributes(it_name, special_item_attribute):
    attribute_dict = frappe.db.sql(
        """SELECT idx, name, attribute, attribute_value, numeric_values
        FROM `tabItem Variant Attribute` WHERE parent = %s AND parenttype = 'Made to Order Item Attributes' ORDER BY
        idx""",
        special_item_attribute,
        as_dict=1,
    )
    return attribute_dict


def get_bom_template_from_item(item_doc, so_detail=None, no_error=0):
    bom_template = {}
    if item_doc.variant_of:
        it_att_dict = get_item_attributes(item_doc.name)
        bom_template = get_bom_temp_from_it_att(
            item_doc, it_att_dict, get_template_usage([item_doc.name]).get(item_doc.name)
        )
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
    %s AND sales_order_item = %s""",
        (docstatus, item_name, so_detail),
        as_dict=1,
    )


def get_bom_temp_from_it_att(item_doc, att_dict, usage=None):
    return match_bom_templates(get_fg_restriction_rules(), att_dict, usage)


USAGE_YEARS = 2


def get_template_usage(items):
    """
    Returns {item: {template: count}} of the submitted Process Sheets of the last 2 years, in 1
    grouped query per chunk.
    """
    ps = frappe.qb.DocType("Process Sheet")
    usage = {}
    for chunk in chunks(items):
        for item, template, count in (
            frappe.qb.from_(ps)
            .select(ps.production_item, ps.bom_template, Count("*"))
            .where(ps.docstatus == 1)
            .where(ps.date >= add_years(nowdate(), -USAGE_YEARS))
            .where(ps.production_item.isin(chunk))
            .groupby(ps.production_item, ps.bom_template)
            .run()
        ):
            usage.setdefault(item, {})[template] = count
    return usage


FG_RULES_CACHE_KEY = "bom_template_fg_rules"
# Templates are indexed on the exact values of these FG attributes
INDEX_ATTRIBUTES = ("Base Material", "Tool Type")


def split_allowed_values(value):
    """Returns the set of values of a non-numeric rule, one value on each line."""
    return {line.strip() for line in (value or "").splitlines() if line.strip()}


def get_fg_restriction_rules():
    """
    Returns the FG rules of the active BOM Templates, prepared by `prepare_fg_rules`. They are
    kept in the cache, and BOM Template RIGPL clears the cache on save and delete.
    """
    return frappe.cache().get_value(FG_RULES_CACHE_KEY, read_fg_restriction_rules)


def clear_fg_rules_cache():
    frappe.cache().delete_value(FG_RULES_CACHE_KEY)


def read_fg_restriction_rules():
    """
    Reads {template: [FG restriction rows by idx]} and the priority of the active templates
    in one query. A template with no FG restrictions has an empty list (it matches all items).
    """
    bt = frappe.qb.DocType("BOM Template RIGPL")
    ivr = frappe.qb.DocType("Item Variant Restrictions")
    rows = (
        frappe.qb.from_(bt)
        .left_join(ivr)
        .on(
            (ivr.parent == bt.name)
            & (ivr.parenttype == "BOM Template RIGPL")
            & (ivr.parentfield == "fg_restrictions")
        )
        .select(
            bt.name.as_("template"), bt.priority, ivr.name.as_("row_name"), ivr.attribute,
            ivr.is_numeric, ivr.allowed_values, ivr.rule,
        )
        .where(bt.disabled == 0)
        .orderby(bt.name)
        .orderby(ivr.idx)
        .run(as_dict=True)
    )
    rules, priority = {}, {}
    for row in rows:
        template = row.pop("template")
        priority[template] = cint(row.pop("priority"))
        restrictions = rules.setdefault(template, [])
        if row.pop("row_name") is not None:
            restrictions.append(row)
    return prepare_fg_rules(rules, priority)


def prepare_fg_rules(rules, priority=None):
    """
    Returns {"rules", "priority", "index"} for `match_bom_templates`. The index maps a
    (Base Material, Tool Type) key to its templates. None in a key means that the template has
    no rule for that attribute, so it can match any value.
    """
    index = {}
    for template, restrictions in rules.items():
        key_values = []
        for attribute in INDEX_ATTRIBUTES:
            values = set()
            for row in restrictions:
                if row.attribute == attribute and row.is_numeric != 1:
                    values |= split_allowed_values(row.allowed_values)
            key_values.append(values or {None})
        for base_material in key_values[0]:
            for tool_type in key_values[1]:
                index.setdefault((base_material, tool_type), []).append(template)
    return {"rules": rules, "priority": priority or {}, "index": index}


def get_candidate_templates(prepared, att_dict):
    values = {att.attribute: att.attribute_value for att in att_dict}
    base_materials = (values.get(INDEX_ATTRIBUTES[0]), None)
    tool_types = (values.get(INDEX_ATTRIBUTES[1]), None)
    candidates = set()
    for base_material in set(base_materials):
        for tool_type in set(tool_types):
            candidates.update(prepared["index"].get((base_material, tool_type), []))
    return candidates


def match_bom_templates_bulk(items, so_details=None):
    """
    Returns {item: [templates]} for variant items in `items`, with 1 cached rules read, and 1
    attribute query and 1 usage query per chunk. Pass `so_details` as {item: Sales Order Item}
    for special items: they use the attributes of their submitted Made to Order Item Attributes.
    A special item code is shared by many Sales Orders, so its usage is not used.
    """
    so_details = so_details or {}
    prepared = get_fg_restriction_rules()
    variants = [item for item in items if item not in so_details]
    att_rows = get_attribute_rows(variants)
    usage = get_template_usage(variants)
    matched = {
        item: match_bom_templates(prepared, att_rows.get(item, []), usage.get(item))
        for item in variants
    }
    if so_details:
        mto = frappe.qb.DocType("Made to Order Item Attributes")
        special_docs = {}
        for chunk in chunks(so_details.values()):
            for name, item, so_detail in (
                frappe.qb.from_(mto)
                .select(mto.name, mto.item_code, mto.sales_order_item)
                .where(mto.docstatus == 1)
                .where(mto.sales_order_item.isin(chunk))
                .run()
            ):
                if so_details.get(item) == so_detail:
                    special_docs.setdefault(item, name)
        special_rows = get_attribute_rows(
            special_docs.values(), parenttype="Made to Order Item Attributes"
        )
        for item in so_details:
            doc = special_docs.get(item)
            matched[item] = match_bom_templates(prepared, special_rows.get(doc, [])) if doc else []
    return matched


def match_bom_templates(prepared, att_dict, usage=None):
    """
    Returns the templates whose FG restrictions all match the item attributes in `att_dict`.
    `prepared` comes from `prepare_fg_rules`. Only the templates of the item's index key are
    checked. A non-numeric rule matches when the item value is one of its values.
    The order is: the higher priority first, then the template that this item used most
    (`usage` is {template: count} from `get_template_usage`), then name.
    """
    bt_list = []
    item_attributes = {att.attribute for att in att_dict}
    rules = prepared["rules"]
    for bt_name in sorted(get_candidate_templates(prepared, att_dict)):
        fg_restrictions = rules[bt_name]
        total_score = len(fg_restrictions)
        match_score = 0
        exit_bt = 0
        # Before checking the formula always check if the attributes are there in the Item Attributes
        for bt_row in fg_restrictions:
            if bt_row.attribute not in item_attributes:
                exit_bt = 1
        if exit_bt == 0:
            for bt_rule in fg_restrictions:
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
                            if att.attribute_value in split_allowed_values(bt_rule.allowed_values):
                                match_score += 1
                                break
                            else:
                                exit_bt = 1
                                break
        if match_score == total_score:
            bt_list.append(bt_name)
    priority, usage = prepared["priority"], usage or {}
    bt_list.sort(key=lambda name: (-priority.get(name, 0), -usage.get(name, 0), name))
    return bt_list


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


def update_produced_qty(jc_doc, status="Submit", pro_sheet=None):
    # This function would update the produced qty in Process Sheet from Process Job Card and Close if needed
    # There are 2 places to update the Produced Qty one in the PSheet and Other in the Operation
    if pro_sheet is None:
        pro_sheet = frappe.get_doc("Process Sheet", jc_doc.process_sheet)
    min_qty, max_qty = get_min_max_ps_qty(pro_sheet.quantity)
    bal_qty = pro_sheet.produced_qty - pro_sheet.produced_qty
    if min_qty - pro_sheet.produced_qty < 0:
        min_bal_qty = 0
    else:
        min_bal_qty = min_qty - pro_sheet.produced_qty
    max_bal_qty = max_qty - pro_sheet.produced_qty
    if min_bal_qty < jc_doc.total_completed_qty < max_bal_qty and bal_qty != 0:
        frappe.msgprint(
            "Balance Ordered Qty = {} but Manufactured Qty = {} for Job Card# {} for Item Code: {}. Check "
            "Short Close Operation to Short Close the Operation".format(
                bal_qty, jc_doc.total_completed_qty, jc_doc.name, jc_doc.production_item
            )
        )

    for ps_r in pro_sheet.operations:
        if ps_r.name == jc_doc.operation_id:
            op_values, ps_values = get_produced_qty_changes(
                jc_doc, status, pro_sheet, ps_r, get_comp_qty_operation(ps_r.name)
            )
            if op_values:
                frappe.db.set_value("BOM Operation", ps_r.name, op_values)
            if ps_values:
                frappe.db.set_value("Process Sheet", pro_sheet.name, ps_values)


def get_comp_qty_operation(op_id):
    jc = frappe.qb.DocType("Process Job Card RIGPL")
    result = (
        frappe.qb.from_(jc)
        .select(Sum(jc.total_completed_qty))
        .where(jc.docstatus == 1)
        .where(jc.operation_id == op_id)
        .run()
    )
    return flt(result[0][0]) if result else 0


def update_qty_for_prod(item_code, warehouse, table_name):
    update_qty_for_prod_rows([(item_code, warehouse)], table_name)


def update_qty_for_prod_rows(pairs, table_name):
    """
    Sets reserved_qty_for_production in the Bin of each (item_code, warehouse) with one read
    """
    pairs = list(dict.fromkeys(pairs))
    qtys = get_qty_for_prod_map(pairs, table_name)
    for item_code, warehouse in pairs:
        update_bin_qty(item_code, warehouse,
            {"reserved_qty_for_production": qtys.get((item_code, warehouse), 0)})


def get_qty_for_prod_map(pairs, table_name):
    """
    Returns {(item_code, source_warehouse): qty still to consume in open Process Sheets}
    """
    ps = frappe.qb.DocType("Process Sheet")
    psi = frappe.qb.DocType("Process Sheet Items")
    qtys = {}
    for chunk in chunks(pairs):
        for item_code, warehouse, qty in (
            frappe.qb.from_(psi)
            .join(ps).on(ps.name == psi.parent)
            .select(psi.item_code, psi.source_warehouse, Sum(psi.calculated_qty - psi.qty))
            .where((psi.parenttype == "Process Sheet") & (psi.parentfield == table_name))
            .where((ps.docstatus == 1) & ps.status.notin(["Stopped", "Completed", "Short Closed"]))
            .where(psi.donot_consider_rm_for_production != 1)
            .where(Tuple(psi.item_code, psi.source_warehouse).isin([Tuple(*pair) for pair in chunk]))
            .groupby(psi.item_code, psi.source_warehouse)
            .run()
        ):
            qtys[(item_code, warehouse)] = flt(qty)
    return qtys


def get_qty_for_prod(item_code, warehouse, table_name):
    return get_qty_for_prod_map([(item_code, warehouse)], table_name).get((item_code, warehouse), 0)


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


def update_pro_sheet_rm_from_jc(jc_doc, status="Submit", pro_sheet=None):
    pro_sheet_doc = pro_sheet or frappe.get_doc("Process Sheet", jc_doc.process_sheet)
    changed = []
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
                changed.append((row.item_code, row.source_warehouse))
    # Reserved qty for production of the rows that changed
    update_qty_for_prod_rows(changed, table_name="rm_consumed")


def get_produced_qty_changes(jc_doc, status, pro_sheet, ps_r, tc_comp_qty):
    """
    Returns the new values ({field: value}) for the BOM Operation row `ps_r` and for the Process
    Sheet after a Job Card submit or cancel. `tc_comp_qty` is the completed qty of the operation.
    A later value for a field replaces an earlier one, as the single-field writes did.
    """
    op_values = {}
    ps_values = {}
    if status == "Submit":
        op_values["completed_qty"] = tc_comp_qty if tc_comp_qty > 0 else 0
        if pro_sheet.status == "Submitted":
            ps_values["status"] = "In Progress"
        if tc_comp_qty >= ps_r.planned_qty or jc_doc.short_close_operation == 1:
            op_values["status"] = "Completed"
        else:
            op_values["status"] = "In Progress"
    else:
        op_values["completed_qty"] = tc_comp_qty if tc_comp_qty > 0 else 0
        if tc_comp_qty < ps_r.planned_qty or jc_doc.short_close_operation == 1:
            op_values["status"] = "In Progress"

    if ps_r.idx == 1 and status == "Submit":
        tc_comp_qty = pro_sheet.produced_qty + jc_doc.total_completed_qty
        ps_values["produced_qty"] = tc_comp_qty if tc_comp_qty > 0 else 0
        if tc_comp_qty >= pro_sheet.quantity:
            ps_values["status"] = "Completed"
        elif jc_doc.short_close_operation != 1:
            ps_values["status"] = "In Progress"
        else:
            sc_qty = pro_sheet.quantity - jc_doc.total_completed_qty - pro_sheet.produced_qty
            tc_comp_qty = pro_sheet.quantity
            ps_values["produced_qty"] = tc_comp_qty if tc_comp_qty > 0 else 0
            ps_values["short_closed_qty"] = sc_qty if sc_qty > 0 else 0
            ps_values["status"] = "Short Closed"
    elif ps_r.idx == 1 and status == "Cancel":
        if jc_doc.short_close_operation != 1:
            tc_comp_qty = pro_sheet.produced_qty - jc_doc.total_completed_qty
            ps_values["produced_qty"] = tc_comp_qty if tc_comp_qty > 0 else 0
        else:
            tc_comp_qty = pro_sheet.quantity - jc_doc.total_completed_qty - pro_sheet.short_closed_qty
            ps_values["produced_qty"] = tc_comp_qty if tc_comp_qty > 0 else 0
            ps_values["short_closed_qty"] = 0
    return op_values, ps_values
