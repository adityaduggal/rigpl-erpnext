from __future__ import unicode_literals
import frappe
from datetime import datetime
from frappe.utils import flt

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	item_map = get_item_details(filters)
	iwb_map = get_item_warehouse_map(filters)
	pl_map = get_pl_map(filters)
	value_map = get_value_map(filters)

	data = []
	for item in sorted(iwb_map):
		for wh in sorted(iwb_map[item]):
			qty_dict = iwb_map[item][wh]
			data.append([item,item_map[item]["description"], wh,
			qty_dict.bal_qty,
			pl_map.get(item,{}).get("price_list_rate"),
			qty_dict.val_rate,
			qty_dict.value,
			item_map[item]["base_material"],
			item_map[item]["quality"], item_map[item]["tool_type"],
			item_map[item]["height_dia"], item_map[item]["width"],
			item_map[item]["length"], item_map[item]["d1"],
			item_map[item]["l1"], item_map[item]["is_rm"],
			item_map[item]["brand"],
			value_map.get(item,{}).get("valuation_rate")
			])

	return columns, data

def get_columns(filters):
	"""return columns based on filters"""

	columns = ["Item:Link/Item:150"] + ["Description::350"] + \
	["Warehouse:Link/Warehouse:100"] + ["Quantity:Float:60"] + ["List Price:Currency:80"] + \
	["VR:Currency:80"] + ["Value:Currency:100"] + \
	["BM::80"] + ["Qual::80"] +["TT::80"] + ["H:Float:50"] + \
	["W:Float:50"] + ["L:Float:50"] + ["D1:Float:50"] + \
	["L1:Float:50"] + ["Is RM::50"] + ["Brand::60"] + ["Set Value:Currency:80"]

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
		frappe.msgprint("Please Enter Valuation Date", raise_exception=1)

	if filters.get("pl") is None:
		frappe.msgprint("Please select a Price List for Valuation Purposes", raise_exception=1)

	return conditions

#get all details
def get_stock_ledger_entries(filters):
	conditions = get_conditions(filters)
	return frappe.db.sql("""select item_code, warehouse,
		posting_date, actual_qty ,valuation_rate, stock_value
		from `tabStock Ledger Entry`
		where ifnull(is_cancelled, 'No') = 'No' %s order by posting_date, posting_time, item_code, warehouse""" %
		conditions, as_dict=1)

def get_item_warehouse_map(filters):
	sle = get_stock_ledger_entries(filters)
	iwb_map = {}
	filters["date"] = datetime.strptime(filters["date"], '%Y-%m-%d').date()
	for d in sle:
		iwb_map.setdefault(d.item_code, {}).setdefault(d.warehouse, frappe._dict({\
				"opening_qty": 0.0, "in_qty": 0.0, "out_qty": 0.0, "bal_qty": 0.0, "val_rate":0.0, "value":0.0
			}))
		qty_dict = iwb_map[d.item_code][d.warehouse]
		if d.posting_date <= filters["date"]:
			qty_dict.opening_qty += flt(d.actual_qty)
			qty_dict.val_rate = flt(d.valuation_rate)
			qty_dict.value = flt(d.stock_value)
		elif d.posting_date > filters["date"].date():
			if flt(d.actual_qty) > 0:
				qty_dict.in_qty += flt(d.actual_qty)
			else:
				qty_dict.out_qty += abs(flt(d.actual_qty))

		qty_dict.bal_qty += flt(d.actual_qty)
	return iwb_map

def get_item_details(filters):

	item_map = {}
	for d in frappe.db.sql("select name, description, base_material, \
		quality, tool_type, height_dia, width, length, d1, l1, is_rm, \
		brand from tabItem", as_dict=1):
		item_map.setdefault(d.name, d)

	return item_map

def get_pl_map(filters):
	if filters.get("pl"):
		conditions = " and price_list = '%s'" % filters["pl"]
	else:
		frappe.msgprint("Please select a Price List for Valuation Purposes", raise_exception=1)

	pl_map_int = frappe.db.sql ("""SELECT it.name, p.price_list, p.price_list_rate
		FROM `tabItem` it, `tabItem Price` p
		WHERE p.item_code = it.name %s
		ORDER BY it.name""" % conditions, as_dict=1)
	pl_map={}

	for d in pl_map_int:
		pl_map.setdefault(d.name,d)
	return pl_map

def get_value_map(filter):
	value_map_int = frappe.db.sql ("""SELECT it.name, v.price_list, v.valuation_rate
	FROM `tabItem` it, `tabValuation Rate` v
	WHERE v.item_code = it.name and  v.disabled = "No"
	ORDER BY it.name""", as_dict=1)
	value_map={}
	for d in value_map_int:
		value_map.setdefault(d.name,d)
	return value_map