from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    if not filters:
        filters = {}
    
    # 1. Targeted Fetch - Templates/Items matching conditions
    conditions, params = get_conditions(filters)
    templates = get_templates(conditions, params)
    
    if not templates:
        return [], []

    # 2. Dynamic Column Construction
    columns, attributes, att_details = get_columns(templates)
    
    # 3. Optimized Data Assembly
    data = get_items(conditions, params, attributes, att_details)

    return columns, data


def get_columns(templates):
    columns = [_("Item") + ":Link/Item:130"]
    
    # Unique attributes across all relevant templates
    variant_ofs = [d.variant_of for d in templates]
    attributes = frappe.db.sql_list("""
        SELECT DISTINCT(iva.attribute)
        FROM `tabItem Variant Attribute` iva
        WHERE iva.parent IN %s
        ORDER BY iva.idx
    """, (tuple(variant_ofs),))

    att_details = []
    if attributes:
        # Fetch metadata for attributes in bulk
        attr_meta = frappe.get_all("Item Attribute",
            filters={"name": ["in", attributes]},
            fields=["name", "numeric_values", "hidden"])
        attr_meta_map = {m.name: m for m in attr_meta}

        # Fetch field names for dynamic labels
        field_names = frappe.db.sql("""
            SELECT attribute, MAX(field_name) as field_name 
            FROM `tabItem Variant Attribute` 
            WHERE attribute IN %s AND parent IN %s
            GROUP BY attribute
        """, (tuple(attributes), tuple(variant_ofs)), as_dict=1)
        field_name_map = {f.attribute: f.field_name for f in field_names}

        for attr_name in attributes:
            meta = attr_meta_map.get(attr_name, frappe._dict({"numeric_values": 0, "hidden": 0}))
            
            # Label logic replication
            label = attr_name
            sname = field_name_map.get(attr_name, "")
            if meta.hidden == 1:
                n_row = attr_name.split('_', 1)[1] if '_' in attr_name else attr_name
                label = sname.split('(', 1)[0] + "(" + n_row + ")" if sname else attr_name
            elif meta.numeric_values == 1:
                n_row = attr_name.split('_', 1)[1] if '_' in attr_name else attr_name
                label = sname.split('(', 1)[0] + "(" + n_row + ")" if (sname and '(' in sname) else attr_name
            else: # For non-numeric, non-hidden, use attribute name as label
                label = sname if sname else attr_name
            
            # Width/Type calculation
            width = 80 # Default
            if meta.numeric_values == 0:
                max_len = frappe.db.sql_list("""SELECT MAX(CHAR_LENGTH(attribute_value)) FROM `tabItem Attribute Value` WHERE parent = %s""", (attr_name,))
                if max_len and max_len[0]:
                    width = min(40, max_len[0]) * 10
            
            format_dict = {
                "name": attr_name,
                "label": label,
                "numeric_values": meta.numeric_values,
                "col_def": f"{label}{':Float' if meta.numeric_values else ''}:{width}"
            }
            att_details.append(format_dict)
            columns.append(format_dict["col_def"])

    # Appending Standard Static Columns
    static_cols = [
        (_("Lead Time"), "Int", 40), (_("Pack Size"), "Int", 40),
        (_("Selling MoV"), "Int", 40), (_("Purchase MoQ"), "Int", 40),
        (_("Is PL"), "Data", 40), (_("TOD"), "Data", 40), (_("ROL"), "Int", 40),
        (_("Template or Variant Of"), "Link/Item", 300),
        (_("Def Warehouse"), "Data", 50), (_("Def PL"), "Data", 50),
        (_("Description"), "Data", 400), (_("EOL"), "Date", 80),
        (_("Created By"), "Data", 150), (_("Creation"), "Date", 150)
    ]
    for label, type, width in static_cols:
        columns.append(f"{label}:{type}:{width}")

    return columns, attributes, att_details

def get_templates(conditions_it, params):
    # Determine the "Variant Of" templates that meet core filters
    query = f"""
        SELECT DISTINCT(it.variant_of)
        FROM `tabItem` it
        WHERE 1=1 {conditions_it}
    """
    templates = frappe.db.sql(query, params, as_dict=1)
    if not templates:
        frappe.throw("No Templates found matching the current criteria")
    return templates

