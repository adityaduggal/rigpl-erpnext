# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        filters = {}

    # Bulk fetch warehouses for dynamic columns and calculation
    wh_dict = frappe.db.sql("""
        SELECT name, listing_serial, short_code, warehouse_type 
        FROM `tabWarehouse`
        WHERE disabled=0 AND is_group=0 AND listing_serial != 0 AND is_subcontracting_warehouse = 0
        ORDER BY listing_serial ASC
    """, as_dict=1)

    columns = get_columns(wh_dict)
    data = get_data(filters, wh_dict)
    return columns, data

def get_columns(wh_dict):
    # Same column structure as original, just grouped for readability
    columns = [
        "Item:Link/Item:120", 
        "RM::30", "Brand::50", "Series::50", "Qual::50", "SPL::50", "TT::60",
        "D1:Float:40", "W1:Float:40", "L1:Float:50", "D2:Float:40", "L2:Float:40", "Zn:Float:40",
        "CUT::120", "URG::120", "Total:Float:60", "RO:Int:40", "SO:Int:40", "PO:Int:40", "PL:Int:40", "PRD_RES:Int:40"
    ]

    # Dynamic warehouse columns
    for wh in wh_dict:
        if wh.listing_serial < 10:
            columns.append(f"{wh.short_code}:Float:50")
    
    columns.append("Description::400")
    
    for wh in wh_dict:
        if wh.listing_serial >= 10:
            columns.append(f"{wh.short_code}:Float:50")

    columns += ["JW:Int:30", "Pur:Int:30", "Sale:Int:30"]
    return columns

