# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	if doc.is_subcontracting_warehouse == 1:
		#Allow only 1 Subcontracting Warehouse in System
		other_subcontracting_warehouses = frappe.db.sql("""SELECT name FROM `tabWarehouse`
			WHERE docstatus = 0 AND is_subcontracting_warehouse = 1 AND name != '%s'"""
			%doc.name, as_list=1)
		if other_subcontracting_warehouses:
			frappe.throw(("Warehouse {0} already alloted as Subcontracting Warehouse \
				and only 1 Subcontracting Warehouse is Allowed").\
				format(other_subcontracting_warehouses[0][0]))
	if doc.is_group == 0:
		if not doc.type_of_warehouse:
			frappe.throw("Type of Warehouse is Mandatory for {}".format(doc.name))
		other_serial = frappe.db.sql("""SELECT name FROM `tabWarehouse` 
			WHERE docstatus=0 AND is_group=0 AND name!='%s' 
			AND listing_serial = %s"""%(doc.name, doc.listing_serial), as_list=1)
		if len(other_serial)>0:
			frappe.throw("Listing Serial: {} already Assigned to Warehouse {}".format(doc.listing_serial, other_serial[0][0]))

		if doc.short_code:
			oth_short_code = frappe.db.sql("""SELECT name FROM `tabWarehouse` WHERE docstatus=0 AND is_group=0 
				AND name != '%s' AND short_code = '%s'"""%(doc.name, doc.short_code), as_list=1)
			if len(oth_short_code)>0:
				frappe.throw("Short Code: {} already Assigned to Warehouse {}".format(doc.short_code, oth_short_code[0][0]))
		else:
			frappe.throw("Short Code is Mandatory for {}".format(doc.name))