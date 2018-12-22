# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from rigpl_erpnext.rigpl_erpnext.validations.sales_order import \
	check_price_list, get_hsn_code

def validate(doc,method):
	check_taxes_integrity(doc,method)
	check_price_list(doc, method)
	for rows in doc.items:
		get_hsn_code(doc, rows)
	#Check if Lead is Converted or Not, if the lead is converted 
	#then don't allow it to be selected without linked customer
	if doc.lead:
		link = frappe.db.sql("""SELECT name FROM `tabCustomer` 
			WHERE lead_name = '%s'"""%(doc.lead), as_list=1)
		if doc.customer is None and link:
			frappe.throw(("Lead {0} is Linked to Customer {1} so kindly make quotation for \
				Customer and not Lead").format(doc.lead, link[0][0]))
		elif doc.customer:
			if doc.customer != link[0][0]:
				frappe.throw(("Customer {0} is not linked to Lead {1} hence cannot be set\
				in the Quotation").format(doc.customer, doc.lead))
	#below code updates the CETSH number for the item in Quotation and updates letter head
	letter_head_tax = frappe.db.get_value("Sales Taxes and Charges Template", \
		doc.taxes_and_charges, "letter_head")
	doc.letter_head = letter_head_tax
	
def check_taxes_integrity(doc,method):
	template = frappe.get_doc("Sales Taxes and Charges Template", doc.taxes_and_charges)
	for tax in doc.taxes:
		for temp in template.taxes:
			if tax.idx == temp.idx:
				if tax.charge_type != temp.charge_type or tax.row_id != temp.row_id or \
					tax.account_head != temp.account_head or tax.included_in_print_rate \
					!= temp.included_in_print_rate or tax.rate != temp.rate:
						frappe.throw(("Selected Tax {0}'s table does not match with tax table \
							of Quotation# {1}. Check Row # {2} or reload Taxes").\
							format(doc.taxes_and_charges, doc.name, tax.idx))
