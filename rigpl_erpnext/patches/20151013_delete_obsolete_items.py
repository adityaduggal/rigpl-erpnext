# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def execute():
	obs_items = frappe.db.sql("""
		SELECT it.name, ifnull(it.owner, "Administrator"), it.creation
		FROM `tabItem` it
		WHERE 
			it.variant_of IS NULL
			AND it.has_variants != 1

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
			
			AND ifnull((SELECT count(sod.name) FROM `tabWork Order` sod 
				WHERE sod.production_item = it.name GROUP BY sod.production_item),0) = 0
		ORDER BY it.owner, it.creation""", 
			as_list = 1)
	print ("Total Items Deleted= " + len(obs_items))