# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time


def execute():
    variants = frappe.db.sql("""SELECT name FROM `tabItem` WHERE variant_of IS NOT NULL AND docstatus=0""", as_list=1)
    sno=0
    for d in variants:
        print("Checking Item Code = " + d[0])
        it_doc = frappe.get_doc("Item", d[0])
        for att in it_doc.attributes:
            attribute_num_value = frappe.get_value("Item Attribute", att.attribute, "numeric_values")
            if att.numeric_values != attribute_num_value:
                sno += 1
                frappe.db.set_value("Item Variant Attribute", att.name, "numeric_values", attribute_num_value)
                print("Updated Attribute's numeric field at row# " + str(att.idx) + " for Attribute = " +
                      att.attribute)
                if sno % 1000 == 0:
                    frappe.db.commit()
                    print("Committing Changes to Database")
                    time.sleep(2)