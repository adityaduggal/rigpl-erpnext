# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters:
        filters = {}
    
    # 1. Targeted Fetch - BOM Templates matching conditions
    conditions, params = get_conditions(filters)
    bt_data = get_base_templates(conditions, params)
    
    if not bt_data:
        return [], []

    # 2. Dynamic Column Construction
    columns, attr_details, attributes = get_columns(bt_data)
    
    # 3. Optimized Data Assembly
    data = get_report_data(bt_data, attributes, attr_details)

    return columns, data

def get_columns(bt_data):
    bt_names = [d.name for d in bt_data]
    
    # Unique attributes across all relevant templates
    attributes = frappe.db.sql_list("""
        SELECT DISTINCT(ivr.attribute)
        FROM `tabItem Variant Restrictions` ivr
        WHERE ivr.parent IN %s AND ivr.parenttype = 'BOM Template RIGPL' AND ivr.parentfield = 'fg_restrictions'
        AND ivr.is_numeric = 0
        ORDER BY ivr.attribute
    """, (tuple(bt_names),))

    columns = ["BT Name:Link/BOM Template RIGPL:100"]
    attr_details = []

    if attributes:
        # Fetch widths for attributes in bulk
        widths = frappe.db.sql("""
            SELECT parent as attribute, MAX(CHAR_LENGTH(attribute_value)) as max_len
            FROM `tabItem Attribute Value`
            WHERE parent IN %s
            GROUP BY parent
        """, (tuple(attributes),), as_dict=1)
        width_map = {w.attribute: (w.max_len or 6) for w in widths}

        for attr_name in attributes:
            max_len = width_map.get(attr_name, 6)
            width = min(40, max_len) * 8
            columns.append(f"{attr_name}::{width}")
            attr_details.append({"name": attr_name})

    columns += [
        "# of Ops:Int:50", "Routing:Link/Routing:150", 
        "Remarks::400", "Formula::400"
    ]

    return columns, attr_details, attributes

def get_base_templates(conditions, params):
    # Fetch core data for BOM Templates
    query = f"""
        SELECT 
            bt.name, bt.routing, bt.remarks, bt.formula
        FROM `tabBOM Template RIGPL` bt
        WHERE bt.docstatus = 0 {conditions}
    """
    return frappe.db.sql(query, params, as_dict=1)

def get_report_data(bt_data, attributes, attr_details):
    bt_names = [d.name for d in bt_data]
    
    # 1. Bulk Fetch all Restrictions
    rest_data = frappe.get_all("Item Variant Restrictions",
        filters={"parent": ["in", bt_names], "parenttype": "BOM Template RIGPL", "attribute": ["in", [a["name"] for a in attr_details]]},
        fields=["parent", "attribute", "allowed_values"]
    )
    
    rest_map = {}
    for r in rest_data:
        if r.parent not in rest_map:
            rest_map[r.parent] = {}
        rest_map[r.parent][r.attribute] = r.allowed_values

    # 2. Bulk Fetch Operation Counts (O(1) mapping)
    ops_data = frappe.db.sql("""
        SELECT parent, COUNT(name) as op_count
        FROM `tabBOM Operation`
        WHERE parenttype = 'BOM Template RIGPL' AND parent IN %s
        GROUP BY parent
    """, (tuple(bt_names),), as_dict=1)
    
    ops_map = {d.parent: d.op_count for d in ops_data}

    # 3. Assembly
    data = []
    for bt in bt_data:
        bt_rests = rest_map.get(bt.name, {})
        op_count = ops_map.get(bt.name, 0)
        
        row = [bt.name]
        
        # Restriction Columns
        for attr in attr_details:
            row.append(bt_rests.get(attr["name"], "-"))
            
        # Static Columns
        row += [op_count, bt.routing, bt.remarks, bt.formula]
        data.append(row)

    # Python Sorting to match original ORDER BY attribute_value logic
    data.sort(key=lambda r: (tuple(str(r[i+1]) for i in range(len(attr_details))), r[0]))
    return data

def get_conditions(filters):
    conditions = ""
    params = {}
    
    attr_filters = {
        "rm": "Is RM",
        "bm": "Base Material",
        "tt": "Tool Type",
        "spl": "Special Treatment",
        "series": "Series",
        "purpose": "Purpose",
        "type": "Type Selector",
        "mtm": "Material to Machine"
    }

    if filters.get("quality"):
        if filters.get("bm"):
            # Dynamic quality attribute name
            attr_filters["quality"] = f"{filters.get('bm')} Quality"
        else:
            frappe.throw("Select Base Material before Selecting Quality")

    # Secure filtering using EXISTS
    for f_key, attr_name in attr_filters.items():
        if filters.get(f_key):
            p_val = f"f_{f_key}"
            params[f"{p_val}_attr"] = attr_name
            params[f"{p_val}_val"] = filters.get(f_key)
            
            conditions += f""" AND EXISTS (
                SELECT 1 FROM `tabItem Variant Restrictions` 
                WHERE parent = bt.name AND parenttype = 'BOM Template RIGPL' AND parentfield = 'fg_restrictions'
                AND attribute = %({p_val}_attr)s AND allowed_values = %({p_val}_val)s
            )"""

    return conditions, params
