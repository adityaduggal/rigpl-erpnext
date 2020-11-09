# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class RIGPLSettings(Document):
	def validate(self):
		weightage = self.sales_weightage + self.payment_weightage + self.age_weightage
		if weightage != 100:
			frappe.throw("Total Weightage Should be 100")
