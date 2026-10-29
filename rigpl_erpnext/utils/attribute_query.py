# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.desk.reportview import get_match_cond
from frappe.utils import cint, cstr

QUERY_ATTRIBUTES = {
    "rm": ("Is RM",),
    "bm": ("Base Material",),
    "brand": ("Brand",),
    "quality": ("HSS Quality", "Carbide Quality", "Tool Steel Quality"),
    "tt": ("Tool Type",),
    "spl": ("Special Treatment",),
    "purpose": ("Purpose",),
    "type": ("Type Selector",),
    "mtm": ("Material To Machine",),
    "series": ("Series",),
}


@frappe.whitelist()
def get_uom_factors(from_uom, to_uom):
    if (from_uom == to_uom):
        return {'lft': 1, 'rgt': 1}
    return {
        'rgt': frappe.db.get_value('UOM Conversion Detail', filters={'parent': from_uom, 'uom':
            to_uom}, fieldname='conversion_factor'),
        'lft': frappe.db.get_value('UOM Conversion Detail', filters={'parent': to_uom, 'uom':
            from_uom}, fieldname='conversion_factor')
    }


def search_attribute_values(attributes, txt, start, page_len):
    """
    Link search over the values of the given Item Attributes. The client searchfield is not
    used, because Item Attribute Value names are hashes.
    """
    txt = cstr(txt)
    return frappe.db.sql("""SELECT attribute_value, parent FROM `tabItem Attribute Value`
    WHERE parent IN %(attributes)s AND attribute_value LIKE %(txt)s {mcond}
    ORDER BY IF(LOCATE(%(_txt)s, attribute_value), LOCATE(%(_txt)s, attribute_value), 99999),
    attribute_value
    LIMIT %(start)s, %(page_len)s""".format(mcond=get_match_cond("Item Attribute Value")),
                         {'attributes': tuple(attributes), 'txt': "%%%s%%" % txt,
                          '_txt': txt.replace("%", ""), 'start': cint(start),
                          'page_len': cint(page_len)})


# searches for Item Attributes
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def attribute_rm_query(doctype, txt, searchfield, start, page_len, filters):
    return search_attribute_values(QUERY_ATTRIBUTES["rm"], txt, start, page_len)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def attribute_bm_query(doctype, txt, searchfield, start, page_len, filters):
    return search_attribute_values(QUERY_ATTRIBUTES["bm"], txt, start, page_len)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def attribute_brand_query(doctype, txt, searchfield, start, page_len, filters):
    return search_attribute_values(QUERY_ATTRIBUTES["brand"], txt, start, page_len)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def attribute_quality_query(doctype, txt, searchfield, start, page_len, filters):
    return search_attribute_values(QUERY_ATTRIBUTES["quality"], txt, start, page_len)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def attribute_tt_query(doctype, txt, searchfield, start, page_len, filters):
    return search_attribute_values(QUERY_ATTRIBUTES["tt"], txt, start, page_len)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def attribute_spl_query(doctype, txt, searchfield, start, page_len, filters):
    return search_attribute_values(QUERY_ATTRIBUTES["spl"], txt, start, page_len)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def attribute_purpose_query(doctype, txt, searchfield, start, page_len, filters):
    return search_attribute_values(QUERY_ATTRIBUTES["purpose"], txt, start, page_len)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def attribute_type_query(doctype, txt, searchfield, start, page_len, filters):
    return search_attribute_values(QUERY_ATTRIBUTES["type"], txt, start, page_len)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def attribute_mtm_query(doctype, txt, searchfield, start, page_len, filters):
    return search_attribute_values(QUERY_ATTRIBUTES["mtm"], txt, start, page_len)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def attribute_series_query(doctype, txt, searchfield, start, page_len, filters):
    return search_attribute_values(QUERY_ATTRIBUTES["series"], txt, start, page_len)