def get_items(conditions_it, params, attributes, att_details):
    # Step 1: Fetch Base Items and common linked data (avoid EAV joins)
    # Join reorder/default for basic 1:1 mapping
    query = f"""
        SELECT 
            it.name, it.lead_time_days, it.pack_size, it.selling_mov, it.min_order_qty,
            IFNULL(it.pl_item, "-") as pl_item, IFNULL(it.stock_maintained, "-") as stock_maintained,
            ro.warehouse_reorder_level as rol, it.variant_of, 
            IFNULL(def.default_warehouse, "X") as default_warehouse,
            IFNULL(def.default_price_list, 'X') as default_price_list,
            it.description, IFNULL(it.end_of_life, '2099-12-31') as eol,
            it.owner, it.creation
        FROM `tabItem` it
        LEFT JOIN `tabItem Reorder` ro ON it.name = ro.parent
        LEFT JOIN `tabItem Default` def ON it.name = def.parent
        WHERE 1=1 {conditions_it}
        ORDER BY it.name
    """
    items = frappe.db.sql(query, params, as_dict=1)
    if not items:
        return []

    item_names = [d.name for d in items]

    # Step 2: Bulk Fetch all Attributes for the found items
    # One query instead of dozens of LEFT JOINs
    attr_data = frappe.get_all("Item Variant Attribute",
        filters={"parent": ["in", item_names], "attribute": ["in", attributes]},
        fields=["parent", "attribute", "attribute_value"],
        order_by="idx") # Maintain internal idx for sorting consistency if possible
    
    attr_map = {}
    for a in attr_data:
        if a.parent not in attr_map:
            attr_map[a.parent] = {}
        attr_map[a.parent][a.attribute] = a.attribute_value

    # Step 3: Assembly with Python-side Sorting
    data = []
    for d in items:
        item_attrs = attr_map.get(d.name, {})
        row = [d.name]
        
        # Attribute Columns
        for att in att_details:
            val = item_attrs.get(att["name"])
            if val is None: val = "-"
            row.append(flt(val) if att["numeric_values"] else val)
            
        # Static Columns
        row += [
            d.lead_time_days or None, d.pack_size or None, d.selling_mov or None,
            d.min_order_qty or None, d.pl_item, d.stock_maintained, d.rol or None,
            d.variant_of, d.default_warehouse, d.default_price_list,
            d.description, d.eol, d.owner, d.creation
        ]
        data.append(row)

    # Python Sorting to replicate ORDER BY attribute_value logic
    # The original order was: attr1, attr2..., item_name
    def sort_key(row_data):
        key = []
        for i in range(len(attributes)): 
            val = row_data[i + 1] 
            is_numeric = att_details[i]["numeric_values"]
            
            if val == "-": 
                key.append(float('inf') if is_numeric else "zzz")
            else:
                key.append(flt(val) if is_numeric else str(val))
                
        key.append(row_data[0]) 
        return tuple(key)

    data.sort(key=sort_key)
    return data

def get_conditions(filters):
    conditions = ""
    params = {}
    
    attribute_filters = {
        "rm": "Is RM",
        "bm": "Base Material",
        "series": "Series",
        "quality": "Quality", # Dynamic name handled in loop
        "spl": "Special Treatment",
        "purpose": "Purpose",
        "type": "Type Selector",
        "mtm": "Material to Machine",
        "tt": "Tool Type"
    }

    if filters.get("eol"):
        conditions += " AND IFNULL(it.end_of_life, '2099-12-31') > %(eol)s"
        params["eol"] = filters.get("eol")

    for f_key, attr_name in attribute_filters.items():
        if filters.get(f_key):
            actual_attr_name = attr_name
            if f_key == "quality": 
                if filters.get("bm"):
                    actual_attr_name = f"{filters.get('bm')} Quality"
                else:
                    continue # Skip quality filter if bm is missing
            
            p_val = f"f_{f_key}"
            params[f"{p_val}_attr"] = actual_attr_name
            params[f"{p_val}_val"] = filters.get(f_key)
            
            conditions += f""" AND EXISTS (
                SELECT 1 FROM `tabItem Variant Attribute` 
                WHERE parent = it.name AND attribute = %({p_val}_attr)s 
                AND attribute_value = %({p_val}_val)s
            )"""

    if filters.get("tt"):
        pass # Handled in attribute_filters above
    else:
        user_roles = frappe.get_roles(frappe.session.user)
        if "System Manager" not in user_roles:
            frappe.throw("Please Select Tool Type")

    if filters.get("show_in_website") == 1:
        conditions += " AND it.show_variant_in_website = 1"

    if filters.get("item"):
        conditions += " AND it.name = %(item)s"
        params["item"] = filters.get("item")

    if filters.get("variant_of"):
        conditions += " AND it.variant_of = %(variant_of)s"
        params["variant_of"] = filters.get("variant_of")

    return conditions, params
