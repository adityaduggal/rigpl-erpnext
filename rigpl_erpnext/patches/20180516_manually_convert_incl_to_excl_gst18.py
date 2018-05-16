# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def execute():
	so_or_dn = raw_input("Type dn or so for Delivery Note or Sales Order No: ")
	

	if so_or_dn == 'so':
		doc_no = raw_input("Enter the document number: ")
		sod_dict = frappe.db.sql("""SELECT sod.name as sod_name 
			FROM `tabSales Order Item` sod, `tabSales Order` so
			WHERE sod.parent = so.name
			AND so.name = '%s'""" %(doc_no), as_dict=1)
		for sod in sod_dict:
			sod_doc = frappe.get_doc("Sales Order Item", sod.sod_name)
			frappe.db.set_value("Sales Order Item", sod.sod_name, "rate", sod_doc.net_rate)
			frappe.db.set_value("Sales Order Item", sod.sod_name, "base_rate", sod_doc.base_net_rate)
		print('Updated SO# ' + doc_no)

	elif so_or_dn == 'dn':
		doc_no = raw_input("Enter the document number: ")
		dnd_dict = frappe.db.sql("""SELECT dnd.name as dnd_name, dnd.so_detail as sod_name,
			dnd.rate as rate, dnd.base_rate as base_rate, dnd.net_rate as net_rate,
			dnd.base_net_rate as base_net_rate
			FROM `tabDelivery Note Item` dnd, `tabDelivery Note` dn
			WHERE dnd.parent = dn.name
			AND dn.name = '%s'"""%(doc_no), as_dict=1)
		for dnd in dnd_dict:
			sod_doc = frappe.get_doc("Sales Order Item", dnd.sod_name)
			if dnd.rate != sod_doc.rate:
				frappe.db.set_value("Delivery Note Item", dnd.dnd_name, "rate", sod_doc.net_rate)
				frappe.db.set_value("Delivery Note Item", dnd.dnd_name, "base_rate", sod_doc.net_rate)
				frappe.db.set_value("Sales Order Item", sod_doc.name, "rate", sod_doc.net_rate)
				frappe.db.set_value("Sales Order Item", sod_doc.name, "base_rate", sod_doc.net_rate)
		print('Updated DN# ' + doc_no)
	else:
		print('Incorrect value entered, enter either so or dn')
		exit()

