# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, add_months, getdate

def execute(filters=None):
    if not filters: 
        filters = {}

    if not filters.get("months"):
        frappe.throw("Please specify periods (e.g. 3,6,9)")

    columns = get_columns(filters)
    data = get_rol_data(filters)

    return columns, data

def get_columns(filters):
    period = filters.get("months").split(",")
    for p in period:
        if flt(p) == 0:
            frappe.throw("Only Numbers above ZERO are allowed in Period. Use Comma Separated Values Like 3,6,9")
        if flt(p) > 99:
            frappe.throw("Max period is 99 months")
            
    main_it_cols = [
        "Item:Link/Item:130", "ROL:Int:50", "ROQ:Int:50",
        "Is RM::60", "BM::60", "Brand::60", "Quality::60", "TT::130", "SPL::50",
        "D1 MM:Float:50", "W1 MM:Float:50", "L1 MM:Float:60",
        "D2 MM:Float:50", "L2 MM:Float:60"
    ]
    compare_cols = []
    for d in period:
        compare_cols += [
            f"SI-{d}:Int:70", f"#C-{d}:Int:70", f"Con-{d}:Int:70", f"STE-{d}:Int:70",
            f"SR-{d}:Int:70", f"PO-{d}:Int:70", f"#PO-{d}:Int:70", f"CROL-{d}:Int:80"
        ]
    desc_cols = ["Description::450", "Template:Link/Item:350"]
    return main_it_cols + compare_cols + desc_cols

def get_rol_data(filters):
    periods = [flt(p) for p in filters.get("months").split(",")]
    to_date = getdate(filters.get("to_date") or frappe.utils.nowdate())
    conditions, params = get_conditions(filters)
    
    # 1. Fetch Core Item Data
    items = frappe.db.sql(f"""
        SELECT it.name, it.description, it.variant_of, it.is_sales_item, it.is_purchase_item, it.valuation_rate,
               rol.warehouse_reorder_level as existing_rol, rol.warehouse_reorder_qty as existing_roq
        FROM `tabItem` it
        LEFT JOIN `tabItem Reorder` rol ON it.name = rol.parent AND rol.parentfield = 'reorder_levels'
        WHERE IFNULL(it.end_of_life, '2099-12-31') > CURDATE()
        {conditions}
    """, params, as_dict=1)
    
    if not items:
        return []

    item_codes = [d.name for d in items]
    
    # 2. Bulk Fetch Attributes
    attr_map = get_attribute_map(item_codes, filters.get("bm"))
    
    # 3. Bulk Fetch Calculation Data (Eliminates N*P*6 queries)
    # We fetch data for the longest period and slice it in Python memory
    max_period = max(periods)
    from_date = add_months(to_date, max_period * -1)
    
    bulk_metrics = get_bulk_metrics(items, from_date, to_date, periods)

    # 4. Assembly
    data = []
    for it in items:
        attrs = attr_map.get(it.name, {})
        row = [
            it.name, it.existing_rol, it.existing_roq,
            attrs.get("Is RM", "No"), attrs.get("Base Material", "-"),
            attrs.get("Brand", "-"), attrs.get("Quality", "-"),
            attrs.get("Tool Type", "-"), attrs.get("Special Treatment", "-"),
            flt(attrs.get("d1_mm")), flt(attrs.get("w1_mm")), flt(attrs.get("l1_mm")),
            flt(attrs.get("d2_mm")), flt(attrs.get("l2_mm"))
        ]
        
        for p in periods:
            m = bulk_metrics.get(it.name, {}).get(p, frappe._dict({
                "sold": 0, "customers": 0, "consumed": 0, "no_of_ste": 0,
                "sred": 0, "purchased": 0, "no_of_po": 0, "calc_rol": 0
            }))
            
            row += [
                m.sold or None, m.customers or None, m.consumed or None,
                m.no_of_ste or None, m.sred or None, m.purchased or None,
                m.no_of_po or None, m.calc_rol or None
            ]
            
        row += [it.description, it.variant_of]
        data.append(row)

    # Replicate original complex sorting in Python
    data.sort(key=lambda x: (
        str(x[4]), str(x[6]), str(x[7]), flt(x[9]), flt(x[10]), 
        flt(x[11]), flt(x[12]), flt(x[13]), str(x[5]), str(x[8])
    ))
    
    return data

def get_attribute_map(item_codes, bm_filter):
    if not item_codes: return {}
    quality_attr = f"{bm_filter} Quality" if bm_filter else "Quality"
    attrs_to_fetch = ["Is RM", "Base Material", "Brand", "Tool Type", "Special Treatment", "d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm", quality_attr]
    
    raw_attrs = frappe.get_all("Item Variant Attribute",
        filters={"parent": ["in", item_codes], "attribute": ["in", attrs_to_fetch]},
        fields=["parent", "attribute", "attribute_value"]
    )
    
    res = {}
    for a in raw_attrs:
        if a.parent not in res: res[a.parent] = {}
        # Normalize the Dynamic Quality attribute to a fixed key for the report
        key = "Quality" if a.attribute == quality_attr else a.attribute
        res[a.parent][key] = a.attribute_value
    return res