def get_data(filters, wh_dict):
    conditions, params = get_conditions(filters)
    
    # Step 1: Base Fetch (Item + Reorder)
    query = f"""
        SELECT 
            it.name, it.description, it.valuation_rate as vr, it.lead_time_days,
            it.is_job_work as jw, it.is_purchase_item as pur, it.is_sales_item as sale,
            IFNULL(ro.warehouse_reorder_level, 0) as rol
        FROM `tabItem` it
        LEFT JOIN `tabItem Reorder` ro ON it.name = ro.parent
        WHERE IFNULL(it.end_of_life, '2099-12-31') > CURDATE()
        {conditions}
    """
    items = frappe.db.sql(query, params, as_dict=1)
    
    if not items:
        return []

    item_codes = [d.name for d in items]

    # Step 2: Bulk Fetch Attributes
    raw_attr = [
        'Is RM', 'Base Material', 'Brand', 'Series', 'Quality', 'Tool Type', 
        'Special Treatment', 'd1_mm', 'w1_mm', 'l1_mm', 'd2_mm', 'l2_mm', 
        'Number of Flutes Zn'
    ]
    # Handle the '%s Quality' dynamic name from original logic if bm filter is present
    quality_attr = f"{filters.get('bm')} Quality" if filters.get('bm') else "Quality"
    
    attr_data = frappe.get_all("Item Variant Attribute",
        filters={"parent": ["in", item_codes]},
        fields=["parent", "attribute", "attribute_value"]
    )
    
    attr_map = {}
    for a in attr_data:
        if a.parent not in attr_map:
            attr_map[a.parent] = {}
        attr_map[a.parent][a.attribute] = a.attribute_value

    # Step 3: Bulk Fetch Bin Data (Eliminates N+1 loop)
    bin_data = frappe.db.sql("""
        SELECT bn.item_code, bn.reserved_qty as on_so, bn.actual_qty as actual, bn.warehouse,
               bn.ordered_qty as on_po, bn.planned_qty as plan, 
               bn.reserved_qty_for_production as prd, wh.is_subcontracting_warehouse as subcon,
               wh.short_code as scode, wh.warehouse_type
        FROM `tabBin` bn
        INNER JOIN `tabWarehouse` wh ON wh.name = bn.warehouse
        WHERE bn.item_code IN %s
    """, (tuple(item_codes),), as_dict=1)

    bin_map = {}
    for b in bin_data:
        if b.item_code not in bin_map:
            bin_map[b.item_code] = []
        bin_map[b.item_code].append(b)

    # Step 4: Assembly Loop
    actual_data = []
    for d in items:
        attrs = attr_map.get(d.name, {})
        bins = bin_map.get(d.name, [])

        # Attribute resolution
        is_rm = attrs.get('Is RM', '-')
        brand = attrs.get('Brand', '-')
        series = attrs.get('Series', '-')
        qual = attrs.get(quality_attr, '-')
        spl = attrs.get('Special Treatment', '-')
        tt = attrs.get('Tool Type', '-')
        d1 = flt(attrs.get('d1_mm'))
        w1 = flt(attrs.get('w1_mm'))
        l1 = flt(attrs.get('l1_mm'))
        d2 = flt(attrs.get('d2_mm'))
        l2 = flt(attrs.get('l2_mm'))
        zn = flt(attrs.get('Number of Flutes Zn'))

        # Stock calculation (Replaces get_wh_wise_qty logic)
        d.update({"on_so": 0, "on_po": 0, "plan": 0, "prd": 0, "total": 0, "stock": 0, "prd_qty": 0, "dead": 0})
        wh_stock = {}
        
        for b in bins:
            if b.subcon == 1:
                d["on_po"] += flt(b.actual)
            else:
                d["on_po"] += flt(b.on_po)
                d["on_so"] += flt(b.on_so)
                d["prd"] += flt(b.prd)
                d["plan"] += flt(b.plan)
                wh_stock[b.scode] = flt(b.actual)

            # Warehouse type specific totals (from original get_urgency)
            if str(is_rm) in ("1", "Yes", "True"): 
                 if b.warehouse_type in ["Raw Material", "Finished Stock"]:
                     d["stock"] += flt(b.actual)
                 elif b.warehouse_type == "Dead Stock":
                     d["dead"] += flt(b.actual)
            else:
                 if b.warehouse_type == "Finished Stock":
                     d["stock"] += flt(b.actual)
                 elif b.warehouse_type not in ["Finished Stock", "Recoverable Stock"]:
                     if b.warehouse_type == "Dead Stock":
                         d["dead"] += flt(b.actual)
                     else:
                         d["prd_qty"] += flt(b.actual)
        
        # Total across relevant warehouses
        for wh in wh_dict:
            if wh.warehouse_type != "Recoverable Stock":
                d["total"] += wh_stock.get(wh.short_code, 0)
        
        # Original logic: d["total"] += flt(d.on_po) + flt(d.plan) - flt(d.prd) - flt(d.on_so)
        d["total"] += flt(d.on_po) + flt(d.plan) - flt(d.prd) - flt(d.on_so)

        # Urgency Calculation (Ported from get_urgency)
        d = calculate_urgency(d)

        # Build Data Row
        row = [
            d.name, is_rm, brand, series, qual, spl, tt, d1, w1, l1, d2, l2, zn,
            d.get("cut_urg", ""), d.get("prd_urg", ""), d["total"] if d["total"] > 0 else None,
            d.rol if flt(d.rol) > 0 else None,
            d.on_so if d.on_so > 0 else None, d.on_po if d.on_po > 0 else None,
            d.plan if d.plan > 0 else None, d.prd if d.prd > 0 else None
        ]
        
        # Dynamic Wh Columns (Before Description)
        for wh in wh_dict:
            if wh.listing_serial < 10:
                val = wh_stock.get(wh.short_code, 0)
                row.append(val if val > 0 else None)
        
        row.append(d.description)
        
        # Dynamic Wh Columns (After Description)
        for wh in wh_dict:
            if wh.listing_serial >= 10:
                val = wh_stock.get(wh.short_code, 0)
                row.append(val if val > 0 else None)
        
        row += [d.jw if d.jw else None, d.pur if d.pur else None, d.sale if d.sale else None]
        actual_data.append(row)

    # Sort in Python logic (replicates original ORDER BY)
    # Original sort: rm.attr_val, brand.attr_val, spl.attr_val, tt.attr_val, d1, w1, l1, d2, l2
    actual_data.sort(key=lambda x: (str(x[1]), str(x[2]), str(x[5]), str(x[6]), flt(x[7]), flt(x[8]), flt(x[9]), flt(x[10]), flt(x[11])))
    
    return actual_data

