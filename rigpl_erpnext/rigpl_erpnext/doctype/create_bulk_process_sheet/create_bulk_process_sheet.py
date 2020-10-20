# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, comma_and
from ....utils.manufacturing_utils import get_produced_qty


class CreateBulkProcessSheet(Document):
    def clear_table(self, table_name):
        self.set(table_name, [])

    def clear_all_tables(self):
        tables = ["sales_orders", "items"]
        for d in tables:
            self.clear_table(d)

    def get_open_sales_orders(self):
        """ Pull sales orders  which are pending to deliver based on criteria selected"""
        so_filter = item_filter = ""
        if self.sales_order:
            so_filter += " AND so.name = '%s'" % self.sales_order
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
        self.clear_all_tables()
        for r in open_so:
            it_doc = frappe.get_doc("Item", r["item_code"])
            pp_so = self.append('sales_orders', {})
            pp_so.sales_order = r['name']
            pp_so.sales_order_date = cstr(r['transaction_date'])
            pp_so.customer = cstr(r['customer'])

            # Update Item Table
            if it_doc.include_item_in_manufacturing == 1 and it_doc.made_to_order == 1:
                ppit_so = self.append("items", {})
                ppit_so.item_code = r['item_code']
                ppit_so.description = r['description']
                ppit_so.planned_qty = r['pend_qty']
                ppit_so.pending_qty = r['pend_qty']
                ppit_so.ordered_qty = r['qty']
                ppit_so.sales_order = r['name']
                ppit_so.sales_order_item = r['soi_name']

    def raise_process_sheet(self):
        # It will raise Process Sheet (Draft) for all distinct Items
        items = self.get_production_items()
        pro_list = []
        for item in items:
            process_sheet = self.create_process_sheet(item)
            if process_sheet:
                pro_list.append(process_sheet)

        if pro_list:
            pro_list = ["""<a href="#Form/Process Sheet/%s" target="_blank">%s</a>""" % \
                        (p, p) for p in pro_list]
            frappe.msgprint(_("{0} created").format(comma_and(pro_list)))
            self.clear_all_tables()
        else:
            frappe.msgprint(_("No Process Sheet created"))

    def get_production_items(self):
        item_details = []
        for d in self.get("items"):
            if d.planned_qty > d.pending_qty:
                frappe.throw("For Row # {} in Items Table the Planned Quantity is Greater than Pending Qty".
                             format(d.idx))
            produced_qty = get_produced_qty(d.item_code, d.sales_order_item)
            pend_qty_to_manuf = d.planned_qty - produced_qty
            if d.planned_qty > pend_qty_to_manuf:
                frappe.throw("For Row # {} in Items Table the Planned Qty is Greater than Items Needed to be Produced {}".
                             format(d.idx, pend_qty_to_manuf))
            item_dict = {
                "production_item"   : d.item_code,
                "sales_order"		: d.sales_order,
                "description"		: d.description,
                "status"			: "Draft",
                "sales_order_item"	: d.sales_order_item,
                "quantity"				: d.planned_qty
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

@frappe.whitelist()
def get_so_pending_for_process_sheet(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
    """ Pull sales orders  which are pending to deliver based on criteria selected"""

    query = """SELECT so.name, so.transaction_date, so.customer, soi.item_code, soi.description, soi.qty, 
    soi.delivered_qty, soi.name as soi_name, soi.qty - soi.delivered_qty as pend_qty 
    FROM `tabSales Order` so, `tabSales Order Item` soi 
    WHERE soi.parent = so.name AND so.docstatus = 1 AND so.status != "Closed" 
    AND soi.qty > soi.delivered_qty AND so.name LIKE {txt}
    ORDER BY so.transaction_date, so.name""".format(txt=frappe.db.escape('%{0}%'.format(txt)))
    #frappe.msgprint(query)
    return frappe.db.sql(query, as_dict=as_dict)