def get_bulk_metrics(items, from_date, to_date, periods):
    # This replaces the get_rol_for_item logic by pre-calculating everything
    # in optimized batch queries.
    item_codes = [d.name for d in items]
    res = {ic: {p: frappe._dict({
        "sold": 0, "customers": 0, "consumed": 0, "no_of_ste": 0,
        "sred": 0, "purchased": 0, "no_of_po": 0, "calc_rol": 0,
        "sold_avg": 0, "con_avg": 0, "po_avg": 0,
        "pos_tracker": set() # Accurate distinct count tracking
    }) for p in periods} for ic in item_codes}

    # Helper: Find which periods a date falls into
    sorted_periods = sorted(periods)
    period_start_dates = {p: add_months(to_date, p * -1) for p in periods}

    # 1. SLE Based (Sold & Purchased)
    sle_data = frappe.db.sql("""
        SELECT item_code, posting_date, actual_qty, voucher_type, voucher_no
        FROM `tabStock Ledger Entry`
        WHERE is_cancelled = "No" AND item_code IN %s AND posting_date >= %s AND posting_date < %s
        AND voucher_type IN ('Delivery Note', 'Sales Invoice', 'Purchase Receipt', 'Purchase Invoice')
    """, (tuple(item_codes), from_date, to_date), as_dict=1)

    for d in sle_data:
        for p in periods:
            if d.posting_date >= period_start_dates[p]:
                m = res[d.item_code][p]
                if d.voucher_type in ('Delivery Note', 'Sales Invoice'):
                    m.sold += (flt(d.actual_qty) * -1)
                else:
                    m.purchased += flt(d.actual_qty)
                    m.pos_tracker.add(d.voucher_no) # Capture unique transaction name

    # 2. Consumption (Stock Entry)
    ste_data = frappe.db.sql("""
        SELECT sted.item_code, ste.posting_date, sted.qty
        FROM `tabStock Entry Detail` sted
        INNER JOIN `tabStock Entry` ste ON sted.parent = ste.name
        WHERE ste.docstatus = 1 AND sted.s_warehouse IS NOT NULL 
        AND (sted.t_warehouse IS NULL OR sted.t_warehouse = "")
        AND sted.item_code IN %s AND ste.posting_date >= %s AND ste.posting_date < %s
    """, (tuple(item_codes), from_date, to_date), as_dict=1)

    for d in ste_data:
        for p in periods:
            if d.posting_date >= period_start_dates[p]:
                m = res[d.item_code][p]
                m.consumed += flt(d.qty)
                m.no_of_ste += 1

    # 3. Selling Based (Customers & SO Count)
    so_data = frappe.db.sql("""
        SELECT sod.item_code, so.transaction_date, so.customer, so.name
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` sod ON sod.parent = so.name
        WHERE so.docstatus = 1 AND sod.item_code IN %s AND so.transaction_date >= %s AND so.transaction_date < %s
    """, (tuple(item_codes), from_date, to_date), as_dict=1)

    # We need sets to count DISTINCT in memory
    so_tracker = {ic: {p: {'customers': set(), 'sos': set()} for p in periods} for ic in item_codes}
    for d in so_data:
        for p in periods:
            if d.transaction_date >= period_start_dates[p]:
                so_tracker[d.item_code][p]['customers'].add(d.customer)
                so_tracker[d.item_code][p]['sos'].add(d.name)

    # 4. Stock Reconciliation
    sr_data = frappe.db.sql("""
        SELECT srd.item_code, sr.posting_date, (srd.current_qty - srd.qty) as diff
        FROM `tabStock Reconciliation Item` srd
        INNER JOIN `tabStock Reconciliation` sr ON srd.parent = sr.name
        WHERE sr.docstatus = 1 AND srd.item_code IN %s AND sr.posting_date >= %s AND sr.posting_date < %s
    """, (tuple(item_codes), from_date, to_date), as_dict=1)
    
    for d in sr_data:
        for p in periods:
            if d.posting_date >= period_start_dates[p]:
                res[d.item_code][p].sred += flt(d.diff)

    # 5. Final Calculation logic (Replicating get_rol_for_item decision tree)
    # Use passed items to avoid extra DB query
    item_meta = {i.name: i for i in items}

    for ic in item_codes:
        for p in periods:
            m = res[ic][p]
            m.customers = len(so_tracker[ic][p]['customers'])
            m.no_of_po = len(m.pos_tracker) # Exact distinct count
            
            # Averages
            m.sold_avg = m.sold / p
            m.po_avg = m.purchased / p
            if m.no_of_ste > 2:
                m.con_avg = m.consumed / p
            else:
                m.con_avg = m.consumed / p / 2

            # Decision Logic
            is_sale = item_meta.get(ic, frappe._dict()).is_sales_item
            if is_sale:
                if m.customers > 2:
                    m.calc_rol = m.con_avg + m.sold_avg
                elif m.customers == 2:
                    m.calc_rol = m.con_avg + (m.sold_avg / 2)
                else:
                    m.calc_rol = m.con_avg
            else:
                if m.no_of_po >= m.no_of_ste:
                    m.calc_rol = m.po_avg + m.sold_avg
                else:
                    m.calc_rol = m.con_avg + m.sold_avg
            
            m.calc_rol = flt(m.calc_rol, 0)
            
    return res

def get_conditions(filters):
    conditions = ""
    params = {}
    
    attr_filters = {
        "rm": "Is RM", "bm": "Base Material", "series": "Series", 
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
