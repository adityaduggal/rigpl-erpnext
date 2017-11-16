# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe, erpnext

def execute():
	no_valid_till = frappe.db.sql("""SELECT name, valid_till, quote_valid FROM `tabQuotation` 
		WHERE quote_valid IS NOT NULL AND valid_till IS NULL ORDER BY creation ASC""", as_list=1)
	no_date = frappe.db.sql("""SELECT name, transaction_date FROM `tabQuotation`
		WHERE quote_valid IS NULL AND valid_till IS NULL ORDER BY creation DESC""", as_list=1)
	for quote in no_valid_till:
		frappe.db.set_value("Quotation", quote[0], "valid_till", quote[2])
		print ("Quotation No: " + quote[0] + " Changed Expiry Date from  = " + str(quote[1]) + " to New Expiry Date = " + str(quote[2]))

	for quote in no_date:
		frappe.db.set_value("Quotation", quote[0], "valid_till", quote[1])
		print ("Quotation No: " + str(quote[0]) + " Has NO DATE But Updated the Validity = " + str(quote[1]))