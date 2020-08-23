# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.desk.reportview import get_match_cond


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


# searches for Item Attributes
@frappe.whitelist()
def attribute_rm_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""SELECT attribute_value, parent FROM `tabItem Attribute Value`
    WHERE parent = "Is RM" AND ({key} LIKE %(txt)s OR attribute_value LIKE %(txt)s) {mcond} 
    ORDER BY IF(LOCATE(%(_txt)s, name), LOCATE(%(_txt)s, name), 99999), IF(LOCATE(%(_txt)s, attribute_value), 
    LOCATE(%(_txt)s, attribute_value), 99999), attribute_value 
    LIMIT %(start)s, %(page_len)s""".format(**{'key': searchfield, 'mcond': get_match_cond(doctype)}),
                         {'txt': "%%%s%%" % txt, '_txt': txt.replace("%", ""), 'start': start, 'page_len': page_len})


@frappe.whitelist()
def attribute_bm_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""SELECT attribute_value, parent FROM `tabItem Attribute Value`
    WHERE parent = "Base Material" AND ({key} LIKE %(txt)s OR attribute_value LIKE %(txt)s) {mcond} 
    ORDER BY IF(LOCATE(%(_txt)s, name), LOCATE(%(_txt)s, name), 99999), IF(LOCATE(%(_txt)s, attribute_value), 
    LOCATE(%(_txt)s, attribute_value), 99999), attribute_value 
    LIMIT %(start)s, %(page_len)s""".format(**{'key': searchfield, 'mcond': get_match_cond(doctype)}),
                         {'txt': "%%%s%%" % txt, '_txt': txt.replace("%", ""), 'start': start, 'page_len': page_len})


@frappe.whitelist()
def attribute_brand_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""SELECT attribute_value, parent FROM `tabItem Attribute Value`
    WHERE parent = "Brand" AND ({key} LIKE %(txt)s OR attribute_value LIKE %(txt)s) {mcond} 
    ORDER BY IF(LOCATE(%(_txt)s, name), LOCATE(%(_txt)s, name), 99999), IF(LOCATE(%(_txt)s, attribute_value), 
    LOCATE(%(_txt)s, attribute_value), 99999), attribute_value 
    LIMIT %(start)s, %(page_len)s""".format(**{'key': searchfield, 'mcond': get_match_cond(doctype)}),
                         {'txt': "%%%s%%" % txt, '_txt': txt.replace("%", ""), 'start': start, 'page_len': page_len})


@frappe.whitelist()
def attribute_quality_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""SELECT attribute_value, parent FROM `tabItem Attribute Value`
    WHERE (parent = "HSS Quality" OR parent = 'Carbide Quality' OR parent = 'Tool Steel Quality') AND 
    ({key} LIKE %(txt)s OR attribute_value LIKE %(txt)s) {mcond} 
    ORDER BY IF(LOCATE(%(_txt)s, name), LOCATE(%(_txt)s, name), 99999), IF(LOCATE(%(_txt)s, attribute_value), 
    LOCATE(%(_txt)s, attribute_value), 99999), attribute_value 
    LIMIT %(start)s, %(page_len)s""".format(**{'key': searchfield, 'mcond': get_match_cond(doctype)}),
                         {'txt': "%%%s%%" % txt, '_txt': txt.replace("%", ""), 'start': start, 'page_len': page_len})


