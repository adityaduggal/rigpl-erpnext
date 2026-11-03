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


@frappe.whitelist()
def get_variant_dialog_data(template):
    """
    Data for the New Variant with Restrictions dialog of a template (#192), in a few bulk queries:
    - values: {attribute: its values in idx order}, for the template attributes that are not numeric
    - links: {link field: {"source", "uoms": {hidden attribute: UOM}, "default_uom"}} for the
      hidden attributes, where the link field is their `update_from` (e.g. d1 for d1_mm, d1_inch)
    - factors: {from UOM: {to UOM: conversion factor}} for the UOMs of the links
    """
    if not isinstance(template, str) or not frappe.db.exists("Item", {"name": template, "has_variants": 1}):
        frappe.throw(f"{template} is not an Item template", title="Template not found")
    if not frappe.has_permission("Item", "read", template):
        raise frappe.PermissionError
    iva = frappe.qb.DocType("Item Variant Attribute")
    att = frappe.qb.DocType("Item Attribute")
    rows = (
        frappe.qb.from_(iva)
        .inner_join(att)
        .on(att.name == iva.attribute)
        .select(iva.attribute, iva.use_in_description, att.numeric_values, att.hidden, att.update_from,
            att.source, att.relation)
        .where((iva.parent == template) & (iva.parenttype == "Item"))
        .orderby(iva.idx)
    ).run(as_dict=True)
    links = get_dialog_links(rows)
    uoms = sorted({uom for link in links.values() for uom in link["uoms"].values() if uom})
    return {
        "values": get_attribute_value_lists(
            [row.attribute for row in rows if not cint(row.numeric_values)]
        ),
        "links": links,
        "factors": get_uom_factor_map(uoms),
    }


def get_dialog_links(rows):
    """
    Groups the hidden attribute rows by their `update_from` link field. The default UOM is the
    only UOM, or the only one with `use_in_description` (the others are calculated from it).
    """
    links = {}
    for row in rows:
        if not cint(row.hidden) or not row.update_from:
            continue
        link = links.setdefault(row.update_from, {"source": row.source, "uoms": {}, "shown": []})
        link["uoms"][row.attribute] = row.relation
        if cint(row.use_in_description):
            link["shown"].append(row.relation)
    for link in links.values():
        uoms = set(link["uoms"].values())
        shown = link.pop("shown")
        if len(uoms) == 1:
            link["default_uom"] = uoms.pop()
        elif len(set(shown)) == 1:
            link["default_uom"] = shown[0]
        else:
            link["default_uom"] = None
    return links


def get_attribute_value_lists(attributes):
    """Returns {attribute: [attribute_value in idx order]}."""
    if not attributes:
        return {}
    iav = frappe.qb.DocType("Item Attribute Value")
    values = {attribute: [] for attribute in attributes}
    rows = (
        frappe.qb.from_(iav)
        .select(iav.parent, iav.attribute_value)
        .where(iav.parent.isin(attributes))
        .where(iav.parenttype == "Item Attribute")
        .orderby(iav.parent)
        .orderby(iav.idx)
    ).run()
    for parent, value in rows:
        values[parent].append(value)
    return values


def get_uom_factor_map(uoms):
    """Returns {from UOM: {to UOM: factor}} like get_uom_factors 'rgt', for the pairs that have one."""
    if len(uoms) < 2:
        return {}
    ucd = frappe.qb.DocType("UOM Conversion Detail")
    rows = (
        frappe.qb.from_(ucd)
        .select(ucd.parent, ucd.uom, ucd.conversion_factor)
        .where(ucd.parent.isin(uoms) & ucd.uom.isin(uoms))
    ).run()
    factors = {}
    for from_uom, to_uom, factor in rows:
        factors.setdefault(from_uom, {})[to_uom] = factor
    return factors


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
