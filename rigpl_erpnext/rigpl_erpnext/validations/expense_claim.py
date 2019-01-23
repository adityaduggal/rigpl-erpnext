# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	doc.deparment = frappe.get_value("Employee", doc.employee, "department")