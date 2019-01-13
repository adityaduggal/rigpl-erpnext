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
def attribute_rm_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Is RM" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_bm_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Base Material" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_brand_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Brand" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_quality_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where (parent = 'HSS Quality' OR parent = 'Carbide Quality' OR parent = 'Tool Steel Quality')
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_tt_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Tool Type" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_spl_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Special Treatment" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_purpose_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Purpose" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_type_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Type Selector" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_mtm_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Material to Machine" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_series_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Series" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})