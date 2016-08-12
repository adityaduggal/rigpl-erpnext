# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	if not filters: filters = {}
	conditions, cond_dep = get_conditions(filters)
	columns = get_columns()
	assets = get_assets(conditions)
	acc_dep = get_acc_dep(assets, cond_dep)
	data = []
	for a in assets:
		open_dep = a.opening_accumulated_depreciation
		purchase = a.gross_purchase_amount
		row = [a.name, a.item_code, a.asset_category, a.warehouse, a.model, a.manufacturer, \
			a.description, a.purchase_date, purchase, \
			a.total_number_of_depreciations, open_dep]
		check = 0
		for acc in acc_dep:
			if acc.parent == a.name:
				total_dep = round(acc.dep,2)
				row += [total_dep]
				check = 1
		if check == 0:
			total_dep = open_dep
			row += [total_dep]
		row += [(total_dep - open_dep), (purchase - total_dep), a.salvage, a.fixed_asset_account]
		

		data.append(row)
	return columns, data

def get_columns():
	return [
		"Asset:Link/Asset:150", "Item:Link/Item:150", "AssetCategory:Link/Asset Category:150",
		"Warehouse::150", "Model::150", "Manufacturer::150", "Description::250",
		"Purchase Date:Date:80", "Gross Purchase Amt:Currency:100", "# Dep:Int:60", 
		"Op Dep:Currency:100", "Total Depreciation:Currency:100", "Period Dep:Currency:100",
		"Net Block:Currency:100", "Salvage Value:Currency:100", "Account:Link/Account:200"
	]
	
def get_assets(conditions):
	query = """SELECT ass.name, ass.item_code, ass.asset_category, ass.warehouse, ass.model,
		ass.manufacturer, ass.description, ass.purchase_date, ass.gross_purchase_amount, 
		ass.opening_accumulated_depreciation, ass.expected_value_after_useful_life AS salvage, 
		ass.total_number_of_depreciations, as_cat_acc.fixed_asset_account
		FROM `tabAsset` ass, `tabAsset Category` as_cat, `tabAsset Category Account` as_cat_acc
		WHERE ass.docstatus = 1 AND ass.asset_category = as_cat.name AND 
			as_cat_acc.parent = as_cat.name %s
		ORDER BY ass.purchase_date DESC, ass.asset_category""" %(conditions)
	
	assets = frappe.db.sql(query, as_dict = 1)
	return assets

def get_acc_dep(asset, cond_dep):
	acc_dep = frappe.db.sql("""SELECT MAX(ds.accumulated_depreciation_amount) as dep,
		ds.parent, SUM(ds.depreciation_amount) as monthly
		FROM `tabDepreciation Schedule` ds
		WHERE ds.docstatus = 1 {condition} AND ds.parent IN (%s)
		GROUP BY ds.parent""".format(condition = cond_dep) % 
		(', '.join(['%s']*len(asset))), tuple([d.name for d in asset]), as_dict=1)
	
	return acc_dep
	
def get_conditions(filters):
	conditions = ""
	cond_dep = ""
	
	if filters.get("from_date"):
		if filters["from_date"] > filters["to_date"]:
			frappe.throw("From Date cannot be greater than To Date")
		cond_dep += "AND ds.schedule_date >= '%s'"% filters["from_date"]
	
	if filters.get("to_date"):
		conditions += "AND ass.purchase_date <= '%s'" % filters["to_date"]
		cond_dep += "AND ds.schedule_date <= '%s'"% filters["to_date"]
		
	if filters.get("asset_category"):
		conditions += "AND ass.asset_category = '%s'" % filters["asset_category"]
		
	if filters.get("asset"):
		conditions += "AND ass.name = '%s'" % filters["asset"]
		
	if filters.get("account"):
		conditions += "AND as_cat_acc.fixed_asset_account = '%s'" % filters["account"]
		
		
	return conditions, cond_dep