# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import logging
import string
import datetime
import re
import json

import frappe.desk.form.meta
import frappe.desk.form.load
from frappe.utils import getdate, flt,validate_email_add, cint
from frappe.model.naming import make_autoname
from frappe import throw, _, msgprint
import frappe.permissions
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc

_logger = logging.getLogger(frappe.__name__)


@frappe.whitelist()
def create_todo(owner, assigned_by, description, date,reference_name,reference_type):
        """allow any logged user to post toDo via interaction master"""
        todo = frappe.new_doc("ToDo")
        todo.owner = owner
        todo.assigned_by = assigned_by
        todo.description = description
        todo.date = date
        todo.reference_type = reference_type
        todo.reference_name = reference_name
        todo.insert(ignore_permissions=True)

@frappe.whitelist()
def add_expense_claim(doc):
        doc_json=json.loads(doc)
        emp = frappe.db.get_value("Employee",{"user_id":doc_json['responsible']},"name")
        doc_json['employee'] = emp
        print "1111111111111111111111111"
        print emp
        print doc_json
        """allow any logged user to post a comment"""
        doc = frappe.get_doc(doc_json)

        if doc.doctype != "Expense Claim":
                frappe.throw(_("This method can only be used to create a Expense Claim"), frappe.PermissionError)

        doc.insert(ignore_permissions = True)

        return doc.as_dict()