@frappe.whitelist()
def attribute_tt_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""SELECT attribute_value, parent FROM `tabItem Attribute Value`
    WHERE parent = "Tool Type" AND ({key} LIKE %(txt)s OR attribute_value LIKE %(txt)s) {mcond} 
    ORDER BY IF(LOCATE(%(_txt)s, name), LOCATE(%(_txt)s, name), 99999), IF(LOCATE(%(_txt)s, attribute_value), 
    LOCATE(%(_txt)s, attribute_value), 99999), attribute_value 
    LIMIT %(start)s, %(page_len)s""".format(**{'key': searchfield, 'mcond': get_match_cond(doctype)}),
                         {'txt': "%%%s%%" % txt, '_txt': txt.replace("%", ""), 'start': start, 'page_len': page_len})


@frappe.whitelist()
def attribute_spl_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""SELECT attribute_value, parent FROM `tabItem Attribute Value`
    WHERE parent = "Special Treatment" AND ({key} LIKE %(txt)s OR attribute_value LIKE %(txt)s) {mcond} 
    ORDER BY IF(LOCATE(%(_txt)s, name), LOCATE(%(_txt)s, name), 99999), IF(LOCATE(%(_txt)s, attribute_value), 
    LOCATE(%(_txt)s, attribute_value), 99999), attribute_value 
    LIMIT %(start)s, %(page_len)s""".format(**{'key': searchfield, 'mcond': get_match_cond(doctype)}),
                         {'txt': "%%%s%%" % txt, '_txt': txt.replace("%", ""), 'start': start, 'page_len': page_len})


@frappe.whitelist()
def attribute_purpose_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""SELECT attribute_value, parent FROM `tabItem Attribute Value`
    WHERE parent = "Purpose" AND ({key} LIKE %(txt)s OR attribute_value LIKE %(txt)s) {mcond} 
    ORDER BY IF(LOCATE(%(_txt)s, name), LOCATE(%(_txt)s, name), 99999), IF(LOCATE(%(_txt)s, attribute_value), 
    LOCATE(%(_txt)s, attribute_value), 99999), attribute_value 
    LIMIT %(start)s, %(page_len)s""".format(**{'key': searchfield, 'mcond': get_match_cond(doctype)}),
                         {'txt': "%%%s%%" % txt, '_txt': txt.replace("%", ""), 'start': start, 'page_len': page_len})


@frappe.whitelist()
def attribute_type_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""SELECT attribute_value, parent FROM `tabItem Attribute Value`
    WHERE parent = "Type Selector" AND ({key} LIKE %(txt)s OR attribute_value LIKE %(txt)s) {mcond} 
    ORDER BY IF(LOCATE(%(_txt)s, name), LOCATE(%(_txt)s, name), 99999), IF(LOCATE(%(_txt)s, attribute_value), 
    LOCATE(%(_txt)s, attribute_value), 99999), attribute_value 
    LIMIT %(start)s, %(page_len)s""".format(**{'key': searchfield, 'mcond': get_match_cond(doctype)}),
                         {'txt': "%%%s%%" % txt, '_txt': txt.replace("%", ""), 'start': start, 'page_len': page_len})


@frappe.whitelist()
def attribute_mtm_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""SELECT attribute_value, parent FROM `tabItem Attribute Value`
    WHERE parent = "Material To Machine" AND ({key} LIKE %(txt)s OR attribute_value LIKE %(txt)s) {mcond} 
    ORDER BY IF(LOCATE(%(_txt)s, name), LOCATE(%(_txt)s, name), 99999), IF(LOCATE(%(_txt)s, attribute_value), 
    LOCATE(%(_txt)s, attribute_value), 99999), attribute_value 
    LIMIT %(start)s, %(page_len)s""".format(**{'key': searchfield, 'mcond': get_match_cond(doctype)}),
                         {'txt': "%%%s%%" % txt, '_txt': txt.replace("%", ""), 'start': start, 'page_len': page_len})


@frappe.whitelist()
def attribute_series_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""SELECT attribute_value, parent FROM `tabItem Attribute Value`
    WHERE parent = "Series" AND ({key} LIKE %(txt)s OR attribute_value LIKE %(txt)s) {mcond} 
    ORDER BY IF(LOCATE(%(_txt)s, name), LOCATE(%(_txt)s, name), 99999), IF(LOCATE(%(_txt)s, attribute_value), 
    LOCATE(%(_txt)s, attribute_value), 99999), attribute_value 
    LIMIT %(start)s, %(page_len)s""".format(**{'key': searchfield, 'mcond': get_match_cond(doctype)}),
                         {'txt': "%%%s%%" % txt, '_txt': txt.replace("%", ""), 'start': start, 'page_len': page_len})
