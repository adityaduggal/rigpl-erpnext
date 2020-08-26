# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cstr, flt, nowdate, comma_and
from frappe import msgprint, _


class CreateBulkProcessSheet(Document):
    def clear_table(self, table_name):
        self.set(table_name, [])

    def get_open_sales_orders(self):
        """ Pull sales orders  which are pending to deliver based on criteria selected"""
        so_filter = item_filter = ""
        if self.from_date:
            so_filter += " AND so.transaction_date >= '%s'" % self.from_date
        if self.to_date:
            so_filter += " AND so.transaction_date <= '%s'" % self.to_date
        if self.customer:
            so_filter += " AND so.customer = '%s'" % self.customer

        if self.item:
            item_filter += " AND soi.item_code = '%s'" % self.item

        query = """SELECT so.name, so.transaction_date, so.customer, soi.item_code, soi.description, soi.qty, 
        soi.delivered_qty, soi.name as soi_name, soi.qty - soi.delivered_qty as pend_qty 
        FROM `tabSales Order` so, `tabSales Order Item` soi 
        WHERE soi.parent = so.name AND so.docstatus = 1 AND so.status != "Closed" 
        AND soi.qty > soi.delivered_qty %s %s ORDER BY so.transaction_date, so.name""" % (so_filter, item_filter)
        open_so = frappe.db.sql(query, as_dict=1)
        self.add_so_in_table(open_so)

    def add_so_in_table(self, open_so):
        """ Add sales orders in the table"""
        self.clear_table("sales_orders")
        so_list = []
        for r in open_so:
            if cstr(r['soi_name']) not in so_list:
                pp_so = self.append('sales_orders', {})
                pp_so.sales_order = r['name']
                pp_so.sales_order_date = cstr(r['transaction_date'])
                pp_so.customer = cstr(r['customer'])
                pp_so.item_code = r['item_code']
                pp_so.description = r['description']
                pp_so.qty = r['pend_qty']
                pp_so.so_item = r['soi_name']

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
                pi.warehouse = p['warehouse']
                pi.item_code = p['item_code']
                pi.description = p['description']  # item_details AND item_details.description or ''
                pi.stock_uom = item_details and item_details.stock_uom or ''
                pi.bom_no = item_details and item_details.bom_no or ''
                pi.planned_qty = flt(p['pending_qty']) - flt(p['prd_qty'])
                pi.pending_qty = flt(p['pending_qty'])
                pi.so_detail = p['name']

                if self.get_items_from == "Sales Order":
                    pi.sales_order = p['parent']
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
            variant_of = frappe.db.get_value("Item", item, "variant_of")
            if variant_of:
                res["bom_no"] = frappe.db.get_value("BOM", filters={"item": variant_of, "is_default": 1})
        return res

    def raise_process_sheet(self):
        # It will raise Process Sheet (Draft) for all distinct Items

        items = self.get_production_items()
        pro_list = []
        for item in items:
            frappe.msgprint("hello")
            process_sheet = self.create_process_sheet(item)
            frappe.msgprint("hello2s")
            if process_sheet:
                pro_list.append(process_sheet)

        if pro_list:
            pro_list = ["""<a href="#Form/Process Sheet/%s" target="_blank">%s</a>""" % \
                        (p, p) for p in pro_list]
            frappe.msgprint(_("{0} created").format(comma_and(pro_list)))
        else:
            frappe.msgprint(_("No Process Sheet created"))

    def get_production_items(self):
        item_details = []
        for d in self.get("sales_orders"):
            item_dict = {
                "production_item"   : d.item_code,
                "sales_order"		: d.sales_order,
                "description"		: d.description,
                "status"			: "Draft",
                "sales_order_item"	: d.so_item,
                "quantity"				: d.qty
            }
            item_details.append(item_dict.copy())
        return item_details

    def create_process_sheet(self, item_dict):
        # Create Process Sheet called from Bulk Process Sheet Creation
        pro = frappe.new_doc("Process Sheet")
        pro.flags.ignore_mandatory = True
        pro.update(item_dict)

        try:
            pro.insert()
            return pro.name
        except:
            pass
