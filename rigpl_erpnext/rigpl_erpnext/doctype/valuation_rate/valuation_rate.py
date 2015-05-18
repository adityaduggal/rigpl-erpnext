# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ValuationRate(Document):
	def validate(doc):
		query = """SELECT vr.name from `tabValuation Rate` vr where vr.disabled = 'No' and vr.item_code = '%s' """% (doc.item_code)
		list = frappe.db.sql(query, as_list=1)
		if list <> []:
			if len(list)>1:
				frappe.msgprint("Cannot more than 1 active valuation rates for one Item Code")
			elif len(list)==1:
				if list[0][0] <> doc.name:
					frappe.msgprint('{0}{1}{2}'.format("Valuation Rate ", list[0][0], " already active for same item code"), raise_exception=1)