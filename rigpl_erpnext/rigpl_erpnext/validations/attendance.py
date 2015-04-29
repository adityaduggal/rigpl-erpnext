# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	for att in doc.attendance_time:
		if att:
			frappe.msgprint(att.date_time)