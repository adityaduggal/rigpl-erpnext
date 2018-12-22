# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def execute():
	qod_no_cetsh = frappe.db.sql("""SELECT name, item_code ,gst_hsn_code, cetsh_number FROM `tabQuotation Item` 
		WHERE cetsh_number IS NULL AND gst_hsn_code IS NULL 
		ORDER BY creation""", as_list=1)
	if qod_no_cetsh:
		for qod in sod_no_cetsh:
			qod_doc = frappe.get_doc("Quotation Item", qod[0])
			cetsh_number = frappe.get_value("Item", qod[1], "customs_tariff_number")
			if cetsh_number:
				frappe.db.set_value("Quotation Item", qod[0], "cetsh_number", cetsh_number)
				frappe.db.set_value("Quotation Item", qod[0], "gst_hsn_code", cetsh_number)
				frappe.db.commit()
				print("Updated CETSH Number and GST HSN Code in Quotation # " \
					+ qod_doc.parent + " Item No: " + str(qod_doc.idx))
			else:
				print("QTN# " + qod_doc.parent + " Item Code: " + qod[1] + \
					" At Row No " + str(qod_doc.idx) + \
					" Does Not Have CETSH Number Linked")

	qod_list = frappe.db.sql("""SELECT name, gst_hsn_code, cetsh_number FROM `tabQuotation Item` 
		WHERE cetsh_number IS NOT NULL AND gst_hsn_code IS NULL 
		ORDER BY creation""", as_list=1)
	if qod_list:
		for qod in qod_list:
			cetsh_number = frappe.get_value("Quotation Item", qod[0], "cetsh_number")
			qod_doc = frappe.get_doc("Quotation Item", qod[0])
			frappe.db.set_value("Quotation Item", qod[0], "gst_hsn_code", cetsh_number)
			frappe.db.commit()
			print("Updated GST HSN Code in Quotation # " + qod_doc.parent + " Item No: " + str(qod_doc.idx))

	sod_no_cetsh = frappe.db.sql("""SELECT name, item_code ,gst_hsn_code, cetsh_number FROM `tabSales Order Item` 
		WHERE cetsh_number IS NULL AND gst_hsn_code IS NULL 
		ORDER BY creation""", as_list=1)
	if sod_no_cetsh:
		for sod in sod_no_cetsh:
			sod_doc = frappe.get_doc("Sales Order Item", sod[0])
			cetsh_number = frappe.get_value("Item", sod[1], "customs_tariff_number")
			if cetsh_number:
				frappe.db.set_value("Sales Order Item", sod[0], "cetsh_number", cetsh_number)
				frappe.db.set_value("Sales Order Item", sod[0], "gst_hsn_code", cetsh_number)
				frappe.db.commit()
				print("Updated CETSH Number and GST HSN Code in Sales Order # " \
					+ sod_doc.parent + " Item No: " + str(sod_doc.idx))
			else:
				print("SO# " + sod_doc.parent + " Item Code: " + sod[1] + \
					" At Row No " + str(sod_doc.idx) + \
					" Does Not Have CETSH Number Linked")

	sod_list = frappe.db.sql("""SELECT name, gst_hsn_code, cetsh_number FROM `tabSales Order Item` 
		WHERE cetsh_number IS NOT NULL AND gst_hsn_code IS NULL 
		ORDER BY creation""", as_list=1)
	if sod_list:
		for sod in sod_list:
			cetsh_number = frappe.get_value("Sales Order Item", sod[0], "cetsh_number")
			sod_doc = frappe.get_doc("Sales Order Item", sod[0])
			frappe.db.set_value("Sales Order Item", sod[0], "gst_hsn_code", cetsh_number)
			frappe.db.commit()
			print("Updated GST HSN Code in Sales Order # " + sod_doc.parent + " Item No: " + str(sod_doc.idx))

	dnd_no_cetsh = frappe.db.sql("""SELECT name, item_code, gst_hsn_code, cetsh_number FROM `tabDelivery Note Item` 
		WHERE cetsh_number IS NULL AND gst_hsn_code IS NULL 
		ORDER BY creation""", as_list=1)
	if dnd_no_cetsh:
		for dnd in dnd_no_cetsh:
			dnd_doc = frappe.get_doc("Delivery Note Item", dnd[0])
			cetsh_number = frappe.get_value("Item", dnd[1], "customs_tariff_number")
			if cetsh_number:
				frappe.db.set_value("Delivery Note Item", dnd[0], "cetsh_number", cetsh_number)
				frappe.db.set_value("Delivery Note Item", dnd[0], "gst_hsn_code", cetsh_number)
				frappe.db.commit()
				print("Updated CETSH Number and GST HSN Code in Delivery Note # " \
					+ dnd_doc.parent + " Item No: " + str(dnd_doc.idx))
			else:
				print("DN# " + dnd_doc.parent + " Item Code: " + dnd[1] + \
					" At Row No " + str(dnd_doc.idx) + \
					" Does Not Have CETSH Number Linked")


	dnd_list = frappe.db.sql("""SELECT name, gst_hsn_code, cetsh_number FROM `tabDelivery Note Item` 
		WHERE cetsh_number IS NOT NULL AND gst_hsn_code IS NULL 
		ORDER BY creation""", as_list=1)
	if dnd_list:
		for dnd in dnd_list:
			cetsh_number = frappe.get_value("Delivery Note Item", dnd[0], "cetsh_number")
			dnd_doc = frappe.get_doc("Delivery Note Item", dnd[0])
			frappe.db.set_value("Delivery Note Item", dnd[0], "gst_hsn_code", cetsh_number)
			frappe.db.commit()
			print("Updated GST HSN Code in DN # " + dnd_doc.parent + " Item No: " + str(dnd_doc.idx))