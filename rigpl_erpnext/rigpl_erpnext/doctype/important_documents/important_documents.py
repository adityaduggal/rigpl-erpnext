# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from datetime import datetime
from frappe.model.naming import getseries, get_default_naming_series
from rohit_common.utils.rohit_common_utils import fn_check_digit
from frappe.model.document import Document
from frappe.utils import cstr, formatdate, strip_html

from rigpl_erpnext.utils.attribute_query import QUERY_ATTRIBUTES, search_attribute_values


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
        chk_digit = fn_check_digit(pref)
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
        return frappe.get_all("File", filters={"attached_to_doctype": self.doctype, "attached_to_name": self.name},
            fields=["name", "attached_to_doctype", "attached_to_name", "is_private", "file_name"])

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


# The form cannot use add_fetch for links to child tables: v13 refuses the read, also for Administrator
@frappe.whitelist()
def get_sales_order_item_values(sales_order_item):
    row = frappe.db.get_value("Sales Order Item", cstr(sales_order_item),
        ["parent", "item_code", "description"], as_dict=True)
    if not row or not frappe.get_list("Sales Order", filters={"name": row.parent}):
        raise frappe.PermissionError
    return {"item": row.item_code, "description": row.description}


@frappe.whitelist()
def get_category_name(category):
    return frappe.db.get_value("Item Attribute Value",
        {"name": cstr(category), "parent": ("in", QUERY_ATTRIBUTES["tt"])}, "attribute_value")


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def sales_order_query(doctype, txt, searchfield, start, page_len, filters):
    like = "%{}%".format(cstr(txt))
    orders = frappe.get_list("Sales Order", filters={"docstatus": 1},
        or_filters={field: ("like", like) for field in ("name", "customer", "customer_name")},
        fields=["name", "transaction_date", "customer_name"], order_by="transaction_date desc, name desc",
        limit_start=start, limit_page_length=page_len)
    return [(d.name, formatdate(d.transaction_date), d.customer_name) for d in orders]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def sales_order_item_query(doctype, txt, searchfield, start, page_len, filters):
    order = (filters or {}).get("sales_order")
    # Sales Order Item has no permissions of its own
    if not isinstance(order, str) or not frappe.get_list("Sales Order", filters={"name": order}):
        return []
    like = "%{}%".format(cstr(txt))
    items = frappe.get_all("Sales Order Item", filters={"parent": order, "parenttype": "Sales Order"},
        or_filters={field: ("like", like) for field in ("item_code", "description")},
        fields=["name", "idx", "item_code", "description"], order_by="idx",
        limit_start=start, limit_page_length=page_len)
    return [(d.name, "#{} {}".format(d.idx, d.item_code), strip_html(cstr(d.description))) for d in items]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def category_query(doctype, txt, searchfield, start, page_len, filters):
    return search_attribute_values(QUERY_ATTRIBUTES["tt"], txt, start, page_len,
        extra_columns=("abbr", "long_description"))
