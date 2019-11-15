# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cstr, flt, cint, nowdate, add_days, comma_and
from frappe import msgprint, _


class CreateBulkProductionOrders(Document):
	def clear_table(self, table_name):
		self.set(table_name, [])

	def get_open_sales_orders(self):
		""" Pull sales orders  which are pending to deliver based on criteria selected"""
		so_filter = item_filter = ""
		if self.from_date:
			so_filter += " and so.transaction_date >= %(from_date)s"
		if self.to_date:
			so_filter += " and so.transaction_date <= %(to_date)s"
		if self.customer:
			so_filter += " and so.customer = %(customer)s"

		if self.item:
			item_filter += " and so_item.item_code = %(item)s"
		
		open_so = frappe.db.sql("""
			select distinct so.name, so.transaction_date, so.customer, so.base_grand_total
			from `tabSales Order` so, `tabSales Order Item` so_item
			where so_item.parent = so.name
				AND so.docstatus = 1 AND so.status != "Closed"
				AND so_item.qty > so_item.delivered_qty {0} {1}
			""".format(so_filter, item_filter), {
				"from_date": self.from_date,
				"to_date": self.to_date,
				"customer": self.customer,
				"item": self.item
			}, as_dict=1)

		self.add_so_in_table(open_so)

	def add_so_in_table(self, open_so):
		""" Add sales orders in the table"""
		self.clear_table("sales_orders")

		so_list = []
		for r in open_so:
			if cstr(r['name']) not in so_list:
				pp_so = self.append('sales_orders', {})
				pp_so.sales_order = r['name']
				pp_so.sales_order_date = cstr(r['transaction_date'])
				pp_so.customer = cstr(r['customer'])
				pp_so.grand_total = flt(r['base_grand_total'])
	
	def get_items(self):
		if self.get_items_from == "Sales Order":
			self.get_so_items()
	

	def get_so_items(self):
		so_list = [d.sales_order for d in self.get('sales_orders') if d.sales_order]
		if not so_list:
			msgprint(_("Please enter Sales Orders in the above table"))
			return []

		item_condition = ""
		if self.item:
			item_condition = ' AND sod.item_code = "{0}"'.format(frappe.db.escape(self.item))
		
		items = frappe.db.sql("""SELECT DISTINCT sod.parent, sod.item_code, sod.warehouse, sod.description,
			(sod.qty - sod.delivered_qty) as pending_qty, sod.name, (SELECT SUM(prd.qty) 
			FROM `tabWork Order` prd WHERE prd.so_detail = sod.name 
			AND prd.docstatus != 2 AND prd.status != "Stopped") as prd_qty
			from `tabSales Order Item` sod
			where sod.parent in (%s) AND sod.docstatus = 1 AND 
				sod.qty > sod.delivered_qty %s""" % \
			(", ".join(["%s"] * len(so_list)), item_condition), tuple(so_list), as_dict=1)

		self.add_items(items)

	def add_items(self, items):
		self.clear_table("items")
		for p in items:
			pend_prd = flt(p['pending_qty']) - flt(p['prd_qty'])
			if pend_prd > 0:
				item_details = self.get_item_details(p['item_code'])
				pi = self.append('items', {})
				pi.warehouse				= p['warehouse']
				pi.item_code				= p['item_code']
				pi.description				= p['description'] #item_details AND item_details.description or ''
				pi.stock_uom				= item_details and item_details.stock_uom or ''
				pi.bom_no					= item_details and item_details.bom_no or ''
				pi.planned_qty				= flt(p['pending_qty']) - flt(p['prd_qty'])
				pi.pending_qty				= flt(p['pending_qty'])
				pi.so_detail				= p['name']

				if self.get_items_from == "Sales Order":
					pi.sales_order		= p['parent']
			else:
				frappe.msgprint(("For SO# {0} \n Item Description: {1} \n \
				Work Orders have already been made hence this item is not included in the \
				Item List").format(p['parent'], p['description']))
				
	def get_item_details(self, item):
		res = frappe.db.sql("""select stock_uom, description
			from `tabItem` where disabled=0 and (end_of_life is null or end_of_life='0000-00-00' or end_of_life > %s)
			and name=%s""", (nowdate(), item), as_dict=1)
		if not res:
			return {}

		res = res[0]
		res["bom_no"] = frappe.db.get_value("BOM", filters={"item": item, "is_default": 1})
		if not res["bom_no"]:
			variant_of= frappe.db.get_value("Item", item, "variant_of")
			if variant_of:
				res["bom_no"] = frappe.db.get_value("BOM", filters={"item": variant_of, "is_default": 1})
		return res

	def raise_production_orders(self):
		"""It will raise production order (Draft) for all distinct Items"""
		self.validate_data()

		from erpnext.utilities.transaction_base import validate_uom_is_integer
		validate_uom_is_integer(self, "stock_uom", "planned_qty")

		items = self.get_production_items()

		pro_list = []
		for key in items:
			production_order = self.create_production_order(items[key])
			if production_order:
				pro_list.append(production_order)

		if pro_list:
			pro_list = ["""<a href="#Form/Work Order/%s" target="_blank">%s</a>""" % \
				(p, p) for p in pro_list]
			frappe.msgprint(_("{0} created").format(comma_and(pro_list)))
		else :
			frappe.msgprint(_("No Work Orders created"))

	def get_production_items(self):
		item_dict = {}
		for d in self.get("items"):
			item_details= {
				"production_item"		: d.item_code,
				"sales_order"			: d.sales_order,
				"material_request"		: d.material_request,
				"material_request_item"	: d.material_request_item,
				"description"			: d.description,
				"item_description"		: d.description,
				"rm_description"		: d.description,
				"stock_uom"				: d.stock_uom,
				"company"				: "RIGPL",
				"wip_warehouse"			: d.warehouse,
				"fg_warehouse"			: d.warehouse,
				"status"				: "Draft",
				"so_detail"				: d.so_detail,
				"qty"					: d.planned_qty
			}
			#frappe.throw(item_dict)
			""" Club similar BOM and item for processing in case of Sales Orders """
			if self.get_items_from == "Material Request":
				item_details.update({
					"qty": d.planned_qty
				})
				item_dict[(d.item_code, d.material_request_item, d.warehouse)] = item_details

			else:
				item_details.update({
					"qty":flt(item_dict.get((d.item_code, d.so_detail, d.warehouse),{})
						.get("qty")) + flt(d.planned_qty)
				})
				item_dict[(d.item_code, d.so_detail, d.warehouse)] = item_details

		return item_dict

	def create_production_order(self, item_dict):
		#Create production order. Called from Production Planning Tool
		from erpnext.manufacturing.doctype.work_order.work_order import OverProductionError, get_default_warehouse
		warehouse = get_default_warehouse()
		pro = frappe.new_doc("Work Order")
		pro.update(item_dict)

		try:
			pro.insert()
			return pro.name
		except OverProductionError:
			pass

	def validate_data(self):
		for d in self.get('items'):
			if not flt(d.planned_qty):
				frappe.throw(_("Please enter Planned Qty for Item {0} at row {1}").format(d.item_code, d.idx))
			#if d.work_order:
			#	frappe.throw(_("Work Order # {} already created for Row# {}").format(d.work_order, d.idx))