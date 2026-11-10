# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from typing import Dict, List, Optional

import frappe
from frappe.utils import getdate, nowdate

from rigpl_erpnext.utils.item_attribute_utils import get_attribute_map

# Most Important Note that Label Desc Field should always be COLUMN # 20 do not move this column or change the XLSX
# Used in Laser Marking to reference Label Desc field dynamically till them don't move the column

INCH = "''"
# Item Variant Attributes that end in "Quality". An item has 1 of them, the first found here is used.
QUALITY_ATTRIBUTES = (
    "Carbide Quality",
    "HSS Quality",
    "Tool Steel Quality",
    "Die Steel Quality",
    "Aluminium Oxide Quality",
)
SIZES = ("d1", "w1", "l1", "d2", "l2", "r1", "l3")
ATTRIBUTES = (
    ("Base Material", "Brand", "Tool Type", "Special Treatment", "Series", "Number of Flutes Zn")
    + QUALITY_ATTRIBUTES
    + tuple("{}_{}".format(size, unit) for size in SIZES for unit in ("mm", "inch"))
)
HSS_BASE_MATERIAL = {"2X": "HSS-M35", "3X": "HSS-T42", "SP": "HSS-M42"}


def execute(filters=None):
    return get_columns(), get_data()


def get_columns() -> List[Dict]:
    # The order of the columns is the order of the XLSX, see the note on top of the file.
    columns = [
        ("item_code", "Item", 130), ("base_mat", "BM", 80), ("brand", "Brand", 50), ("qual", "Quality", 50),
        ("tt", "TT", 150), ("spl", "SPL", 50), ("series", "Series", 50), ("qualspl", "Qual-Spl", 80),
        ("d1", "d1", 40), ("d1_sfx", "d1_sfx", 30), ("w1", "w1", 40), ("w1_sfx", "w1_sfx", 30),
        ("l1", "l1", 40), ("l1_sfx", "l1_sfx", 30), ("d2", "d2", 40), ("d2_sfx", "d2_sfx", 30),
        ("l2", "l2", 40), ("l2_sfx", "l2_sfx", 30), ("zn", "Zn", 30), ("lbl_desc", "Label Desc", 150),
        ("description", "Description", 400), ("r1", "r1", 40), ("r1_sfx", "r1_sfx", 30), ("l3", "l3", 40),
        ("l3_sfx", "l3_sfx", 30),
    ]
    return [
        {
            "fieldname": fieldname, "label": label, "width": width,
            "fieldtype": "Link" if fieldname == "item_code" else "Data",
            "options": "Item" if fieldname == "item_code" else None,
        }
        for fieldname, label, width in columns
    ]


def get_data() -> List[List]:
    items = get_items()
    attributes = get_attribute_map([item.name for item in items], ATTRIBUTES)
    return [build_row(item, attributes.get(item.name, {})) for item in items]


def get_items() -> List[frappe._dict]:
    """Sales items that the user can read, oldest first. The order is the order of the XLSX."""
    items = frappe.get_list(
        "Item",
        filters={"is_sales_item": 1, "disabled": 0, "has_variants": 0},
        fields=["name", "description", "end_of_life"],
        order_by="creation asc, name asc",
        limit_page_length=0,
    )
    today = getdate(nowdate())
    return [item for item in items if not item.end_of_life or getdate(item.end_of_life) > today]


def build_row(item: frappe._dict, attributes: Dict[str, str]) -> List:
    quality = next((attributes[name] for name in QUALITY_ATTRIBUTES if name in attributes), None)
    qual = quality[2:] if quality is not None else None
    base_mat = attributes.get("Base Material")
    if base_mat == "HSS":
        base_mat = HSS_BASE_MATERIAL.get(qual, base_mat)
    spl = attributes.get("Special Treatment")
    sizes = {name: get_size(attributes, name) for name in SIZES}
    zn = attributes.get("Number of Flutes Zn")
    return [
        item.name, base_mat, none_as_blank(attributes.get("Brand")), qual, attributes.get("Tool Type"),
        none_as_blank(spl), attributes.get("Series") or "", get_qual_spl(qual, spl),
        *sizes["d1"], *sizes["w1"], *sizes["l1"], *sizes["d2"], *sizes["l2"],
        "Z" + zn if zn is not None else None,
        get_label_desc(sizes), item.description,
        *sizes["r1"], *sizes["l3"],
    ]


def none_as_blank(value: Optional[str]) -> Optional[str]:
    """The attribute value 'None' means that the item has nothing of it."""
    return "" if value == "None" else value


def get_qual_spl(qual: Optional[str], spl: Optional[str]) -> Optional[str]:
    if qual is None or spl is None or spl == "None":
        return qual
    return "{} {}".format(qual, "Nova" if spl == "ACX" else spl)


def is_zero(value: str) -> bool:
    """True for 0, 0.0 and 0.000. An inch fraction such as 3/32 is not a number, so it is not 0."""
    try:
        return float(value) == 0
    except ValueError:
        return False


def get_size(attributes: Dict[str, str], name: str) -> tuple:
    """(value, suffix) of a size. The inch value is used before the mm value. A size of 0 is blank."""
    inch = attributes.get(name + "_inch")
    value = inch if inch is not None else attributes.get(name + "_mm")
    if value is None or is_zero(value):
        return ("" if name == "d1" else None), ""
    return value, INCH if inch is not None else ""


def get_label_desc(sizes: Dict[str, tuple]) -> str:
    desc = ""
    r1, r1_sfx = sizes["r1"]
    d1, d1_sfx = sizes["d1"]
    w1, w1_sfx = sizes["w1"]
    if r1:
        desc += "CR:" + r1 + r1_sfx + " "
    if d1:
        desc += d1 + d1_sfx
        if w1:
            desc += "x" + w1 + w1_sfx
    for name in ("l1", "d2", "l2"):
        value, suffix = sizes[name]
        if value:
            desc += "x" + value + suffix
    l3 = sizes["l3"][0]
    if l3:
        desc += " RL:" + l3
    return desc
