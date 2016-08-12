# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
import re

def validate(doc,method):
	child_asset = frappe.db.sql("""SELECT ass.name FROM `tabAsset` ass
		WHERE ass.docstatus = 1 AND
		ass.asset_category = '%s'"""%(doc.name), as_list=1)
	
	if child_asset:
		frappe.throw(("Cannot Change this Asset Category as Asset {0} already \
			submitted").format(child_asset[0][0]))
	if len(doc.accounts) >1:
		frappe.throw("Only one account allowed per Asset Category")
		
	if len(doc.asset_short_name) <> 3:
		frappe.throw("Asset Short name should be EXACTLY THREE Characters long")
		
	if not re.match("^[A-H, J-N, P-Z, 0-9]*$", doc.asset_short_name):
		frappe.throw("Only numbers and letters except I and O are allowed in Asset Short Name")
	other_short_names = frappe.db.sql("""SELECT name, asset_short_name AS asn FROM `tabAsset Category`
		WHERE name <> '%s'"""%doc.name, as_dict = 1)
		
	for i in other_short_names:
		if i.asn == doc.asset_short_name:
			frappe.throw(("Short name {0} already used in Asset Category \
				{1}").format(doc.asset_short_name, i.name))

	