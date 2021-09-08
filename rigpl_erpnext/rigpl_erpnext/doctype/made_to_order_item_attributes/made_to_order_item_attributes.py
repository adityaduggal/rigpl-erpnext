# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from ...utils.item_utils import check_numeric_attributes, check_text_attributes, get_item_attributes


class MadetoOrderItemAttributes(Document):
    def validate(self):
        self.validate_attribute_values()
        if self.reference_spl:
            self.reference_spl = ""
        other_specials = frappe.db.sql("""SELECT name FROM `tabMade to Order Item Attributes` WHERE sales_order =
        '%s' AND sales_order_item = '%s' AND item_code = '%s' AND name != '%s' AND docstatus != 2"""
                                       % (self.sales_order, self.sales_order_item, self.item_code, self.name),
                                       as_dict=1)
        if other_specials:
            frappe.throw("{} Already Exists".format(frappe.get_desk_link("Made to Order Item Attributes",
                                                                         other_specials[0].name)))
        for d in self.attributes:
            is_numeric = frappe.db.get_value("Item Attribute", d.attribute, "numeric_values")
            d.numeric_values = is_numeric

    def on_submit(self):
        if not self.attributes:
            frappe.throw("Attributes Table is mandatory for Submission")

    def copy_attributes_from_item(self):
        if self.reference_item_code:
            attributes = get_item_attributes(self.reference_item_code)
            self.set("attributes", [])
            self.set_attributes_in_table(attributes)
        else:
            frappe.throw("First Select a Reference Item Code")

    def copy_attributes_from_another_spl(self):
        if self.reference_spl:
            if self.reference_spl == self.name:
                frappe.throw("Cannot Select Name of Special Item Attribute as {}".format(self.name))
            else:
                query = """SELECT idx, name, attribute, attribute_value, numeric_values
                FROM `tabItem Variant Attribute`
                WHERE parent = '%s' AND parenttype= '%s'
                ORDER BY idx""" % (self.reference_spl, self.doctype)
                attributes = frappe.db.sql(query, as_dict=1)
                self.set("attributes", [])
                self.set_attributes_in_table(attributes)
        else:
            frappe.throw("First Select a Reference Special Item Attribute")

    def set_attributes_in_table(self, att_dict):
        if att_dict:
            for att in att_dict:
                cust_att = self.append('attributes', {})
                cust_att.attribute = att['attribute']
                cust_att.attribute_value = att['attribute_value']
                cust_att.numeric_values = att['numeric_values']
        else:
            frappe.throw("No Attributes defined for Selection")

    def validate_attribute_values(self):
        for att in self.attributes:
            att_doc = frappe.get_doc("Item Attribute", att.attribute)
            if att_doc.numeric_values == 1:
                # Check numeric values are Numeric only and within range of Attribute and within defined increment
                check_numeric_attributes(att_doc=att_doc, att_value=att.attribute_value)
            else:
                # Check text fields with matching case or else change it with guess work
                check_text_attributes(att_doc=att_doc, att_value=att.attribute_value)
