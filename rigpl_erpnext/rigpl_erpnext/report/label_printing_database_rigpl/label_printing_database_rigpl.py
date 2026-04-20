# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt


# Most Important Note that Label Desc Field should always be COLUMN # 20 do not move this column or change the XLSX
# Used in Laser Marking to reference Label Desc field dynamically till them don't move the column

def execute(filters=None):
    columns = get_columns()
    data = get_data()
    return columns, data


def get_columns():
    return [
        "Item:Link/Item:130", "BM::80", "Brand::50", "Quality::50", "TT::150", "SPL::50", "Series::50", "Qual-Spl::80",
        "d1::40", "d1_sfx::30", "w1::40", "w1_sfx::30", "l1::40", "l1_sfx::30", "d2::40", "d2_sfx::30",
        "l2::40", "l2_sfx::30",  "Zn::30", "Label Desc::150", "Description::400 ", "r1::40", "r1_sfx::30", "l3::40",
        "l3_sfx::30"]


def get_data():
    # 1. Base Item Fetch
    items = frappe.db.sql("""
        SELECT it.name as item_code, it.description
        FROM `tabItem` it
        WHERE it.is_sales_item = 1 AND it.disabled = 0 AND it.has_variants = 0
        AND IFNULL(it.end_of_life, '2099-12-31') > CURDATE()
        ORDER BY it.creation ASC, it.name ASC
    """, as_dict=1)

    if not items:
        return []

    item_codes = [d.item_code for d in items]

    # 2. Bulk Fetch Attributes (O(1) mapping)
    attr_map = get_attribute_map(item_codes)

    # 3. Assembly
    data = []
    for it in items:
        res = attr_map.get(it.item_code, {})
        
        # Attribute Data Extraction
        bm = res.get("Base Material", "")
        brand = res.get("Brand", "")
        if brand == "None": brand = ""
        
        qual_full = res.get("Quality", "")
        qual = qual_full[2:] if len(qual_full) > 2 else qual_full
        
        tt = res.get("Tool Type", "")
        spl = res.get("Special Treatment", "")
        if spl == "None": spl = ""
        
        series = res.get("Series", "")
        
        # Qual-Spl logic
        qualspl = qual
        if spl:
            suffix = "Nova" if spl == "ACX" else spl
            qualspl = f"{qual} {suffix}"
            
        # Dimension Logic (Inch vs MM priority)
        def get_dim(pref, suff):
            val = res.get(f"{pref}_{suff}", res.get(f"{pref}_mm", ""))
            sfx = "''" if res.get(f"{pref}_{suff}") else ""
            return val, sfx
            
        d1, d1_sfx = get_dim("d1", "inch")
        w1, w1_sfx = get_dim("w1", "inch")
        l1, l1_sfx = get_dim("l1", "inch")
        d2, d2_sfx = get_dim("d2", "inch")
        l2, l2_sfx = get_dim("l2", "inch")
        r1, r1_sfx = get_dim("r1", "inch")
        l3, l3_sfx = get_dim("l3", "inch")
        
        zn_val = res.get("Number of Flutes Zn")
        zn = f"Z{zn_val}" if zn_val else None
        
        # Build Label Desc (Index 19)
        lbl_desc = ""
        if r1: lbl_desc += f"CR:{r1}{r1_sfx} "
        if d1:
            lbl_desc += f"{d1}{d1_sfx}"
            if w1: lbl_desc += f"x{w1}{w1_sfx}"
        if l1: lbl_desc += f"x{l1}{l1_sfx}"
        if d2: lbl_desc += f"x{d2}{d2_sfx}"
        if l2: lbl_desc += f"x{l2}{l2_sfx}"
        if l3: lbl_desc += f" RL:{l3}"
        
        # Bm logic
        if bm == 'HSS':
            if qual == '2X': bm = 'HSS-M35'
            elif qual == '3X': bm = 'HSS-T42'
            elif qual == 'SP': bm = 'HSS-M42'

        # Final row mapping
        row = [
            it.item_code, bm, brand, qual, tt, spl, series, qualspl,
            d1, d1_sfx, w1, w1_sfx, l1, l1_sfx, d2, d2_sfx, l2, l2_sfx,
            zn, lbl_desc, it.description, r1, r1_sfx, l3, l3_sfx
        ]
        data.append(row)
        
    return data


def get_attribute_map(item_codes):
    if not item_codes: return {}
    
    # Pre-fetching all possible variant attributes at once
    raw_attrs = frappe.get_all("Item Variant Attribute",
        filters={"parent": ["in", item_codes]},
        fields=["parent", "attribute", "attribute_value"]
    )
    
    res = {}
    for a in raw_attrs:
        if a.parent not in res: res[a.parent] = {}
        # Handle the dynamic '%Quality' mapping logic
        key = "Quality" if a.attribute.endswith("Quality") else a.attribute
        res[a.parent][key] = a.attribute_value
    return res

