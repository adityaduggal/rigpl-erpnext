# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document

from ....utils.item_attribute_utils import get_attribute_rows
from ....utils.item_utils import (
    check_numeric_attributes,
    check_text_attributes,
    get_item_attributes,
)


class MadetoOrderItemAttributes(Document):
    def validate(self):
        self.validate_attribute_values()
        if self.reference_spl:
            self.reference_spl = ""
        other_special = frappe.db.get_value(
            self.doctype,
            {
                "sales_order": self.sales_order,
                "sales_order_item": self.sales_order_item,
                "item_code": self.item_code,
                "name": ("!=", self.name),
                "docstatus": ("!=", 2),
            },
        )
        if other_special:
            frappe.throw(
                "{} Already Exists".format(
                    frappe.get_desk_link("Made to Order Item Attributes", other_special)
                )
            )
        for d in self.attributes:
            is_numeric = frappe.db.get_value(
                "Item Attribute", d.attribute, "numeric_values"
            )
            d.numeric_values = is_numeric

    def on_submit(self):
        if not self.attributes:
            frappe.throw("Attributes Table is mandatory for Submission")

    @frappe.whitelist()
    def copy_attributes_from_item(self):
        if self.reference_item_code:
            attributes = get_item_attributes(self.reference_item_code)
            self.set("attributes", [])
            self.set_attributes_in_table(attributes)
        else:
            frappe.throw("First Select a Reference Item Code")

    @frappe.whitelist()
    def copy_attributes_from_another_spl(self):
        if self.reference_spl:
            if self.reference_spl == self.name:
                frappe.throw(
                    "Cannot Select Name of Special Item Attribute as {}".format(
                        self.name
                    )
                )
            else:
                attributes = get_attribute_rows(
                    [self.reference_spl], parenttype=self.doctype
                ).get(self.reference_spl, [])
                self.set("attributes", [])
                self.set_attributes_in_table(attributes)
        else:
            frappe.throw("First Select a Reference Special Item Attribute")

    def set_attributes_in_table(self, att_dict):
        if att_dict:
            for att in att_dict:
                cust_att = self.append("attributes", {})
                cust_att.attribute = att["attribute"]
                cust_att.attribute_value = att["attribute_value"]
                cust_att.numeric_values = att["numeric_values"]
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
