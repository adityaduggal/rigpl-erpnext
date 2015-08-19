# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc, method):
	if doc.variant_of:
		frappe.msgprint(doc.variant_of)
