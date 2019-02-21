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
			"Ref Name:Dynamic Link/Ref Doctype:100", "Invoice Date:Date:80", "BRC Status::80",
			"BRC No::100", "BRC Date:Date:80", "BRC Days:Int:40", 
			"Invoice Net Total INR:Currency:80", "Invoice Grand Total:Currency:80",
			"BRC Realised Value:Currency:80",
			"Invoice Currency::80", "Bill ID::250", "Notes::200", "Type::80", 
			"Export Invoice No::100", "Ref Doctype::10", "Cust or Supp::10"
		]
	else:
		return [
			"BRC:Link/BRC MEIS Tracking:80",
			"SHB No::70", "SHB Date:Date:80", 
			"Customer or Supplier:Dynamic Link/Cust or Supp:150",
			"Ref Name:Dynamic Link/Ref Doctype:100",
			"MEIS Status::60", "MEIS No::80",
			"MEIS Date:Date:80", "MEIS Days:Int:40",
			"MEIS Total Amount:Currency:80", "Invoice Net Total INR:Currency:80",
			"MEIS Ref No:Dynamic Link/MEIS Ref:100",
			"Doc Status::50",
			"Ref Doctype::10", "Cust or Supp::10", "MEIS Ref::10"
		]


def get_data(filters):
	conditions = get_conditions(filters)
	if not filters.get("meis_status"):
		data = frappe.db.sql("""SELECT brc.name, brc.shipping_bill_number, brc.shipping_bill_date,
			brc.bank_ifsc_code, brc.customer_or_supplier_name, brc.reference_name, si.posting_date,
			brc.brc_status, brc.brc_number, brc.brc_date,  
			DATEDIFF(IFNULL(brc.brc_date, CURDATE()), brc.shipping_bill_date),
			si.base_net_total, brc.grand_total, brc.reference_currency, brc.brc_realised_value,
			brc.brc_bill_id, brc.notes, brc.export_or_import, brc.export_invoice_number,
			brc.reference_doctype, brc.customer_or_supplier
			FROM `tabBRC MEIS Tracking` brc, `tabSales Invoice` si
			WHERE si.name = brc.reference_name AND brc.reference_doctype = 'Sales Invoice' 
				AND brc.docstatus !=2 %s"""%(conditions), as_list=1)
	else:
		data = frappe.db.sql("""SELECT brc.name, brc.shipping_bill_number, brc.shipping_bill_date,
			brc.customer_or_supplier_name, brc.reference_name, brc.meis_status,
			brc.meis_authorization_no, brc.meis_date, 
			DATEDIFF(IFNULL(brc.meis_date, CURDATE()), brc.shipping_bill_date),
			brc.meis_amount, si.base_net_total, 
			brc.meis_reference_name,
			IF (brc.docstatus=0, "Draft", "Submitted"), 
			brc.reference_doctype, brc.customer_or_supplier, brc.meis_reference_type
			FROM `tabBRC MEIS Tracking` brc, `tabSales Invoice` si
			WHERE si.name = brc.reference_name AND brc.reference_doctype = 'Sales Invoice'
				AND brc.docstatus !=2 AND brc.brc_status = 'BRC Issued' %s"""%(conditions), as_list=1)

	return data

def get_conditions(filters):
	conditions = ""
	if filters.get("from_date"):
		conditions += " AND brc.shipping_bill_date >= '%s'" %filters["from_date"]

	if filters.get("to_date"):
		conditions += " AND brc.shipping_bill_date <= '%s'" %filters["to_date"]

	if filters.get("brc_status"):
		conditions += " AND brc.brc_status = '%s'" %filters["brc_status"]

	if filters.get("meis_status"):
		if filters.get("meis_status") != "All MEIS":
			conditions += " AND brc.meis_status = '%s'" %filters["meis_status"]

	if filters.get("docstatus"):
		if filters.get("brc.docstatus") == "Draft":
			conditions += " AND brc.docstatus = 0"
		else:
			conditions += " AND brc.docstatus = 1"
	else:
		conditions += " AND brc.docstatus = 0"
	return conditions