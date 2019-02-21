# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	if not filters.get("meis_status"):
		return [
			"BRC:Link/BRC MEIS Tracking:80",
			"SB No::70", "SB Date:Date:80",
			"Bank IFSC::60", "Customer or Supplier:Dynamic Link/Cust or Supp:150",
			"Ref Name:Dynamic Link/Ref Doctype:100", "BRC Status::80",
			"BRC No::100", "BRC Date:Date:80",
			"BRC Realised Value:Currency:80", "BRC Days:Int:40", "Bill ID::80",
			"Grand Total:Currency:80", "Currency::50", 
			"Notes::200", "Type::80", 
			"Export Invoice No::100",
			"Ref Doctype::10", "Cust or Supp::10"
		]
	else:
		return [
			"BRC:Link/BRC MEIS Tracking:80",
			"SHB No::70", "SHB Date:Date:80", 
			"Customer or Supplier:Dynamic Link/Cust or Supp:150",
			"Ref Name:Dynamic Link/Ref Doctype:100",
			"MEIS Status::60", "MEIS No::80",
			"MEIS Date:Date:80", "MEIS Days:Int:40",
			"MEIS Total Amount:Currency:80", "BRC Realised Amount:Currency:80",
			"MEIS Ref No:Dynamic Link/MEIS Ref:100",
			"BRC Currency::30", "Doc Status::50",
			"Ref Doctype::10", "Cust or Supp::10", "MEIS Ref::10"
		]


def get_data(filters):
	conditions = get_conditions(filters)
	if not filters.get("meis_status"):
		data = frappe.db.sql("""SELECT name, shipping_bill_number, shipping_bill_date,
			bank_ifsc_code, customer_or_supplier_name, reference_name, brc_status,
			brc_number, brc_date, brc_realised_value, 
			DATEDIFF(IFNULL(brc_date, CURDATE()), shipping_bill_date), brc_bill_id,
			grand_total, reference_currency, notes, export_or_import, export_invoice_number,
			reference_doctype, customer_or_supplier
			FROM `tabBRC MEIS Tracking`
			WHERE docstatus !=2 %s"""%(conditions), as_list=1)
	else:
		data = frappe.db.sql("""SELECT name, shipping_bill_number, shipping_bill_date,
			customer_or_supplier_name, reference_name, meis_status,
			meis_authorization_no, meis_date, 
			DATEDIFF(IFNULL(meis_date, CURDATE()), shipping_bill_date),
			meis_amount, brc_realised_value, reference_currency, 
			meis_reference_name,
			IF (docstatus=0, "Draft", "Submitted"), 
			reference_doctype, customer_or_supplier, meis_reference_type
			FROM `tabBRC MEIS Tracking`
			WHERE docstatus !=2 AND brc_status = 'BRC Issued' %s"""%(conditions), as_list=1)

	return data

def get_conditions(filters):
	conditions = ""
	if filters.get("from_date"):
		conditions += "AND shipping_bill_date >= '%s'" %filters["from_date"]

	if filters.get("to_date"):
		conditions += "AND shipping_bill_date <= '%s'" %filters["to_date"]

	if filters.get("brc_status"):
		conditions += "AND brc_status = '%s'" %filters["brc_status"]

	if filters.get("meis_status"):
		if filters.get("meis_status") != "All MEIS":
			conditions += "AND meis_status = '%s'" %filters["meis_status"]

	if filters.get("docstatus"):
		if filters.get("docstatus") == "Draft":
			conditions += "AND docstatus = 0"
		elif filters.get("docstatus") == "Submitted":
			conditions += "AND docstatus = 1"
		else:
			if not filter.get("meis_status"):
				conditions += "AND docstatus = 1"
			else:
				conditions += "AND docstatus = 0"

	return conditions