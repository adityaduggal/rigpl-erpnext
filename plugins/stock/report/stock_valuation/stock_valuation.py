# ERPNext - web based ERP (http://erpnext.com)
# Copyright (C) 2012 Web Notes Technologies Pvt Ltd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals
import webnotes
from webnotes.utils import flt

def execute(filters=None):
	if not filters: filters = {}
	
	columns = get_columns(filters)
	item_map = get_item_details(filters)
	iwb_map = get_item_warehouse_map(filters)
	pl_map = get_pl_map(filters)
	purchase_map = get_purchase_map (filters)
	
	data = []
	for item in sorted(iwb_map):
		for wh in sorted(iwb_map[item]):
			#webnotes.msgprint(pl_map.get(item,0))
			qty_dict = iwb_map[item][wh]
			data.append([item,item_map[item]["description"], wh,
			qty_dict.bal_qty,pl_map.get(item,{}).get("ref_rate"),
			purchase_map.get(item,{}).get("purchase_rate"),
			0,
			item_map[item]["base_material"],
			item_map[item]["quality"], item_map[item]["tool_type"], 
			item_map[item]["height_dia"], item_map[item]["width"],
			item_map[item]["length"], item_map[item]["d1"],
			item_map[item]["l1"], item_map[item]["is_rm"],
			item_map[item]["brand"]
			])
	
	return columns, data

def get_columns(filters):
	"""return columns based on filters"""
	
	columns = ["Item:Link/Item:150"] + ["Description::350"] + \
	["Warehouse:Link/Warehouse:100"] + ["Quantity:Float/2:90"] + ["List Price:Currency:100"] + \
	["Last Purchase Price:Currency:100"] + ["Latest SP:Currency:100"] + \
	["BM::100"] + ["Qual::100"] +["TT::100"] + ["H:Float/3:70"] + \
	["W:Float/3:70"] + ["L:Float/3:70"] + ["D1:Float/3:70"] + \
	["L1:Float/3:70"] + ["Is RM::100"] + ["Brand::100"]

	return columns

def get_conditions(filters):
	conditions = ""
	if filters.get("item_code"):
		conditions += " and item_code='%s'" % filters["item_code"]

	if filters.get("warehouse"):
		conditions += " and warehouse='%s'" % filters["warehouse"]

	if filters.get("date"):
		conditions += " and posting_date <= '%s'" % filters["date"]
	else:
		webnotes.msgprint("Please Enter Valuation Date", raise_exception=1)
		
	return conditions

#get all details
def get_stock_ledger_entries(filters):
	conditions = get_conditions(filters)
	return webnotes.conn.sql("""select item_code, warehouse, 
		posting_date, actual_qty 
		from `tabStock Ledger Entry` 
		where ifnull(is_cancelled, 'No') = 'No' %s order by item_code, warehouse""" %
		conditions, as_dict=1)

def get_item_warehouse_map(filters):
	sle = get_stock_ledger_entries(filters)
	iwb_map = {}

	for d in sle:
		iwb_map.setdefault(d.item_code, {}).setdefault(d.warehouse, webnotes._dict({\
				"opening_qty": 0.0, "in_qty": 0.0, "out_qty": 0.0, "bal_qty": 0.0
			}))
		qty_dict = iwb_map[d.item_code][d.warehouse]
		if d.posting_date < filters["date"]:
			qty_dict.opening_qty += flt(d.actual_qty)
		elif d.posting_date >= filters["date"]:
			if flt(d.actual_qty) > 0:
				qty_dict.in_qty += flt(d.actual_qty)
			else:
				qty_dict.out_qty += abs(flt(d.actual_qty))

		qty_dict.bal_qty += flt(d.actual_qty)

	return iwb_map

def get_item_details(filters):

	item_map = {}
	for d in webnotes.conn.sql("select name, description, base_material, \
		quality, tool_type, height_dia, width, length, d1, l1, is_rm, \
		brand from tabItem", as_dict=1):
		item_map.setdefault(d.name, d)
	
	return item_map
	
def get_pl_map(filters):
	if filters.get("pl"):
		conditions = " and price_list_name = '%s'" % filters["pl"]
	else:
		webnotes.msgprint("Please select a Price List for Valuation Purposes", raise_exception=1)
	
	pl_map_int = webnotes.conn.sql ("""SELECT it.name, p.price_list, p.ref_rate
		FROM `tabItem` it, `tabItem Price` p
		WHERE p.parent = it.name %s
		ORDER BY it.name""" % conditions, as_dict=1)
	pl_map={}
	
	for d in pl_map_int:
		pl_map.setdefault(d.name,d)
	return pl_map
	
def get_purchase_map(filters):
	conditions = ""
	if filters.get("item_code"):
		conditions += " and prd.item_code = '%s'" % filters["item_code"]
	
	if filters.get("date"):
		conditions += " and pr.posting_date <= '%s'" % filters ["date"]
	
	purchase_map_int = webnotes.conn.sql ("""SELECT prd.item_code, prd.purchase_rate , max(pr.posting_date)
		FROM `tabPurchase Receipt` pr, `tabPurchase Receipt Item` prd
		WHERE prd.parent = pr.name 
		AND pr.docstatus = 1 %s
		GROUP BY prd.item_code
		ORDER BY prd.item_code, pr.posting_date desc""" % conditions , as_dict=1)
	purchase_map={}
	
	for d in purchase_map_int:
		purchase_map.setdefault(d.name,d)
	#webnotes.msgprint(purchase_map_int)
	return purchase_map