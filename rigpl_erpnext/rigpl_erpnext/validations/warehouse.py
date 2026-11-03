# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def validate(doc, method):
    if doc.is_subcontracting_warehouse == 1:
        # Allow only 1 Subcontracting Warehouse in System
        other_subcontracting_warehouse = frappe.db.get_value("Warehouse", {"docstatus": 0,
            "is_subcontracting_warehouse": 1, "name": ("!=", doc.name)})
        if other_subcontracting_warehouse:
            frappe.throw(("Warehouse {0} already allotted as Subcontracting Warehouse and only 1 Subcontracting "
                          "Warehouse is Allowed").format(other_subcontracting_warehouse))
    if doc.is_group == 0:
        if not doc.warehouse_type:
            frappe.throw("Type of Warehouse is Mandatory for {}".format(doc.name))
        other_serial = frappe.db.get_value("Warehouse", {"docstatus": 0, "is_group": 0, "name": ("!=", doc.name),
            "listing_serial": doc.listing_serial})
        if other_serial:
            frappe.throw(
                "Listing Serial: {} already Assigned to Warehouse {}".format(doc.listing_serial, other_serial))

        if doc.short_code:
            oth_short_code = frappe.db.get_value("Warehouse", {"docstatus": 0, "is_group": 0,
                "name": ("!=", doc.name), "short_code": doc.short_code})
            if oth_short_code:
                frappe.throw(
                    "Short Code: {} already Assigned to Warehouse {}".format(doc.short_code, oth_short_code))
        else:
            frappe.throw("Short Code is Mandatory for {}".format(doc.name))
