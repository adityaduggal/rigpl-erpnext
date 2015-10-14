# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def execute():
	obs_items = frappe.db.sql("""
		SELECT it.name, ifnull(it.owner, "Administrator"), it.creation
		FROM `tabItem` it
		WHERE 
			it.base_material = 'HSS'
			AND it.pl_item = 'No'
			AND (it.tool_type = 'Round' OR it.tool_type = 'Punches')

			AND ifnull((SELECT count(sod.name) FROM `tabMaterial Request Item` sod WHERE sod.item_code = 
				it.name GROUP BY sod.item_code),0) = 0
			
			AND ifnull((SELECT count(sod.name) FROM `tabSupplier Quotation Item` sod WHERE sod.item_code = 
				it.name GROUP BY sod.item_code),0) = 0
			
			AND ifnull((SELECT count(sod.name) FROM `tabQuotation Item` sod WHERE sod.item_code = 
				it.name GROUP BY sod.item_code),0) = 0
			
			AND ifnull((SELECT count(sod.name) FROM `tabSales Order Item` sod WHERE sod.item_code = 
				it.name GROUP BY sod.item_code),0) = 0
			
			AND ifnull((SELECT count(sod.name) FROM `tabSales Invoice Item` sod 
				WHERE sod.item_code = it.name GROUP BY sod.item_code),0) = 0
			
			AND ifnull((SELECT count(sod.name) FROM `tabPurchase Order Item` sod 
				WHERE sod.item_code = it.name GROUP BY sod.item_code),0) = 0
			
			AND ifnull((SELECT count(sod.name) FROM `tabPurchase Invoice Item` sod 
				WHERE sod.item_code = it.name GROUP BY sod.item_code),0) = 0
			
			AND ifnull((SELECT count(sod.name) FROM `tabStock Ledger Entry` sod 
				WHERE sod.item_code = it.name GROUP BY sod.item_code),0) = 0
			
			AND ifnull((SELECT count(sod.name) FROM `tabStock Entry Detail` sod 
				WHERE sod.item_code = it.name GROUP BY sod.item_code),0) = 0
			
			AND ifnull((SELECT count(sod.name) FROM `tabStock Reconciliation Item` sod 
				WHERE sod.item_code = it.name GROUP BY sod.item_code),0) = 0
			
			AND ifnull((SELECT count(sod.name) FROM `tabProduction Order` sod 
				WHERE sod.production_item = it.name GROUP BY sod.production_item),0) = 0
		ORDER BY it.owner, it.creation""", 
			as_list = 1)
	j = 1
	for i in obs_items:
		vr = frappe.db.sql("""SELECT name FROM `tabValuation Rate` 
			WHERE item_code = '%s' """% i[0], as_list=1)
		if vr:
			for k in range(len(vr)):
				frappe.delete_doc_if_exists("Valuation Rate", vr[k][0])
				print "Deleted", vr[k][0]
		frappe.delete_doc_if_exists("Item", i[0])
		print "Row#", j, "Deleted Item", i[0], "which was Created By", i[1], "on", i[2]
		j += 1
	print "Total Items Deleted=", len(obs_items)