# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from datetime import datetime
from frappe.model.naming import getseries, get_default_naming_series
from rohit_common.utils.file_checks import check_attachments
from rohit_common.utils.file_rules import get_matching_rule
from rohit_common.utils.rohit_common_utils import fn_check_digit
from frappe.model.document import Document
from frappe.utils import cint, cstr, formatdate, strip_html

from rigpl_erpnext.utils.attribute_query import QUERY_ATTRIBUTES, search_attribute_values

NEW_RULE_LINK = '<a href="/app/file-attachment-rule/new-file-attachment-rule-1">New File Attachment Rule</a>'


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
        if self.docstatus == 0:
            self.warn_attachments()

    def before_submit(self):
        # rohit_common checks the files in its own before_submit hook
        if not get_matching_rule(self):
            frappe.throw(get_no_rule_message(self), title="No Attachment Rule")

    def warn_attachments(self):
        """A draft always saves. The same problems stop the submit."""
        message_count = len(frappe.local.message_log)
        try:
            if get_matching_rule(self):
                check_attachments(self)
                return
            warning, title = get_no_rule_message(self), "No Attachment Rule"
        except frappe.ValidationError as error:
            # Remove the red message of the throw
            del frappe.local.message_log[message_count:]
            warning, title = str(error), "Attachments Not Ready"
        frappe.msgprint(warning, title=title, indicator="orange")

    def validate_fields(self):
        if self.item:
            has_variants = frappe.db.get_value("Item", self.item, "has_variants")
            if self.template != has_variants:
                frappe.throw("Item: {} has_variants = {} but here template = {}".format(self.item,
                                                                                has_variants, self.template))

    def update_fields(self):
        if self.category:
            self.category_name = frappe.db.get_value("Item Attribute Value", self.category, "attribute_value")
        if self.sales_order:
            self.customer = frappe.db.get_value("Sales Order", self.sales_order, "customer")
        self.set_item_values()
        self.check_standard_year()
        self.set_title()

    def set_item_values(self):
        """A Sales Order Item has its own description. It wins over the Item description."""
        if self.sales_order_item:
            self.item, description = frappe.db.get_value("Sales Order Item", self.sales_order_item,
                ["item_code", "description"])
        elif self.item:
            description = frappe.db.get_value("Item", self.item, "description")
        else:
            return
        # description is a Data field: plain text, 140 characters
        self.description = strip_html(cstr(description))[:140]

    def check_standard_year(self):
        this_year = datetime.now().year
        if cint(self.standard_year) and not 1900 <= cint(self.standard_year) <= this_year:
            frappe.throw("Standard Year must be from 1900 to {}, not {}".format(this_year, self.standard_year))

    def set_title(self):
        if self.type == 'Standard':
            parts = ['STD', self.standard_authority, self.standard_number, self.standard_year, self.description]
        else:
            parts = ['DWG', self.drawing_based_on, self.customer, self.sales_order, self.item]
        self.title = ": ".join(cstr(part) for part in parts if part)[:140]


def get_no_rule_message(doc):
    return ("No File Attachment Rule applies to this {0}. You cannot submit it until a rule exists. "
            "Make one, or ask a System Manager: {1}").format(doc.type, NEW_RULE_LINK)


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
