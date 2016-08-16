# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc,method):
	if doc.is_subcontracting_warehouse == 1:
		#Allow only 1 Subcontracting Warehouse in System
		other_subcontracting_warehouses = frappe.db.sql("""SELECT name FROM `tabWarehouse`
			WHERE docstatus = 0 AND is_subcontracting_warehouse = 1 AND name <> '%s'"""
			%doc.name, as_list=1)
		if other_subcontracting_warehouses:
			frappe.throw(("Warehouse {0} already alloted as Subcontracting Warehouse \
				and only 1 Subcontracting Warehouse is Allowed").\
				format(other_subcontracting_warehouses[0][0]))