# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.utils import flt
from frappe.desk.reportview import get_match_cond

def validate(doc, method):
	validate_variants(doc,method)
	web_catalog(doc,method)
	doc.page_name = doc.item_name
	generate_description(doc,method)
	if doc.variant_of is None:
		doc.item_name = doc.name
		doc.item_code = doc.name
		doc.page_name = doc.name
		doc.description = doc.name
def autoname(doc,method):
	if doc.variant_of:
		(serial, code) = generate_item_code(doc,method)
		doc.name = code
		doc.page_name = doc.name
		nxt_serial = fn_next_string(doc,serial[0][0])
		frappe.db.set_value("Item Attribute Value", serial[0][1], "serial", nxt_serial)

def web_catalog(doc,method):
	validate_stock_fields(doc,method)
	if doc.pl_item == "Yes":
		doc.show_in_website = 1
	else:
		doc.show_in_website = 0
		
	if doc.show_in_website == 1:
		rol = frappe.db.sql("""SELECT warehouse_reorder_level FROM `tabItem Reorder` WHERE parent ='%s' """%(doc.name), as_list=1)
		doc.website_warehouse = doc.default_warehouse
		if rol:
			frappe.msgprint(rol)
			doc.weightage = rol[0][0]

def validate_stock_fields(doc,method):
	if doc.is_stock_item ==1:
		if doc.valuation_method <> 'FIFO':
			frappe.throw("Select Valuation method as FIFO for Stock Item")
			
def validate_variants(doc,method):
	user = frappe.session.user
	query = """SELECT role from `tabUserRole` where parent = '%s' """ %user
	roles = frappe.db.sql(query, as_list=1)
	
	if doc.show_in_website == 1:
		if doc.image and doc.website_image:
			pass
		else:
			frappe.throw("For Website Items Image is Mandatory")
	
	if doc.variant_of:
		#Check if all variants are mentioned in the Item Variant Table as per the Template.
		template = frappe.get_doc("Item", doc.variant_of)
		
		template_attribute = []
		variant_attribute = []
		template_restricted_attributes = {}
		template_rest_summary = []
		

		for t in template.attributes:
			template_attribute.append(t.attribute)
		
		count = 0
		for d in doc.attributes:
			variant_attribute.append([d.attribute])
			variant_attribute[count].append(d.attribute_value)
			count +=1
		
		#First check the order of all the variants is as per the template or not.
		for i in range(len(template_attribute)):
			if len(template_attribute) == len(variant_attribute) and \
				template_attribute[i] != variant_attribute[i][0]:
				
				frappe.throw(("Item Code: {0} Row# {1} should have {2} as per the template")\
					.format(doc.name, i+1, template_attribute[i]))
			
			elif len(template_attribute) != len(variant_attribute):
				frappe.throw(("Item Code: {0} number of attributes not as per the template")\
					.format(doc.name))
		
		#Now check the values of the Variant and if they are within the restrictions.
		#1. Check if the Select field is as per restriction table
		#2. Check the rule of the numeric fields like d1_mm < d2_mm
				
		for t in template.item_variant_restrictions:
			template_rest_summary.append(t.attribute)
			template_restricted_attributes.setdefault(t.attribute,{'rules': [], 'allows': []})
			if t.is_numeric == 1:
				template_restricted_attributes[t.attribute]['rules'].append(t.rule)
			else:
				template_restricted_attributes[t.attribute]['allows'].append(t.allowed_values)
		
		ctx = {}
		for d in doc.attributes:
			is_numeric = frappe.db.get_value("Item Attribute", d.attribute, \
			"numeric_values")
			if is_numeric == 1:
				d.attribute_value = flt(d.attribute_value)
			ctx[d.attribute] =  d.attribute_value
		
		for d in doc.attributes:
			chk_numeric = frappe.db.get_value("Item Attribute", d.attribute, \
			"numeric_values")
			
			if chk_numeric == 1:
				if template_restricted_attributes.get(d.attribute):
					rules = template_restricted_attributes.get(d.attribute, {}).get('rules', [])
					for rule in rules:
						repls = {
							'!': ' not ',
							'false': 'False',
							'true': 'True',
							'&&': ' and ',
							'||': ' or ' 
						}
						for k,v in repls.items():
							rule = rule.replace(k,v)
						try:
							valid = eval(rule, ctx, ctx)
						except Exception, e:
							frappe.throw(e)
							
						if not valid:
							frappe.throw('Item Code: {0} Rule "{1}" failing for field "{2}"'\
								.format(doc.name, rule, d.attribute))
			else:
				if template_restricted_attributes.get(d.attribute, {}).get('allows', False):
					if d.attribute_value not in template_restricted_attributes.get(d.attribute, {})\
						.get('allows', []):
						frappe.throw(("Item Code: {0} Attribute value {1} not allowed")\
							.format(doc.name, d.attribute_value))
		
		#Check the limit in the Template
		limit = template.variant_limit
		actual = frappe.db.sql("""SELECT count(name) FROM `tabItem` WHERE variant_of = '%s'""" \
			% template.name, as_list =1)
		
		check = frappe.db.sql("""SELECT name FROM `tabItem` WHERE name = '%s'""" \
			% doc.name, as_list = 1)
		
		if check:
			if actual[0][0] > limit:
				frappe.throw(("Template Limit reached. Set Limit = {0} whereas total \
					number of variants = {1} increase the limit to save the variant")\
						.format(limit, actual[0][0]))
			else:
				frappe.msgprint(("Template Set Limit = {0} whereas total number of variants = {1}")\
						.format(limit, actual[0][0]))
		else:
			if actual[0][0] >= limit:
				frappe.throw(("Template Limit reached. Set Limit = {0} whereas total \
				number of variants = {1} increase the limit to save New Item Code")\
					.format(limit, actual[0][0]))
	elif doc.has_variants <> 1:
		if any("System Manager" in s  for s in roles):
			pass
		else:
			frappe.throw("Only System Managers are Allowed to Create Non Template or Variant Items")
	elif doc.has_variants == 1:
		if any("System Manager" in s  for s in roles):
			pass
		else:
			frappe.throw("Only System Managers are Allowed to Edit Templates")

						
