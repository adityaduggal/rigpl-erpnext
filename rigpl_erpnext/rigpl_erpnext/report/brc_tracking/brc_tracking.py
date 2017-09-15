# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		"BRC:Link/BRC MEIS Tracking:50",
		"SHB No::80", "SHB Date:Date:80",
		"Bank IFSC::100", "BRC No::200", "BRC Date:Date:80",
		"BRC Realised Value:Currency:80", "Bill ID::150",
		"Grand Total:Currency:80", "Currency::50", 
		"BRC Status::80", "Notes::200", "Type::80", 
		"Ref Name:Dynamic Link/Ref Doctype:100",
		"Export Invoice No::100",
		"Customer or Supplier:Dynamic Link/Cust or Supp:150",
		"Ref Doctype::10", "Cust or Supp::10"
	]

def get_data(filters):
	conditions = get_conditions(filters)

	data = frappe.db.sql("""SELECT name, shipping_bill_number, shipping_bill_date,
		bank_ifsc_code, brc_number, brc_date, brc_realised_value, brc_bill_id,
		grand_total, reference_currency,
		brc_status, notes, export_or_import, 
		reference_name, export_invoice_number,
		customer_or_supplier_name, reference_doctype, customer_or_supplier
		FROM `tabBRC MEIS Tracking`
		WHERE docstatus = 0 %s"""%(conditions), as_list=1)

	return data

def get_conditions(filters):
	conditions = ""
	if filters.get("ref_name"):
		conditions += "AND reference_name = '%s'" %filters["ref_name"]

	if filters.get("shb_no"):
		conditions += "AND shipping_bill_number = '%s'" %filters["shb_no"]

	if filters.get("brc_no"):
		conditions += "AND brc_number = '%s'" %filters["brc_no"]

	if filters.get("type"):
		conditions += "AND export_or_import = '%s'" %filters["type"]

	if filters.get("brc_status"):
		conditions += "AND brc_status = '%s'" %filters["brc_status"]

	return conditions