# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from rigpl_erpnext.manufacturing_rigpl.utils.manufacturing_utils import (
    get_bom_template_from_item,
)


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
    data = []
    it_conditions, params = get_conditions(filters)
    query = f"""SELECT it.name, it.description, it.variant_of FROM `tabItem` it 
	WHERE it.disabled = 0 AND it.include_item_in_manufacturing = 1 AND it.has_variants = 0 
	AND it.variant_of IS NOT NULL {it_conditions}
	ORDER BY it.variant_of, it.name"""
    it_dict = frappe.db.sql(query, params, as_dict=1)
    for d in it_dict:
        it_doc = frappe.get_doc("Item", d.name)
        bt_name = get_bom_template_from_item(it_doc, no_error=1)
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


def get_conditions(filters):
    it_conds = ""
    params = {}
    if filters.get("template"):
        it_conds += " AND it.variant_of = %(template)s"
        params["template"] = filters.get("template")

    return it_conds, params