def calculate_urgency(itd):
    ROL = flt(itd.get("rol"))
    SO = flt(itd.get("on_so"))
    PO = flt(itd.get("on_po"))
    PLAN = flt(itd.get("plan"))
    PRD_RES = flt(itd.get("prd"))
    VR = flt(itd.get("vr"))
    stock = flt(itd.get("stock"))
    prd_qty = flt(itd.get("prd_qty"))
    dead = flt(itd.get("dead"))
    
    total = stock + prd_qty + dead + PLAN + PO - PRD_RES
    
    # ROL adjustment based on Value Rate
    if 0 <= ROL * VR <= 1000:
        ROL = 5 * ROL
    elif 1000 < ROL * VR <= 2000:
        ROL = 2.5 * ROL
    elif 2000 < ROL * VR <= 5000:
        ROL = 1.5 * ROL

    # Cutting Urgency
    urg = ""
    if dead > 0:
        urg = "Dead Stock"
    elif total < SO:
        urg = "1C ORD" if SO > 0 else "1C For Production"
    elif total < SO + (0.3 * ROL): urg = "2C STK"
    elif total < SO + (0.6 * ROL): urg = "3C STK"
    elif total < SO + (1.0 * ROL): urg = "4C STK"
    elif total < SO + (1.4 * ROL): urg = "5C STK"
    elif total < SO + (1.8 * ROL): urg = "6C STK"
    elif total > (SO + 2.5 * ROL): urg = "7 Over" if ROL > 0 else ""
    
    if urg != "" and "Qty=" not in urg:
        c_qty = ((2 * ROL) + SO - total)
        urg = f"{urg} Qty= {int(c_qty)}"

    # Production Urgency
    prd = ""
    if dead > 0:
        prd = "Dead Stock"
    elif stock < SO:
        prd = "1P ORD" if SO > 0 else "1P for Production"
    elif stock < SO + ROL: prd = "2P STK"
    elif stock < SO + 1.2 * ROL: prd = "3P STK"
    elif stock < SO + 1.4 * ROL: prd = "4P STK"
    elif stock < SO + 1.6 * ROL: prd = "5P STK"
    elif stock < SO + 1.8 * ROL: prd = "6P STK"
    elif stock < SO + 2.0 * ROL: prd = "7P STK"
    elif stock > SO + 2.5 * ROL: prd = "9 OVER" if ROL > 0 else ""
    
    if prd != "" and "Qty=" not in prd:
        shortage = (2 * ROL) - stock - dead
        qty = int(shortage) if shortage < prd_qty else int(prd_qty)
        prd = f"{prd} Qty= {qty}"

    itd["cut_urg"] = urg
    itd["prd_urg"] = prd
    return itd

def get_conditions(filters):
    conditions = ""
    params = {}
    
    attr_filters = {
        "rm": "Is RM", "bm": "Base Material", "series": "Series", 
        "quality": "Quality", "spl": "Special Treatment", "tt": "Tool Type"
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

    if filters.get("show_in_website") == 1:
        conditions += " AND it.show_in_website = 1"
    if filters.get("item"):
        conditions += " AND it.name = %(item)s"
        params["item"] = filters.get("item")
    if filters.get("variant_of"):
        conditions += " AND it.variant_of = %(variant_of)s"
        params["variant_of"] = filters.get("variant_of")

    return conditions, params
