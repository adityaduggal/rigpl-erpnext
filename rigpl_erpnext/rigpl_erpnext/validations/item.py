# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import html
from frappe import msgprint
from frappe.desk.reportview import get_match_cond
from rigpl_erpnext.utils.item_utils import *
from datetime import date, datetime
from frappe.utils import getdate

def validate(doc, method):
	if doc.variant_of:
		template = frappe.get_doc("Item", doc.variant_of)
		if doc.get("__islocal") == 1:
			check_item_defaults(template, doc)
		else:
			check_and_copy_attributes_to_variant(template, doc, insert_type="frontend")

	validate_variants(doc)
	validate_attribute_numeric(doc)
	validate_reoder(doc)
	web_catalog(doc)
	doc.page_name = doc.item_name
	description, long_desc = generate_description(doc)
	doc.description = description
	#doc.web_long_description = long_desc
	doc.item_name = long_desc
	doc.item_code = doc.name

	if getdate(doc.end_of_life) < datetime.strptime('2099-12-31', "%Y-%m-%d").date():
		doc.disabled = 1
		doc.pl_item = "No"
		doc.show_variant_in_website = 0
		doc.show_in_website = 0

	if doc.disabled == 1:
		if getdate(doc.end_of_life) > date.today():
			doc.end_of_life = date.today()

		doc.pl_item = "No"
		doc.show_variant_in_website = 0
		doc.show_in_website = 0

	if doc.variant_of is None:
		doc.item_name = doc.name
		doc.item_code = doc.name
		doc.page_name = doc.name
		doc.description = doc.name
	else:
		set_website_specs(doc,method)
	make_route(doc)
	#validate_sales_fields(doc, method)

		
def autoname(doc,method):
	if doc.variant_of:
		(serial, code) = generate_item_code(doc,method)
		doc.name = code
		doc.page_name = doc.name
		nxt_serial = fn_next_string(doc,serial[0][0])
		frappe.db.set_value("Item Attribute Value", serial[0][1], "serial", nxt_serial)
		
def generate_item_code(doc,method):
	if doc.variant_of:
		code = ""
		abbr = []
		for d in doc.attributes:
			is_numeric = frappe.db.get_value("Item Attribute", d.attribute, "numeric_values")
			use_in_item_code = frappe.db.get_value("Item Attribute", d.attribute, 
				"use_in_item_code")
			if is_numeric != 1 and use_in_item_code == 1:
				cond1 = d.attribute
				cond2 = d.attribute_value
				query = """SELECT iav.abbr from `tabItem Attribute Value` iav, 
				`tabItem Attribute` ia
				WHERE iav.parent = '%s' AND iav.parent = ia.name
				AND iav.attribute_value = '%s'""" %(cond1, cond2)

				#Get serial from Tool Type (This is HARDCODED)
				#TODO: Put 1 custom field in Item Attribute checkbox "Use for Serial Number"
				#now also add a validation that you cannot use more than 1 attributes which 
				#have use for serial no.
				if cond1 == "Tool Type":
					query2 = """SELECT iav.serial, iav.name from `tabItem Attribute Value` iav
						WHERE iav.parent = 'Tool Type' AND iav.attribute_value= '%s'""" %cond2
					serial = frappe.db.sql(query2 , as_list=1)
				
				abbr.extend(frappe.db.sql(query, as_list=1))
				abbr[len(abbr)-1].append(d.idx)
		abbr.sort(key=lambda x:x[1]) #Sort the abbr as per priority lowest one is taken first
		
		for i in range(len(abbr)):
			if abbr[i][0] != '""':
				code = code + abbr[i][0]
		if len(serial[0][0]) > 2:
			code = code + serial[0][0]
		else:
			frappe.throw("Serial length is lower than 3 characters")
		chk_digit = fn_check_digit(doc,code)
		code = code + str(chk_digit)
		return serial, code
			
########CODE FOR NEXT STRING#######################################################################
def fn_next_string(doc,s):
	#This function would increase the serial number by One following the
	#alpha-numeric rules as well
	if len(s) == 0:
		return '1'
	head = s[0:-1]
	tail = s[-1]
	if tail == 'Z':
		return fn_next_string(doc, head) + '0'
	if tail == '9':
		return head+'A'
	if tail == 'H':
		return head+'J'
	if tail == 'N':
		return head+'P'
	return head + chr(ord(tail)+1)
################################################################################
	
###############~Code to generate the CHECK DIGIT~###############################
################################################################################
def fn_check_digit(doc,id_without_check):

	# allowable characters within identifier
	valid_chars = "0123456789ABCDEFGHJKLMNPQRSTUVYWXZ"

	# remove leading or trailing whitespace, convert to uppercase
	id_without_checkdigit = id_without_check.strip().upper()

	# this will be a running total
	sum = 0;

	# loop through digits from right to left
	for n, char in enumerate(reversed(id_without_checkdigit)):

			if not valid_chars.count(char):
					frappe.throw('Invalid Character has been used for Item Code check Attributes')

			# our "digit" is calculated using ASCII value - 48
			digit = ord(char) - 48

			# weight will be the current digit's contribution to
			# the running total
			weight = None
			if (n % 2 == 0):

					# for alternating digits starting with the rightmost, we
					# use our formula this is the same as multiplying x 2 &
					# adding digits together for values 0 to 9.  Using the
					# following formula allows us to gracefully calculate a
					# weight for non-numeric "digits" as well (from their
					# ASCII value - 48).
					weight = (2 * digit) - int((digit / 5)) * 9
			else:
					# even-positioned digits just contribute their ascii
					# value minus 48
					weight = digit

			# keep a running total of weights
			sum += weight

	# avoid sum less than 10 (if characters below "0" allowed,
	# this could happen)
	sum = abs(sum) + 10

	# check digit is amount needed to reach next number
	# divisible by ten. Return an integer
	return int((10 - (sum % 10)) % 10)

#Set the Website Specifications automatically from Template, Attribute and Variant Table
#This is done only for Variants which are shown on website
def set_website_specs(doc,method):
	if doc.show_variant_in_website == 1:
		template = frappe.get_doc("Item", doc.variant_of)
		web_spec = []
		for temp_att in template.attributes:
			temp = []
			if temp_att.use_in_description == 1:				
				attribute_doc = frappe.get_doc("Item Attribute", temp_att.attribute)
				att_val = frappe.db.sql("""SELECT attribute_value 
					FROM `tabItem Variant Attribute`
					WHERE parent = '%s' AND attribute = '%s'"""% \
					(doc.name, temp_att.attribute), as_list=1)

				if attribute_doc.numeric_values == 1 and att_val[0][0] is not None:
					temp.insert(0,temp_att.field_name)
					temp.insert(1,str(att_val[0][0]))
					web_spec.append(temp)
				else:
					desc = frappe.db.sql("""SELECT long_description FROM `tabItem Attribute Value`
						WHERE parent = '%s' AND attribute_value = '%s' """ \
						%(temp_att.attribute, att_val[0][0]), as_list=1)
					if desc[0][0][1:-1] != "":
						temp.insert(0,temp_att.field_name)
						temp.insert(1,desc[0][0][1:-1])
						web_spec.append(temp)	
		doc.set("website_specifications", [])
		for label, desc in web_spec:
			row = doc.append("website_specifications")
			row.label = label
			row.description = desc