def generate_description(doc,method):
	if doc.variant_of:
		desc = []
		description = ""
		long_desc = ""
		for d in doc.attributes:
			concat = ""
			concat1 = ""
			concat2 = ""
			is_numeric = frappe.db.get_value("Item Attribute", d.attribute, "numeric_values")
			use_in_description = frappe.db.sql("""SELECT iva.use_in_description from  
				`tabItem Variant Attribute` iva 
				WHERE iva.parent = '%s' AND iva.attribute = '%s' """ %(doc.variant_of, 
					d.attribute), as_list=1)[0][0]
				
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
					WHERE iva.parent = '%s' AND iva.attribute = '%s' """ % (doc.variant_of, 
						d.attribute ), as_list=1)

				suffix = frappe.db.sql("""SELECT iva.suffix FROM `tabItem Variant Attribute` iva
					WHERE iva.parent = '%s' AND iva.attribute = '%s' """ % (doc.variant_of, 
						d.attribute ), as_list=1)

				concat = ""
				concat2 = ""
								
				if prefix[0][0] <> '""':
					if list[0][0]:
						concat1 = unicode(prefix[0][0][1:-1]) + unicode(list[0][0][1:-1])
					if list[0][1]:
						concat2 = unicode(prefix[0][0][1:-1]) + unicode(list[0][1][1:-1])
				else:
					if list[0][0] <> '""':
						concat1 = unicode(list[0][0][1:-1])
					if list[0][1] <> '""':
						concat2 = unicode(list[0][1][1:-1])

				if suffix[0][0]<> '""':
					concat1 = concat1 + unicode(suffix[0][0][1:-1])
					concat2 = concat2 + unicode(suffix[0][0][1:-1])
				desc.extend([[concat1, concat2, d.idx]])
			
			elif is_numeric == 1 and use_in_description == 1:
				concat=""
				concat2 = ""
				#Below query gets the values of description mentioned in the Attribute table
				#for Numeric values
				query1 = """SELECT iva.idx FROM `tabItem Variant Attribute` iva
					WHERE iva.attribute = '%s'""" %d.attribute
					
				prefix = frappe.db.sql("""SELECT iva.prefix FROM `tabItem Variant Attribute` iva
					WHERE iva.parent = '%s' AND iva.attribute = '%s' """ % (doc.variant_of, 
						d.attribute ), as_list=1)
					
				suffix = frappe.db.sql("""SELECT iva.suffix FROM `tabItem Variant Attribute` iva
					WHERE iva.parent = '%s' AND iva.attribute = '%s' """ % (doc.variant_of, 
						d.attribute ), as_list=1)
					
				concat = ""
				if prefix[0][0] <> '""':
					concat = unicode(prefix[0][0][1:-1]) + unicode('{0:g}'.format(d.attribute_value))
				else:
					concat = unicode('{0:g}'.format(d.attribute_value))

				if suffix[0][0]<> '""':
					concat = concat + unicode(suffix[0][0][1:-1])
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
			use_in_item_code = frappe.db.get_value("Item Attribute", d.attribute, 
				"use_in_item_code")
			if is_numeric <> 1 and use_in_item_code == 1:
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
			if abbr[i][0] <> '""':
				code = code + abbr[i][0]
		if len(serial[0][0]) > 2:
			code = code + serial[0][0]
		else:
			frappe.throw("Serial length is lower than 3 characters")
		chk_digit = fn_check_digit(doc,code)
		code = code + `chk_digit`
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

@frappe.whitelist()
def get_uom_factors(from_uom, to_uom):
	if (from_uom == to_uom): 
		return {'lft': 1, 'rgt': 1}
	return {
		'rgt': frappe.db.get_value('UOM Conversion Detail', filters={'parent': from_uom, 'uom': 
			to_uom}, fieldname='conversion_factor'),
		'lft': frappe.db.get_value('UOM Conversion Detail', filters={'parent': to_uom, 'uom': 
			from_uom}, fieldname='conversion_factor')
	}

 # searches for Item Attributes
def attribute_rm_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Is RM" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_bm_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Base Material" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_brand_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Brand" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_quality_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where (parent = 'HSS Quality' OR parent = 'Carbide Quality')
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_tt_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Tool Type" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_spl_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Special Treatment" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_purpose_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Purpose" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_type_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Type Selector" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})
def attribute_mtm_query(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""select attribute_value, parent from `tabItem Attribute Value`
		where parent = "Material to Machine" 
			AND ({key} like %(txt)s
				or attribute_value like %(txt)s)
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, attribute_value), locate(%(_txt)s, attribute_value), 99999),
			attribute_value
		limit %(start)s, %(page_len)s""".format(**{
			'key': searchfield,
			'mcond': get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
		})