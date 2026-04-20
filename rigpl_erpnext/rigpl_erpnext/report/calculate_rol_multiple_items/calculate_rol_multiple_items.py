# Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, getdate

def execute(filters=None):
    if not filters: 
        filters = {}

    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw("Please select both From and To dates.")

    columns = get_columns()
    data = get_sl_entries(filters)

    return columns, data

def get_columns():
    return [
        "Item:Link/Item:130", "ROL:Int:50", "SOLD:Int:50",
        "#Cust:Int:50", "CON:Int:50", "CON SR:Int:60", "SI Avg:Int:50",
        "CON Avg:Int:50", "TotA:Int:50", "Diff:Int:40", "# SO:Int:40",
        "BM::60", "Brand::60", "Quality::60", "TT::130", "SPL::50",
        "D1 MM:Float:50", "W1 MM:Float:50", "L1 MM:Float:60",
        "D2 MM:Float:50", "L2 MM:Float:60",
        "Description::450", "Template:Link/Item:150"
    ]

def get_sl_entries(filters):
    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    diff = (to_date - from_date).days or 1 # Avoid division by zero
    
    conditions, params = get_conditions(filters)
    
    # 1. Base Fetch: Items and ROL (Eliminates recursive joins)
    items = frappe.db.sql(f"""
        SELECT it.name, it.description, it.variant_of,
               rol.warehouse_reorder_level as existing_rol
        FROM `tabItem` it
        LEFT JOIN `tabItem Reorder` rol ON it.name = rol.parent AND rol.parentfield = 'reorder_levels'
        WHERE IFNULL(it.end_of_life, '2099-12-31') > CURDATE()
        {conditions}
    """, params, as_dict=1)

	# if len(items) > 1500:
	#         frappe.throw(f"Server overload possible due to {len(items)} rows of data, kindly reduce the lines by selecting filters")
	
    if not items:
        return []

    item_codes = [d.name for d in items]
    
    # 2. Bulk Fetch Attributes (O(1) Memory Map)
    attr_map = get_attribute_map(item_codes, filters.get("bm"))
    
    # 3. Bulk Fetch Metrics (Eliminates 6 subqueries per item)
    metrics = get_bulk_metrics(item_codes, from_date, to_date)
    
    # 4. Assembly
    data = []
    for it in items:
        attrs = attr_map.get(it.name, {})
        m = metrics.get(it.name, frappe._dict({
            "sold": 0, "customers": 0, "consumed": 0, "sr_diff": 0, "so_count": 0
        }))
        
        rol = flt(it.existing_rol)
        sold = flt(m.sold)
        cons = flt(m.consumed)
        sr = flt(m.sr_diff)
        
        # Calculation logic from original report
        si_avg = (sold / diff) * 30 if sold != 0 else None
        con_avg = ((cons + sr) / diff) * 30 if (cons != 0 or sr != 0) else None
        
        tot_avg = None
        if si_avg is not None:
            tot_avg = si_avg + (con_avg or 0)
        elif con_avg is not None:
            tot_avg = con_avg
            
        change = None
        if rol != 0:
            change = (tot_avg or 0) - rol
        elif tot_avg is not None:
            change = tot_avg
            
        data.append([
            it.name, (rol if rol != 0 else None), (sold if sold != 0 else None),
            (m.customers if m.customers != 0 else None), (cons if cons != 0 else None),
            (sr if sr != 0 else None), si_avg, con_avg, tot_avg, change,
            (m.so_count if m.so_count != 0 else None),
            attrs.get("Base Material", "-"), attrs.get("Brand", "-"),
            attrs.get("Quality", "-"), attrs.get("Tool Type", "-"),
            attrs.get("Special Treatment", "-"),
            flt(attrs.get("d1_mm")), flt(attrs.get("w1_mm")), flt(attrs.get("l1_mm")),
            flt(attrs.get("d2_mm")), flt(attrs.get("l2_mm")),
            it.description, it.variant_of
        ])

    # Standard complex sort order preserved
    data.sort(key=lambda x: (
        str(x[11]), str(x[13]), str(x[14]), flt(x[16]), flt(x[17]),
        flt(x[19]), flt(x[20])
    ))
    
    return data

