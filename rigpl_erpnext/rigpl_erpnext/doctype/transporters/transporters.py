# Copyright (c) 2013, Rohit Industries Ltd.
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class Transporters(Document):
	def validate(self):
		if self.fedex_credentials == 1:
			self.track_on_shipway = 0
			self.fedex_tracking_only = 0
		elif self.track_on_shipway == 1:
			self.fedex_tracking_only = 0
			self.fedex_credentials = 0
		elif self.fedex_tracking_only == 1:
			self.track_on_shipway = 0
			self.fedex_credentials = 0