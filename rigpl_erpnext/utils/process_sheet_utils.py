# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe


def get_produced_qty(item_code, so_item=None):
    it_doc = frappe.get_doc("Item", item_code)
    if it_doc.include_item_in_manufacturing == 1:
        if it_doc.made_to_order == 1:
            if not so_item:
                frappe.throw("{} is Made to Order but No SO is defined".format(frappe.get_desk_link("Item", item_code)))
            else:
                qty_list = frappe.db.sql("""SELECT name, quantity, produced_qty FROM `tabProcess Sheet`
                    WHERE docstatus < 2 AND production_item = '%s' 
                    AND sales_order_item = '%s'""" % (item_code, so_item), as_dict=1)
                prod_qty = 0
                if qty_list:
                    for qty in qty_list:
                        prod_qty += qty.quantity
        else:
            qty_list = frappe.db.sql("""SELECT name, quantity , produced_qty FROM `tabProcess Sheet`
                WHERE docstatus < 2 AND production_item = '%s' """ % item_code, as_dict=1)
            prod_qty = 0
            if qty_list:
                for qty in qty_list:
                    prod_qty += qty.quantity
    return prod_qty
