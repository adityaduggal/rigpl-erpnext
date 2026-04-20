# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        filters = {}
    if not filters.get("bm"):
        frappe.throw("Base Material (BM) filter is mandatory")

    columns = get_columns()
    data = get_items(filters)

    return columns, data

def get_columns():
    return [
        "Item:Link/Item:120", 
        "Series::60", "BM::60", "Brand::40", "Qual::50", "SPL::50", "TT::100",
        "MTM::60", "Purpose::100", "Type::60",
        "D1:Float:50", "W1:Float:50", "L1:Float:60",
        "D2:Float:50", "L2:Float:60", "Zn:Int:30",
        "Description::400", "Ready Stock:Int:60", "WIP1:Int:60", "WIP2:Int:60"
    ]

def get_items(filters):
    conditions, params = get_conditions(filters)
    bm_val = filters.get("bm")
    quality_attr = f"{bm_val} Quality"

    # Step 1: Targeted Fetch - Item Master data and Stock Aggregation
    # We only join tabItem and tabBin here.
    query = f"""
        SELECT 
            it.name, it.description,
            SUM(IF(bn.warehouse IN ('BGH655 - RIGPL', 'DEL20A - RIGPL', 'Dead Stock - RIGPL'), bn.actual_qty, 0)) as ready_stock,
            SUM(IF(bn.warehouse NOT IN ('BGH655 - RIGPL', 'DEL20A - RIGPL', 'REJ-DEL20A - RIGPL', 'Dead Stock - RIGPL'), 
                (bn.actual_qty + bn.ordered_qty + bn.planned_qty), 0)) as wip1,
            SUM(IF(bn.warehouse IN ('BGH655 - RIGPL', 'DEL20A - RIGPL'), (bn.ordered_qty + bn.planned_qty), 0)) as wip2
        FROM `tabItem` it
        INNER JOIN `tabBin` bn ON it.name = bn.item_code
        WHERE IFNULL(it.end_of_life, '2099-12-31') > CURDATE()
        {conditions}
        GROUP BY it.name
    """
    items = frappe.db.sql(query, params, as_dict=1)
    
    if not items:
        return []

    item_codes = [d.name for d in items]

    # Step 2: Bulk Fetch Attributes
    # Fetch all relevant attributes for the found items in ONE query
    attributes_to_fetch = [
        'Is RM', 'Base Material', 'Brand', quality_attr, 'Tool Type', 
        'Special Treatment', 'd1_mm', 'w1_mm', 'l1_mm', 'd2_mm', 'l2_mm', 
        'Number of Flutes Zn', 'Series', 'Material to Machine', 
        'Type Selector', 'Purpose'
    ]
    
    attr_data = frappe.get_all("Item Variant Attribute",
        filters={
            "parent": ["in", item_codes],
            "attribute": ["in", attributes_to_fetch]
        },
        fields=["parent", "attribute", "attribute_value"]
    )

    # Map attributes for O(1) lookup
    attr_map = {}
    for a in attr_data:
        if a.parent not in attr_map:
            attr_map[a.parent] = {}
        attr_map[a.parent][a.attribute] = a.attribute_value

    # Step 3: Python-side Filtering and Assembly
    data = []
    for d in items:
        attrs = attr_map.get(d.name, {})
        
        # Strictly replicates original SQL: rm.attribute_value IS NULL and bm.attribute_value IS NOT NULL
        if 'Is RM' in attrs or 'Base Material' not in attrs:
            continue
            
        def get_val(attr, default="-"):
            return attrs.get(attr, default)

        def get_num(attr):
            val = attrs.get(attr)
            return flt(val) if val else 0

        row = [
            d.name,
            get_val('Series'), get_val('Base Material'), get_val('Brand'),
            get_val(quality_attr), get_val('Special Treatment'), get_val('Tool Type'),
            get_val('Material to Machine'), get_val('Purpose'), get_val('Type Selector'),
            get_num('d1_mm'), get_num('w1_mm'), get_num('l1_mm'),
            get_num('d2_mm'), get_num('l2_mm'), int(get_num('Number of Flutes Zn')),
            d.description, d.ready_stock, d.wip1, d.wip2
        ]
        data.append(row)

    # Sort data in Python to replicate the complex SQL ORDER BY
    # Sort order: is_rm (None in this view), brand, spl, tt, d1, w1, l1, d2, l2
    data.sort(key=lambda x: (
        x[3], # Brand (index 3)
        x[5], # SPL (index 5)
        x[6], # TT (index 6)
        x[10], # D1
        x[11], # W1
        x[12], # L1
        x[13], # D2
        x[14]  # L2
    ))

    return data

def get_conditions(filters):
    conditions = ""
    params = {}
    
    if filters.get("item"):
        conditions += " AND it.name = %(item)s"
        params["item"] = filters.get("item")

    # Efficiently filter by attributes using EXISTS instead of multiple JOINs
    attribute_filters = {
        "bm": "Base Material",
        "series": "Series",
        "tt": "Tool Type",
        "brand": "Brand",
        "quality": f"{filters.get('bm')} Quality",
        "spl": "Special Treatment"
    }

    for filter_key, attr_name in attribute_filters.items():
        if filters.get(filter_key):
            param_name = f"filter_{filter_key}"
            conditions += f""" 
                AND EXISTS (
                    SELECT 1 FROM `tabItem Variant Attribute` 
                    WHERE parent = it.name AND attribute = %({param_name}_attr)s 
                    AND attribute_value = %({param_name}_val)s
                )
            """
            params[f"{param_name}_attr"] = attr_name
            params[f"{param_name}_val"] = filters.get(filter_key)
    
    return conditions, params
