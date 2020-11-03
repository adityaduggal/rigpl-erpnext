# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from datetime import datetime
from frappe.model.naming import getseries, get_default_naming_series
from rohit_common.utils.rohit_common_utils import fn_check_digit
from frappe.model.document import Document


class ImportantDocuments(Document):
    def autoname(self):
        pref = ""
        if self.type == 'Standard':
            pref += 'STD'
        elif self.type == 'Drawing':
            pref += 'DWG'
        series = get_default_naming_series(self.doctype)
        digits = getseries(series, 3)
        pref += str(digits)
        chk_digit = fn_check_digit(self, pref)
        name = pref + str(chk_digit)
        self.name = name

    def validate(self):
        self.validate_fields()
        self.update_fields()
        if self.get("__is_local") == 1:
            pass
        else:
            self.validate_files()

    def on_submit(self):
        file_dict = self.get_files()
        if not file_dict:
            frappe.throw("Cannot Submit {} without Attachments".format(self.name))

    def validate_fields(self):
        if self.item:
            it_doc = frappe.get_doc('Item', self.item)
            if self.template != it_doc.has_variants:
                frappe.throw("Item: {} has_variants = {} but here template = {}".format(self.item,
                                                                                it_doc.has_variants, self.template))

    def validate_files(self):
        file_dict = self.get_files()
        if file_dict:
            self.check_total_files(file_dict)
            self.allow_only_private_files(file_dict)
            self.check_file_name(file_dict)

    def check_file_name(self, file_dict):
        if self.type == 'Standard':
            for d in file_dict:
                if d.file_name != (self.name + ".pdf"):
                    frappe.throw("Attached File Name {} is Wrong. Attach file with Name "
                                 "= {}.pdf".format(d.file_name, self.name))
        else:
            for d in file_dict:
                threed_file_name = (self.name + '-3D.FCStd')
                twod_file_name = (self.name + '-2D.pdf')
                if d.file_name not in [threed_file_name, twod_file_name]:
                    frappe.throw("Attached File Name is Wrong for {}. Attach 2 Files for Drawing 1 with Name = "
                                 "{}-2D.pdf and another with {}-3D.FCStd".format(d.file_name, self.name, self.name))

    def allow_only_private_files(self, file_dict):
        for d in file_dict:
            if d.is_private != 1:
                frappe.throw("File Name: {} - attached to {} is Public File, Please Delete and Re-Upload as "
                             "Private File".format(d.file_name, self.name))

    def check_total_files(self, file_dict):
        no_of_files = len(file_dict)
        if self.type == 'Drawing':
            if no_of_files != 2:
                frappe.throw("Attach 2 Files for Drawing 1 with Name = {}-2D.pdf and another "
                             "with {}-3D.FCStd".format(self.name, self.name))
        elif self.type == 'Standard':
            if no_of_files != 1:
                frappe.throw("Attach Only 1 File for Standard with Name = {}.pdf".format(self.name))

    def get_files(self):
        file_dict = frappe.db.sql("""SELECT name, attached_to_doctype, attached_to_name, is_private, file_name
        FROM `tabFile` WHERE attached_to_doctype = '%s' AND attached_to_name = '%s'""" % (self.doctype,
                                                                                          self.name), as_dict=1)
        return file_dict

    def update_fields(self):
        if self.category:
            self.category_name = frappe.db.get_value("Item Attribute Value", self.category, "attribute_value")
        if self.sales_order:
            self.customer = frappe.db.get_value("Sales Order", self.sales_order, "customer")
        if self.sales_order_item:
            self.item = frappe.db.get_value("Sales Order Item", self.sales_order_item, "item_code")
            self.description = frappe.db.get_value("Sales Order Item", self.sales_order_item, "description")

        if self.item:
            self.description = frappe.db.get_value("Item", self.item, "description")

        if self.standard_year:
            if self.standard_year > 0:
                if self.standard_year < 1900:
                    frappe.throw("{} is Not Allowed in Standard Year for {}".format(self.standard_year, self.name))
                elif self.standard_year > int(datetime.now().year):
                    frappe.throw("{} is Not Allowed in Standard Year for {}".format(self.standard_year, self.name))

        if self.type == 'Standard':
            title = 'STD: ' + self.standard_authority + ": " + str(self.standard_number)
            if self.standard_year:
                title += ": " + str(self.standard_year)
            title += ": " + self.description
            self.title = title[:140]
        elif self.type == 'Drawing':
            title = 'DWG: ' + self.drawing_based_on
            if self.customer:
                title += ": " + self.customer
            if self.sales_order:
                title += ": " + self.sales_order
            if self.item:
                title += ": " + self.item
            self.title = title[:140]
