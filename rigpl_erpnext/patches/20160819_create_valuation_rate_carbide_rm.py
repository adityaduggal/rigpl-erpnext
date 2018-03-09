# -*- coding: utf-8 -*-
import frappe
from frappe.utils import flt

def execute():
	items = frappe.db.sql("""SELECT it.name FROM `tabItem` it
		LEFT JOIN `tabItem Variant Attribute` bm ON it.name = bm.parent 
			AND bm.attribute = 'Base Material'
		LEFT JOIN `tabItem Variant Attribute` tt ON it.name = tt.parent
			AND tt.attribute = 'Tool Type'
		LEFT JOIN `tabItem Variant Attribute` rm ON it.name =rm.parent
			AND rm.attribute = 'Is RM'
		WHERE
			rm.attribute_value = 'Yes' AND bm.attribute_value = 'Carbide'
			AND tt.attribute_value = 'Round Tool Bits'
		ORDER BY it.name""", as_list = 1)
	for d in items:
		item = frappe.get_doc("Item", d[0])
		#find LPR for each item and them create VR for similar Templates
		lpr = frappe.db.sql("""SELECT pri.item_code, pri.base_net_rate as lpr,
			IFNULL(pr.buying_price_list, 'INR Buying PL') AS buying_price_list, 
			pr.posting_date
			FROM `tabPurchase Receipt` pr, `tabPurchase Receipt Item` pri
			WHERE pr.docstatus = 1 AND pri.parent = pr.name
				AND pri.item_code = '%s'
			ORDER BY pr.posting_date DESC, pr.posting_time DESC
			LIMIT 1""" %d[0], as_dict=1)
		vr_list = []
		if lpr:
			#Now check for all item codes with Similar Attributes
			attributes = frappe.db.sql("""SELECT idx, attribute, attribute_value 
			FROM `tabItem Variant Attribute` WHERE parent = '%s'
			ORDER BY idx"""%(item.name), as_dict = 1)
			check = 0
			for att in attributes:
				if att.attribute == 'l1_mm':
					length = flt(att.attribute_value)
				if att.attribute == 'd1_mm':
					similar_variants = frappe.db.sql("""SELECT it.name 
						FROM `tabItem` it, `tabItem Variant Attribute` iva
						WHERE it.variant_of = '%s' AND iva.attribute = 'd1_mm' 
						AND iva.attribute_value = %s AND iva.parent = it.name
						"""%(item.variant_of, att.attribute_value), as_list = 1)
				else:
					similar_variants = []
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
			else:
				dict = {}
				dict['name'] =  lpr[0].item_code
				dict['valuation'] = round_down(flt(lpr[0].lpr),10)
				vr_list.append(dict)
						
		for d in vr_list:
			vr = frappe.db.sql("""SELECT name FROM `tabValuation Rate` 
				WHERE item_code = '%s' AND disabled = 'No'""" %(d['name']), as_list=1)
			if vr:
				#Condition if the Valuation Rate exists then Update the same
				exist_vr = frappe.get_doc("Valuation Rate", vr[0][0])
				exist_vr.item_code = d['name']
				exist_vr.price_list = lpr[0].buying_price_list
				exist_vr.valid_from = lpr[0].posting_date
				exist_vr.disabled = 'No'
				exist_vr.valuation_rate = d['valuation']
				exist_vr.save(ignore_permissions=True)
				print ("Updated Valuation Rate#", exist_vr.name, " for Item Code: ", d['name'])
			else:
				#Condition if there is NO Valuation Rate then create new
				new_vr = frappe.get_doc({
					"doctype": "Valuation Rate",
					"item_code": d['name'],
					"price_list": lpr[0].buying_price_list,
					"valid_from": lpr[0].posting_date,
					"disabled": "No",
					"valuation_rate": d['valuation'],
					})
				new_vr.insert(ignore_permissions=True)
				print ("Created Valuation Rate # " + new_vr.name + " for Item Code: " + d['name'])
				
def round_down(num, divisor):
    return num - (num%divisor)