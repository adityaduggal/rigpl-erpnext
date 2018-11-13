# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.model.mapper import get_mapped_doc
from frappe.utils import nowdate, add_days, flt
from frappe.desk.reportview import get_match_cond

def validate(doc,method):
	create_valuation_rate(doc,method)

def create_valuation_rate(doc,method):
	#This function would create/update the valuation rate for the Carbide Cut Pieces
	#Check if the GRN is for Carbide Raw Material
	for d in doc.items:
		po = frappe.get_doc("Purchase Order", d.purchase_order)
		if po.is_subcontracting != 1:
			item = frappe.get_doc("Item", d.item_code)
			if item.variant_of and item.is_stock_item == 1:
				#Now check for all item codes with Similar Attributes
				attributes = frappe.db.sql("""SELECT idx, attribute, attribute_value 
				FROM `tabItem Variant Attribute` WHERE parent = '%s'
				ORDER BY idx"""%(item.name), as_dict = 1)
				check = 0
				for att in attributes:
					if att.attribute == 'Tool Type' and att.attribute_value == 'Round Tool Bits':
						check += 1
					if att.attribute == 'l1_mm':
						check += 1
						length = att.attribute_value
					if att.attribute == 'd1_mm':
						similar_variants = frappe.db.sql("""SELECT it.name 
							FROM `tabItem` it, `tabItem Variant Attribute` iva
							WHERE it.variant_of = '%s' AND iva.attribute = 'd1_mm' 
							AND iva.attribute_value = %s AND iva.parent = it.name
							"""%(item.variant_of, att.attribute_value), as_list = 1)
				if check == 2:
					vr_list = []
					if similar_variants:
						for var in similar_variants:
							dict = {}
							len = frappe.db.sql("""SELECT attribute_value FROM `tabItem Variant Attribute`
								WHERE parent = '%s' AND attribute = 'l1_mm'"""%var[0], as_list=1)
							dict['name'] = var[0]
							dict['length'] = len[0][0]
							if (flt(len[0][0])/flt(length)) < 0.5:
								factor = 0.8
							elif (flt(len[0][0])/flt(length)) < 0.9:
								factor = 0.9
							else: factor = 1
							vr = round_down(flt(d.base_net_rate) * (flt(len[0][0])/flt(length)) * factor, 10)
							dict['valuation'] = vr
							vr_list.append(dict)
							vr_list = sorted(vr_list, key=lambda k: k['length'])
					for d in vr_list:
						#frappe.msgprint(str(vr_list))
						vr = frappe.db.sql("""SELECT valuation_rate FROM `tabItem` 
							WHERE name = '%s'""" %(d['name']), as_list=1)
						frappe.db.set_value('Item', d['name'], "valuation_rate", d['valuation'])
						frappe.db.set_value('Item', d['name'], "valuation_rate_date", doc.posting_date)
						frappe.msgprint('Updated Valuation Rate #{0} for Item Code: {1} \
							with Date: {2}'.format(d['valuation'], d['name'], str(doc.posting_date)))
		
def round_down(num, divisor):
    return num - (num%divisor)