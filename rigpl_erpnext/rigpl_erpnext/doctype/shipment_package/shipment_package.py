# -*- coding: utf-8 -*-
# Copyright (c) 2018, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import math

class ShipmentPackage(Document):
	def validate(self):
		if self.uom == 'cm':
			volume = self.length * self.width * self.height
			if self.volumetric_factor > 0:
				vol_wt = volume/self.volumetric_factor
			else:
				frappe.throw("Volumetric Factor has to be greater than Zero")
			self.volumetric_weight_in_kgs = self.round_up_to_factor(vol_wt, 0.5)

	def round_up_to_factor(self, number, factor):
		rounded_number = math.ceil(number/factor) * factor
		return rounded_number
