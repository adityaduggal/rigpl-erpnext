# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.utils import cstr
from datetime import datetime, timedelta

def validate(doc,method):
	if doc.lft:
		childs = frappe.db.sql("""SELECT name FROM `tabItem Group` 
			WHERE lft > %s AND rgt < %s""" % (doc.lft, doc.rgt), as_list=1)
		for i in childs:
			child = frappe.get_doc ("Item Group", i[0])
			child.save()