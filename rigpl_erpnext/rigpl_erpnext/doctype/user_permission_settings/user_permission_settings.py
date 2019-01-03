# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class UserPermissionSettings(Document):
	def validate(self):
		for rule in self.rules:
			if rule.role:
				if rule.apply_to_all_roles == 1:
					rule.apply_to_all_roles = 0
					frappe.msgprint("Removed Apply to All Role in Row# {} as \
						there is Role {} Mentioned".format(rule.idx, rule.role))

			if rule.allow_doctype_value:
				if rule.apply_to_all_values == 1:
					rule.apply_to_all_values = 0
					frappe.msgprint("Removed Apply to Values in Row# {} as \
						there is a {} Value {} Mentioned".\
						format(rule.idx, rule.allow_doctype, rule.allow_doctype_value))

			if rule.applicable_for_doctype:
				if rule.apply_to_all_doctypes == 1:
					rule.apply_to_all_doctypes = 0
					frappe.msgprint("Removed Apply to All Doctypes in Row# {} as \
						there is a {} Value Mentioned".\
						format(rule.idx, rule.applicable_for_doctype))