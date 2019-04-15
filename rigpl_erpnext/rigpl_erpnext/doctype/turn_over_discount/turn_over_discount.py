# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class TurnOverDiscount(Document):
	def validate(self):
		others = frappe.db.sql("""SELECT name, customer, fiscal_year FROM `tabTurn Over Discount` 
			WHERE docstatus != 2 AND customer = '%s' AND name <> '%s'
			AND fiscal_year = '%s'"""%(self.customer, self.fiscal_year, self.name), as_dict=1)
		if others:
			frappe.throw("Already TOD# {} exists for Customer {} \
				and FY: {}".format(others[0].name, others[0].customer, others[0].fiscal_year))