# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters:
        filters = {}
        
    validate_filters(filters)
    columns = get_columns(filters)
    data = get_items(filters)
    return columns, data

def validate_filters(filters):
    if filters.get("restrictions") == 1:
        if not filters.get("template") == 1:
            frappe.throw("Restrictions Table can only be shown for Templates")

def get_columns(filters):
    if filters.get("restrictions") == 1:
        return [
            "Item:Link/Item:250", "Rest ID::100", "Rest IDX::50", "Attribute Name::150", 
            "Allowed Values::150", "Is Numeric::50", "Rule::250"
        ]
    else:
        return [
            "Item:Link/Item:250", "Variant Of:Link/Item:250", "Att ID::100", "IDX::50",
            "Attribute Name::100", "In Desc::50", "Prefix::50","Field Name::80", 
            "Suffix::50", "Attribute Value::150", "Is Numeric:Int:50", "From Range:Float:80",
            "Increment:Float:80","To Range:Float:80"
        ]

def get_items(filters):
    conditions, params = get_conditions(filters)
    
    if filters.get("restrictions") == 1:
        query = f"""
            SELECT
                it.name, ivr.name, ivr.idx, ivr.attribute, ivr.allowed_values,
                ivr.is_numeric, ivr.rule
            FROM `tabItem` it
            INNER JOIN `tabItem Variant Restrictions` ivr ON ivr.parent = it.name
            WHERE 1=1 {conditions}
            ORDER BY it.name, ivr.idx
        """
        return frappe.db.sql(query, params, as_list=1)
    else:
        query = f"""
            SELECT
                it.name, it.variant_of, iva.name, iva.idx, iva.attribute, iva.use_in_description,
                iva.prefix, iva.field_name, iva.suffix, iva.attribute_value, iva.numeric_values,
                iva.from_range, iva.increment, iva.to_range
            FROM `tabItem` it
            INNER JOIN `tabItem Variant Attribute` iva ON iva.parent = it.name
            WHERE 1=1 {conditions}
            ORDER BY it.name, iva.idx
        """
        return frappe.db.sql(query, params, as_list=1)

def get_conditions(filters):
    conditions = ""
    params = {}

    if filters.get("eol"):
        conditions += " AND IFNULL(it.end_of_life, '2099-12-31') > %(eol)s"
        params["eol"] = filters.get("eol")
            
    if filters.get("show_in_website") == 1:
        conditions += " AND it.show_in_website = %(show_in_website)s"
        params["show_in_website"] = filters.get("show_in_website")
    
    if filters.get("item"):
        conditions += " AND it.name = %(item)s "
        params["item"] = filters.get("item")
    
    if filters.get("variant_of"):
        conditions += " AND it.variant_of LIKE %(variant_of)s "
        params["variant_of"] = f"%{filters.get('variant_of')}%"
    
    if filters.get("template") == 1:
        conditions += " AND it.has_variants = 1"
    else:
        conditions += " AND it.has_variants = 0"
        
    return conditions, params