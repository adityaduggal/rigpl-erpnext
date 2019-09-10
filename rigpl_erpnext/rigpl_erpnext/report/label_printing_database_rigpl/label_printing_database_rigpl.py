# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	columns= get_columns()
	data = get_data()
	return columns, data

def get_columns():
	return [
		"Item:Link/Item:130", 
		"BM::80", "Brand::50","Quality::50",
		"TT::150", "SPL::50", "Series::50",
		"Qual-Spl::80",
		"d1::40", "d1_sfx::30", 
		"w1::40", "w1_sfx::30", 
		"l1::40", "l1_sfx::30", 
		"d2::40", "d2_sfx::30", 
		"l2::40", "l2_sfx::30", 
		"Zn::30", "Label Desc::100", "Description::400"
	]

def get_data():
	query = """SELECT it.name AS item_code, bm.attribute_value AS base_mat,
		IF(brand.attribute_value = 'None', '', brand.attribute_value ) AS brand, 
		SUBSTRING(quality.attribute_value,3) AS qual, tt.attribute_value AS tt,
		IF(spl.attribute_value = 'None', '', spl.attribute_value) AS spl, 
		IFNULL(series.attribute_value,'') AS series, 
		IF(spl.attribute_value != 'None', 
			IF(spl.attribute_value = 'ACX', CONCAT(SUBSTRING(quality.attribute_value,3) , " ", "Nova"), 
			CONCAT(SUBSTRING(quality.attribute_value,3) , " ", spl.attribute_value)), 
			SUBSTRING(quality.attribute_value,3)) AS qualspl,
		IFNULL(IFNULL(d1_inch.attribute_value, d1_mm.attribute_value),'') AS d1,
		IF(d1_inch.attribute_value IS NULL, "", "''") AS d1_sfx,
		IFNULL(w1_inch.attribute_value, w1_mm.attribute_value) AS w1,
		IF(w1_inch.attribute_value IS NULL, IF(w1_mm.attribute_value IS NULL, "", ""), "''") AS w1_sfx,
		IFNULL(l1_inch.attribute_value, l1_mm.attribute_value) AS l1,
		IF(l1_inch.attribute_value IS NULL, IF(l1_mm.attribute_value IS NULL, "", ""), "''") AS l1_sfx,
		IFNULL(d2_inch.attribute_value, d2_mm.attribute_value) AS d2,
		IF(d2_inch.attribute_value IS NULL, IF(d2_mm.attribute_value IS NULL, "", ""), "''") AS d2_sfx,
		IFNULL(l2_inch.attribute_value, l2_mm.attribute_value) AS l2,
		IF(l2_inch.attribute_value IS NULL, IF(l2_mm.attribute_value IS NULL, "", ""), "''") AS l2_sfx,
		IF(zn.attribute_value IS NOT NULL, CONCAT("Z", zn.attribute_value), NULL) AS zn,
		'' AS lbl_desc, it.description AS description, 
		IFNULL(r1_mm.attribute_value, r1_mm.attribute_value) AS r1,
		IFNULL(r1_inch.attribute_value, r1_inch.attribute_value) AS r1_inch

		FROM `tabItem` it 
		LEFT JOIN `tabItem Variant Attribute` bm ON it.name = bm.parent
			AND bm.attribute = 'Base Material'
		LEFT JOIN `tabItem Variant Attribute` brand ON it.name = brand.parent
			AND brand.attribute = 'Brand'
		LEFT JOIN `tabItem Variant Attribute` quality ON it.name = quality.parent
			AND quality.attribute LIKE '%Quality'
		LEFT JOIN `tabItem Variant Attribute` tt ON it.name = tt.parent
			AND tt.attribute = 'Tool Type'
		LEFT JOIN `tabItem Variant Attribute` spl ON it.name = spl.parent
			AND spl.attribute = 'Special Treatment'
		LEFT JOIN `tabItem Variant Attribute` purpose ON it.name = purpose.parent
			AND purpose.attribute = 'Purpose'
		LEFT JOIN `tabItem Variant Attribute` type ON it.name = type.parent
			AND type.attribute = 'Type Selector'
		LEFT JOIN `tabItem Variant Attribute` mtm ON it.name = mtm.parent
			AND mtm.attribute = 'Material to Machine'
		LEFT JOIN `tabItem Variant Attribute` series ON it.name = series.parent
			AND series.attribute = 'Series'
		LEFT JOIN `tabItem Variant Attribute` d1_mm ON it.name = d1_mm.parent
			AND d1_mm.attribute = 'd1_mm'
		LEFT JOIN `tabItem Variant Attribute` d1_inch ON it.name = d1_inch.parent
			AND d1_inch.attribute = 'd1_inch'
		LEFT JOIN `tabItem Variant Attribute` w1_mm ON it.name = w1_mm.parent
			AND w1_mm.attribute = 'w1_mm'
		LEFT JOIN `tabItem Variant Attribute` w1_inch ON it.name = w1_inch.parent
			AND w1_inch.attribute = 'w1_inch'
		LEFT JOIN `tabItem Variant Attribute` l1_mm ON it.name = l1_mm.parent
			AND l1_mm.attribute = 'l1_mm'
		LEFT JOIN `tabItem Variant Attribute` l1_inch ON it.name = l1_inch.parent
			AND l1_inch.attribute = 'l1_inch'
		LEFT JOIN `tabItem Variant Attribute` d2_mm ON it.name = d2_mm.parent
			AND d2_mm.attribute = 'd2_mm'
		LEFT JOIN `tabItem Variant Attribute` d2_inch ON it.name = d2_inch.parent
			AND d2_inch.attribute = 'd2_inch'
		LEFT JOIN `tabItem Variant Attribute` l2_mm ON it.name = l2_mm.parent
			AND l2_mm.attribute = 'l2_mm'
		LEFT JOIN `tabItem Variant Attribute` l2_inch ON it.name = l2_inch.parent
			AND l2_inch.attribute = 'l2_inch'
		LEFT JOIN `tabItem Variant Attribute` zn ON it.name = zn.parent
			AND zn.attribute = 'Number of Flutes Zn'
		LEFT JOIN `tabItem Variant Attribute` r1_mm ON it.name = r1_mm.parent
			AND r1_mm.attribute = 'r1_mm'
		LEFT JOIN `tabItem Variant Attribute` r1_inch ON it.name = r1_inch.parent
			AND r1_inch.attribute = 'r1_inch'
		WHERE it.is_sales_item = 1 AND it.disabled = 0
		AND it.has_variants = 0
		AND IFNULL(it.end_of_life, '2099-12-31') > CURDATE()
		ORDER BY it.creation ASC, it.name ASC"""
	data_dict = frappe.db.sql(query, as_dict=1)
	data = []
	for d in data_dict:
		if d.base_mat == 'HSS':
			if d.qual == '2X':
				d.base_mat = 'HSS-M35'
			if d.qual == '3X':
				d.base_mat = 'HSS-T42'
			if d.qual == 'SP':
				d.base_mat = 'HSS-M42'
		if d.r1:
			if d.r1_inch:
				d.lbl_desc += "CR:" + d.r1_inch + '" '
			else:
				d.lbl_desc += "CR:" + d.r1 + " "
		if d.d1:
			d.lbl_desc += d.d1 + d.d1_sfx
			if d.w1:
				d.lbl_desc += "x" + d.w1 + d.w1_sfx
		if d.l1:
			d.lbl_desc += "x" + d.l1 + d.l1_sfx
		if d.d2:
			d.lbl_desc += "x" + d.d2 + d.d2_sfx
		if d.l2:
			d.lbl_desc += "x" + d.l2 + d.l2_sfx

	for d in data_dict:
		row = [d.item_code, d.base_mat, d.brand, d.qual, d.tt, d.spl, d.series, \
			d.qualspl, d.d1, d.d1_sfx, d.w1, d.w1_sfx, d.l1, d.l1_sfx, \
			d.d2, d.d2_sfx, d.l2, d.l2_sfx, d.zn, d.lbl_desc, d.description]
		data.append(row)
	return data