def get_attribute_map(item_codes, bm_filter):
    if not item_codes: return {}
    quality_attr = f"{bm_filter} Quality" if bm_filter else "Quality"
    attrs_to_fetch = ["Base Material", "Brand", "Tool Type", "Special Treatment", "d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm", quality_attr]
    
    raw_attrs = frappe.get_all("Item Variant Attribute",
        filters={"parent": ["in", item_codes], "attribute": ["in", attrs_to_fetch]},
        fields=["parent", "attribute", "attribute_value"]
    )
    
    res = {}
    for a in raw_attrs:
        if a.parent not in res: res[a.parent] = {}
        key = "Quality" if a.attribute == quality_attr else a.attribute
        res[a.parent][key] = a.attribute_value
    return res

def get_bulk_metrics(item_codes, from_date, to_date):
    res = {ic: frappe._dict({
        "sold": 0, "customers": 0, "consumed": 0, "sr_diff": 0, "so_count": 0
    }) for ic in item_codes}

    # 1. Sales metrics (SLE)
    sle_data = frappe.db.sql("""
        SELECT item_code, SUM(actual_qty) * -1 as sold
        FROM `tabStock Ledger Entry` 
        WHERE voucher_type IN ('Delivery Note', 'Sales Invoice') AND is_cancelled = "No"
        AND item_code IN %s AND posting_date >= %s AND posting_date <= %s
        GROUP BY item_code
    """, (tuple(item_codes), from_date, to_date), as_dict=1)
    for d in sle_data:
        res[d.item_code].sold = d.sold

    # 2. Customer & SO Counts
    so_data = frappe.db.sql("""
        SELECT sod.item_code, COUNT(DISTINCT(so.customer)) as customers, COUNT(DISTINCT(so.name)) as so_count
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` sod ON sod.parent = so.name
        WHERE so.docstatus = 1 AND sod.item_code IN %s AND so.transaction_date >= %s AND so.transaction_date <= %s
        GROUP BY sod.item_code
    """, (tuple(item_codes), from_date, to_date), as_dict=1)
    for d in so_data:
        res[d.item_code].customers = d.customers
        res[d.item_code].so_count = d.so_count

    # 3. Consumption (Stock Entry)
    ste_data = frappe.db.sql("""
        SELECT sted.item_code, SUM(sted.qty) as consumed
        FROM `tabStock Entry Detail` sted
        INNER JOIN `tabStock Entry` ste ON sted.parent = ste.name
        WHERE ste.docstatus = 1 AND sted.s_warehouse IS NOT NULL
        AND (sted.t_warehouse IS NULL OR sted.t_warehouse = "")
        AND sted.item_code IN %s AND ste.posting_date >= %s AND ste.posting_date <= %s
        GROUP BY sted.item_code
    """, (tuple(item_codes), from_date, to_date), as_dict=1)
    for d in ste_data:
        res[d.item_code].consumed = d.consumed

    # 4. Stock Reconciliation
    sr_data = frappe.db.sql("""
        SELECT srd.item_code, SUM(srd.current_qty - srd.qty) as sr_diff
        FROM `tabStock Reconciliation Item` srd
        INNER JOIN `tabStock Reconciliation` sr ON srd.parent = sr.name
        WHERE sr.docstatus = 1 AND srd.qty != srd.current_qty
        AND srd.current_valuation_rate = srd.valuation_rate
        AND sr.posting_time != '23:59:59'
        AND srd.item_code IN %s AND sr.posting_date >= %s AND sr.posting_date <= %s
        GROUP BY srd.item_code
    """, (tuple(item_codes), from_date, to_date), as_dict=1)
    for d in sr_data:
        res[d.item_code].sr_diff = d.sr_diff

    return res

def get_conditions(filters):
    conditions = ""
    params = {}
    
    attr_filters = {
        "rm": "Is RM", "bm": "Base Material", "brand": "Brand", 
        "quality": "Quality", "spl": "Special Treatment", "purpose": "Purpose",
        "type": "Type Selector", "mtm": "Material to Machine", "tt": "Tool Type"
    }

    for f_key, attr_name in attr_filters.items():
        if filters.get(f_key):
            actual_attr = attr_name
            if f_key == "quality" and filters.get("bm"):
                actual_attr = f"{filters.get('bm')} Quality"
            
            p_val = f"f_{f_key}"
            params[f"{p_val}_attr"] = actual_attr
            params[f"{p_val}_val"] = filters.get(f_key)
            conditions += f" AND EXISTS (SELECT 1 FROM `tabItem Variant Attribute` WHERE parent = it.name AND attribute = %({p_val}_attr)s AND attribute_value = %({p_val}_val)s)"

    if filters.get("item"):
        conditions += " AND it.name = %(item)s"
        params["item"] = filters.get("item")

    return conditions, params