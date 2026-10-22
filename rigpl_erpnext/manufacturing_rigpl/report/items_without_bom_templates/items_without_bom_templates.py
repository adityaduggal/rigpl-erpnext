# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from rigpl_erpnext.manufacturing_rigpl.utils.manufacturing_utils import (
    get_fg_restriction_rules,
    match_bom_templates,
)
from rigpl_erpnext.utils.item_attribute_utils import get_attribute_rows


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        "Item:Link/Item:150",
        "Description::400",
        "BOM Templates::300",
        "Variant Of:Link/Item:300",
    ]


def get_data(filters):
    """
    Returns each manufactured variant with its BOM Templates. The templates and the attributes
    of all items are read once, then each item is matched in memory (#137).
    """
    data = []
    items = get_items(filters)
    rules = get_fg_restriction_rules()
    att_rows = get_attribute_rows([d.name for d in items])
    for d in items:
        bt_name = match_bom_templates(rules, att_rows.get(d.name, []))
        bt_names_concat = " "
        if bt_name:
            if len(bt_name) == 1:
                bt_names_concat += bt_name[0]
            else:
                for bt in bt_name:
                    bt_names_concat += bt + ", "
        else:
            bt_names_concat = "No Applicable BOM Templates Found"
        data.append([d.name, d.description, bt_names_concat, d.variant_of])
    return data


def get_items(filters):
    it = frappe.qb.DocType("Item")
    query = (
        frappe.qb.from_(it)
        .select(it.name, it.description, it.variant_of)
        .where(it.disabled == 0)
        .where(it.include_item_in_manufacturing == 1)
        .where(it.has_variants == 0)
        .where(it.variant_of.isnotnull())
        .orderby(it.variant_of)
        .orderby(it.name)
    )
    if filters.get("template"):
        query = query.where(it.variant_of == filters["template"])
    return query.run(as_dict=True)
