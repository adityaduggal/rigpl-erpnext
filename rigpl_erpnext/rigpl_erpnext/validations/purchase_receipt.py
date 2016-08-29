# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.utils import flt

def validate(doc,method):
	for d in doc.items:
		wh = frappe.get_doc("Warehouse", d.warehouse)
		if wh.is_subcontracting_warehouse == 1:
			frappe.throw(("Subcontracted Warehouse is Not Allowed Check Row# {0}").format(d.idx))
	create_valuation_rate(doc,method)

def on_submit(doc,method):
	chk = check_subpo(doc,method)
	if chk == 1:
		chk_ste = get_existing_ste(doc,method)
		if chk_ste:
			if len(chk_ste)>1:
				frappe.throw("More than 1 Stock Entry Exists for the Same GRN. ERROR!!!")
			else:
				name = chk_ste[0][0]
				ste_exist = frappe.get_doc("Stock Entry", name)
				ste_exist.submit()
				frappe.msgprint('{0}{1}'.format("Submitted STE# ", ste_exist.name))
		else:
			frappe.throw("No Stock Entry Found for this GRN")
	
def on_cancel(doc,method):
	chk = check_subpo(doc,method)
	if chk == 1:
		chk_ste = get_existing_ste(doc,method)
		if chk_ste:
			if len(chk_ste)>1:
				frappe.throw("More than 1 Stock Entry Exists for the Same GRN. ERROR!!!")
			else:
				name = chk_ste[0][0]
				ste_exist = frappe.get_doc("Stock Entry", name)
				ste_exist.cancel()
				frappe.msgprint('{0}{1}'.format("Cancelled STE# ", ste_exist.name))
		else:
			frappe.msgprint("No Stock Entry Found for this PO")

def on_update(doc,method):
	chk = check_subpo(doc,method)
	if chk == 1:
		create_ste(doc,method)
	
def create_ste(doc, method):
	ste_items = get_ste_items(doc,method)
	chk_ste = get_existing_ste(doc,method)
	if chk_ste:
		if len(chk_ste)>1:
			frappe.throw("More than 1 Stock Entry Exists for the Same GRN. ERROR!!!")
		else:
			ste_name = chk_ste[0][0]
			ste_exist = frappe.get_doc("Stock Entry", ste_name)
			ste_exist.items = []
			for i in ste_items:
				ste_exist.append("items", i)
			ste_exist.posting_date = doc.posting_date
			ste_exist.posting_time = doc.posting_time
			ste_exist.purpose = "Material Transfer"
			ste_exist.purchase_receipt_no = doc.name
			ste_exist.difference_account = "Stock Adjustment - RIGPL"
			ste_exist.remarks = "Material Transfer Entry for GRN#" + doc.name
			ste_exist.save()
			frappe.msgprint('{0}{1}'.format("Updated STE# ", ste_exist.name))
	else:
		ste = frappe.get_doc({
				"doctype": "Stock Entry",
				"purpose": "Material Transfer",
				"posting_date": doc.posting_date,
				"posting_time": doc.posting_time,
				"purchase_receipt_no": doc.name,
				"difference_account": "Stock Adjustment - RIGPL",
				"remarks": "Material Transfer Entry for GRN#" + doc.name,
				"items": ste_items
				})
		ste.insert()
		frappe.msgprint('{0}{1}'.format("Created STE# ", ste.name))

def get_ste_items(doc,method):
	ste_items = []
	source_warehouse = frappe.db.sql("""SELECT name FROM `tabWarehouse` 
		WHERE is_subcontracting_warehouse =1""", as_list=1)
	source_warehouse = source_warehouse[0][0]
	for d in doc.items:
		ste_temp = {}
		po = frappe.get_doc("Purchase Order", d.purchase_order)
		if po.is_subcontracting == 1:
			pod = frappe.get_doc("Purchase Order Item", d.purchase_order_item)
			ste_temp.setdefault("s_warehouse", source_warehouse)
			ste_temp.setdefault("t_warehouse", d.warehouse)
			ste_temp.setdefault("item_code", pod.subcontracted_item)
			item = frappe.get_doc("Item", pod.subcontracted_item)
			if d.stock_uom == item.stock_uom:
				ste_temp.setdefault("qty", d.qty)
			else:
				ste_temp.setdefault("qty", d.conversion_factor)
			ste_items.append(ste_temp)
	return ste_items
	
def get_existing_ste(doc,method):
	chk_ste = frappe.db.sql("""SELECT ste.name FROM `tabStock Entry` ste
		WHERE ste.docstatus <> 2 AND
		ste.purchase_receipt_no = '%s'"""% doc.name, as_list=1)
	return chk_ste

def check_subpo(doc,method):
	chk = 0
	for d in doc.items:
		po = frappe.get_doc("Purchase Order", d.purchase_order)
		if po.is_subcontracting == 1:
			chk = 1
	return chk

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
						vr = frappe.db.sql("""SELECT name FROM `tabValuation Rate` 
							WHERE item_code = '%s' AND disabled = 'No'""" %(d['name']), as_list=1)
						if doc.buying_price_list:
							bpl = doc.buying_price_list
						else:
							bpl = 'INR Buying PL'
						if vr:
							#Condition if the Valuation Rate exists then Update the same
							exist_vr = frappe.get_doc("Valuation Rate", vr[0][0])
							exist_vr.item_code = d['name']
							exist_vr.price_list = doc.buying_price_list
							exist_vr.valid_from = doc.posting_date
							exist_vr.disabled = 'No'
							exist_vr.valuation_rate = d['valuation']
							exist_vr.save(ignore_permissions=True)
							frappe.msgprint('Updated Valuation Rate #{0} for Item Code: {1}'.\
								format(exist_vr.name, d['name']))
						else:
							#Condition if there is NO Valuation Rate then create new
							new_vr = frappe.get_doc({
								"doctype": "Valuation Rate",
								"item_code": d['name'],
								"price_list": doc.buying_price_list,
								"valid_from": doc.posting_date,
								"disabled": "No",
								"valuation_rate": d['valuation'],
								})
							new_vr.insert(ignore_permissions=True)
							frappe.msgprint('Created Valuation Rate # {0} for Item Code: {1}'.\
								format(new_vr.name, d['name']))
		
def round_down(num, divisor):
    return num - (num%divisor)