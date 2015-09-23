# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc, method):
	doc.page_name = doc.item_name
	generate_description(doc,method)
	if doc.variant_of is None:
		doc.item_name = doc.name
		doc.item_code = doc.name
		doc.page_name = doc.name
	
def autoname(doc,method):
	if doc.variant_of:
		(serial, code) = generate_item_code(doc,method)
		doc.name = code
		doc.page_name = doc.name
		nxt_serial = fn_next_string(doc,serial[0][0])
		frappe.db.set_value("Item Attribute Value", serial[0][1], "serial", nxt_serial)

		
def generate_description(doc,method):
	if doc.variant_of:
		desc = []
		description = ""
		long_desc = ""
		for d in doc.attributes:
			is_numeric = frappe.db.get_value("Item Attribute", d.attribute, "numeric_values")
			use_in_description = frappe.db.sql("""SELECT iva.use_in_description from  `tabItem Variant Attribute` iva 
				WHERE iva.parent = '%s' AND iva.attribute = '%s' """ %(doc.variant_of, d.attribute), as_list=1)[0][0]
				
			if is_numeric <> 1 and use_in_description == 1:
				#Below query gets the values of description mentioned in the Attribute table
				#for non-numeric values
				cond1 = d.attribute
				cond2 = d.attribute_value
				query = """SELECT iav.description, iav.long_description
					FROM `tabItem Attribute Value` iav, `tabItem Attribute` ia
					WHERE iav.parent = '%s' AND iav.parent = ia.name
					AND iav.attribute_value = '%s'""" %(cond1, cond2)				
				list =frappe.db.sql(query, as_list=1)

				prefix = frappe.db.sql("""SELECT iva.prefix FROM `tabItem Variant Attribute` iva
					WHERE iva.parent = '%s' AND iva.attribute = '%s' """ % (doc.variant_of, d.attribute ), as_list=1)
					
				suffix = frappe.db.sql("""SELECT iva.suffix FROM `tabItem Variant Attribute` iva
					WHERE iva.parent = '%s' AND iva.attribute = '%s' """ % (doc.variant_of, d.attribute ), as_list=1)
					
				concat = ""
				if prefix[0][0] <> '""':
					concat = str(prefix[0][0]) + str(list[0][0])
					concat2 = str(prefix[0][0]) + str(list[0][1])
				else:
					concat1 = str(list[0][0])
					concat2 = str(list[0][1])

				if suffix[0][0]<> '""':
					concat1 = concat1 + str(suffix[0][0])
					concat2 = concat2 + str(suffix[0][0])
				desc.extend([[concat1, concat2, d.idx]])
				
			elif is_numeric == 1 and use_in_description == 1:
				#Below query gets the values of description mentioned in the Attribute table
				#for Numeric values
				query1 = """SELECT iva.idx FROM `tabItem Variant Attribute` iva
					WHERE iva.attribute = '%s'""" %d.attribute
					
				prefix = frappe.db.sql("""SELECT iva.prefix FROM `tabItem Variant Attribute` iva
					WHERE iva.parent = '%s' AND iva.attribute = '%s' """ % (doc.variant_of, d.attribute ), as_list=1)
					
				suffix = frappe.db.sql("""SELECT iva.suffix FROM `tabItem Variant Attribute` iva
					WHERE iva.parent = '%s' AND iva.attribute = '%s' """ % (doc.variant_of, d.attribute ), as_list=1)
					
				concat = ""
				if prefix[0][0] <> '""':
					concat = str(prefix[0][0]) + str(d.attribute_value)
				else:
					concat = str(d.attribute_value)

				if suffix[0][0]<> '""':
					concat = concat + str(suffix[0][0])
				desc.extend([[concat, concat, d.idx]])
			
			else:
				query1 = """SELECT iva.idx FROM `tabItem Variant Attribute` iva
					WHERE iva.attribute = '%s'""" %d.attribute	
				desc.extend([["","",frappe.db.sql(query1, as_list=1)[0][0]]])

		
		desc.sort(key=lambda x:x[2]) #Sort the desc as per priority lowest one is taken first
		for i in range(len(desc)):
			if desc[i][0] <> '""':
				description = description + desc[i][0]
			if desc[i][1] <> '""':
				long_desc = long_desc + desc[i][1]

		doc.description = description
		doc.web_long_description = long_desc
		doc.item_name = long_desc
		doc.item_code = doc.name
		
def generate_item_code(doc,method):
	if doc.variant_of:
		code = ""
		abbr = []
		for d in doc.attributes:
			is_numeric = frappe.db.get_value("Item Attribute", d.attribute, "numeric_values")
			use_in_item_code = frappe.db.get_value("Item Attribute", d.attribute, "use_in_item_code")
			if is_numeric <> 1 and use_in_item_code == 1:
				cond1 = d.attribute
				cond2 = d.attribute_value
				query = """SELECT iav.abbr, ia.priority from `tabItem Attribute Value` iav, `tabItem Attribute` ia
					WHERE iav.parent = '%s' AND iav.parent = ia.name
					AND iav.attribute_value = '%s'""" %(cond1, cond2)

				#Get serial from Tool Type (This is HARDCODED)
				#TODO: Put 1 custom field in Item Attribute checkbox "Use for Serial Number"
				#now also add a validation that you cannot use more than 1 attributes which have use for serial no.
				if cond1 == "Tool Type":
					query2 = """SELECT iav.serial, iav.name from `tabItem Attribute Value` iav
						WHERE iav.parent = 'Tool Type' AND iav.attribute_value= '%s'""" %cond2
					serial = frappe.db.sql(query2 , as_list=1)
				
				abbr.extend(frappe.db.sql(query,as_list=1))
		abbr.sort(key=lambda x:x[1]) #Sort the abbr as per priority lowest one is taken first
		
		for i in range(len(abbr)):
			if abbr[i][0] <> '""':
				code = code + abbr[i][0]
		code = code + serial[0][0]
		chk_digit = fn_check_digit(doc,code)
		code = code + `chk_digit`
		return serial, code
		
########Change the IDX of the Item Varaint Attribute table as per Priority########################
def change_idx(doc,method):
	if doc.variant_of or doc.has_variants:
		for d in doc.attributes:
			iva = frappe.get_doc("Item Variant Attribute", d.name)
			att = frappe.get_doc("Item Attribute", d.attribute)
			name = `str(d.name)`
			frappe.db.set_value("Item Variant Attribute", name, "idx", att.priority, update_modified=False ,debug = True)
			iva.idx = att.priority
			
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

@frappe.whitelist()
def get_uom_factors(from_uom, to_uom):
	if (from_uom == to_uom): 
		return {'lft': 1, 'rgt': 1}
	return {
		'rgt': frappe.db.get_value('UOM Conversion Detail', filters={'parent': from_uom, 'uom': to_uom}, fieldname='conversion_factor'),
		'lft': frappe.db.get_value('UOM Conversion Detail', filters={'parent': to_uom, 'uom': from_uom}, fieldname='conversion_factor')
	}
	