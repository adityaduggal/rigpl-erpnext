# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.utils import nowdate

def validate(doc,method):
	update_fields(doc,method)
	check_gst_rules(doc,method)
	check_taxes_integrity(doc,method)
	check_price_list(doc,method)

def check_price_list(doc,method):
	for it in doc.items:
		if it.price_list:
			check_get_pl_rate(doc, it)
		else:
			it.price_list = doc.selling_price_list
			check_get_pl_rate(doc, it)

def check_get_pl_rate(doc, row_dict):
	pl_doc = frappe.get_doc("Price List", row_dict.price_list)
	if pl_doc.disable_so == 1:
			frappe.throw("Sales Order Booking Disabled for {} at Row# {}".\
				format(row_dict.price_list, row_dict.idx))
	item_pl_rate = frappe.db.sql("""SELECT price_list_rate, currency FROM `tabItem Price`
			WHERE price_list = '%s' AND item_code = '%s' 
			AND selling = 1"""%(row_dict.price_list, row_dict.item_code), as_list=1)
	if item_pl_rate:
		if row_dict.price_list_rate != item_pl_rate[0][0] and doc.currency == item_pl_rate[0][1]:
			row_dict.price_list_rate = item_pl_rate[0][0]
	else:
		frappe.msgprint("In {}# {} at Row# {} and Item Code: {} Price List \
			Rate is Not Defined".format(doc.doctype, doc.name, row_dict.idx, \
				row_dict.item_code))

def update_fields(doc,method):
	doc.shipping_address_title = frappe.get_value("Address", \
		doc.shipping_address_name, "address_title")
	doc.transaction_date = nowdate()
	if doc.delivery_date < nowdate():
		doc.delivery_date = nowdate()
	for d in doc.items:
		if d.delivery_date < nowdate():
			d.delivery_date = nowdate()

	letter_head_tax = frappe.db.get_value("Sales Taxes and Charges Template", \
		doc.taxes_and_charges, "letter_head")
	doc.letter_head = letter_head_tax
	
	for items in doc.items:
		get_hsn_code(doc, items)

def get_hsn_code(doc, row_dict)
		custom_tariff = frappe.db.get_value("Item", row_dict.item_code, "customs_tariff_number")
		if custom_tariff:
			if len(custom_tariff) == 8:
				row_dict.gst_hsn_code = custom_tariff 
			else:
				frappe.throw(("Item Code {0} in line# {1} has a Custom Tariff {2} which not  \
					8 digit, please get the Custom Tariff corrected").\
					format(row_dict.item_code, row_dict.idx, custom_tariff))
		else:
			frappe.throw(("Item Code {0} in line# {1} does not have linked Customs \
				Tariff in Item Master").format(row_dict.item_code, row_dict.idx))

def check_gst_rules(doc,method):
	bill_state = frappe.db.get_value("Address", doc.customer_address, "state_rigpl")
	template_doc = frappe.get_doc("Sales Taxes and Charges Template", doc.taxes_and_charges)
	bill_country = frappe.db.get_value("Address", doc.customer_address, "country")
	
	series_template = frappe.db.get_value("Sales Taxes and Charges Template", \
		doc.taxes_and_charges ,"series")
		
	#Check series of Tax with the Series Selected for Invoice
	if series_template != doc.naming_series[2:4] and series_template != doc.name[2:4]:
		frappe.throw(("Selected Tax Template {0} Not Allowed since Series Selected {1} and \
			Invoice number {2} don't match with the Selected Template").format( \
			doc.taxes_and_charges, doc.naming_series, doc.name))
	
	if doc.taxes_and_charges != 'OGL':
		#Check if Shipping State is Same as Template State then check if the tax template is LOCAL
		#Else if the States are different then the template should NOT BE LOCAL
		if bill_state == template_doc.state and template_doc.is_export != 1:
			if template_doc.is_local_sales != 1:
				frappe.throw(("Selected Tax {0} is NOT LOCAL Tax but Shipping Address is \
					in Same State {1}, hence either change Shipping Address or Change the \
					Selected Tax").format(doc.taxes_and_charges, bill_state))
		elif bill_country == 'India' and bill_state != template_doc.state:
			if template_doc.is_local_sales == 1:
				frappe.throw(("Selected Tax {0} is LOCAL Tax but Shipping Address is \
					in Different State {1}, hence either change Shipping Address or Change the \
					Selected Tax").format(doc.taxes_and_charges, bill_state))
		elif bill_country != 'India': #Case of EXPORTS
			if template_doc.state is not None and template_doc.is_export != 1:
				frappe.throw(("Selected Tax {0} is for Indian Sales but Shipping Address is \
					in Different Country {1}, hence either change Shipping Address or Change the \
					Selected Tax").format(doc.taxes_and_charges, bill_country))

def check_taxes_integrity(doc,method):
	template = frappe.get_doc("Sales Taxes and Charges Template", doc.taxes_and_charges)
	for tax in doc.taxes:
		for temp in template.taxes:
			if tax.idx == temp.idx:
				if tax.charge_type != temp.charge_type or tax.row_id != temp.row_id or \
					tax.account_head != temp.account_head or tax.included_in_print_rate \
					!= temp.included_in_print_rate or tax.rate != temp.rate:
						frappe.throw(("Selected Tax {0}'s table does not match with tax table \
							of Sales Order# {1}. Check Row # {2} or reload Taxes").\
							format(doc.taxes_and_charges, doc.name, tax.idx))

def on_submit(so,method):
	if so.track_trial == 1:
		no_of_team = 0
		
		for s_team in so.get("sales_team"):
			no_of_team = len(so.get("sales_team"))
		
		if no_of_team != 1:
			frappe.msgprint("Please enter exactly one Sales Person who is responsible for carrying out the Trials", raise_exception=1)
		
		for sod in so.get("items"):
			tt=frappe.new_doc("Trial Tracking")
			tt.prevdoc_detail_docname = sod.name
			tt.against_sales_order = so.name
			tt.customer = so.customer
			tt.item_code = sod.item_code
			tt.qty = sod.qty
			tt.description = sod.description
			tt.base_rate = sod.base_rate
			tt.trial_owner = s_team.sales_person
			tt.status = "In Production"
			tt.insert()
			query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod.name
			name = frappe.db.sql(query, as_list=1)
			frappe.msgprint('{0}{1}'.format("Created New Trial Tracking Number: ", name[0][0]))
			
			
def on_cancel(so, method):
	if so.track_trial == 1:
		for sod in so.get("items"):
			query = """SELECT tt.name FROM `tabTrial Tracking` tt where tt.prevdoc_detail_docname = '%s' """ % sod.name
			name = frappe.db.sql(query, as_list=1)
			if name:
				frappe.delete_doc("Trial Tracking", name[0])
				frappe.msgprint('{0}{1}'.format("Deleted Trial Tracking No: ", name[0][0]))
