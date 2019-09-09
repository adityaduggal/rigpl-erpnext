# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, re
from frappe.utils import flt
import datetime

def check_and_copy_attributes_to_variant(template, variant, insert_type=None):
	from frappe.model import no_value_fields
	check = 0
	save_chk = 0
	copy_field_list = frappe.db.sql("""SELECT field_name FROM `tabVariant Field`""", as_list=1)
	include_fields = []
	for fields in copy_field_list:
		include_fields.append(fields[0])
	for field in template.meta.fields:
		# "Table" is part of `no_value_field` but we shouldn't ignore tables
		if (field.fieldtype == 'Table' or field.fieldtype not in no_value_fields) \
			and (not field.no_copy) and field.fieldname in include_fields:
			if variant.get(field.fieldname) != template.get(field.fieldname):
				if insert_type == "frontend":
					variant.set(field.fieldname, template.get(field.fieldname))
					frappe.msgprint ("Updated Item " + variant.name + " Field Changed = " + str(field.label) + 
						" Updated Value to " + str(template.get(field.fieldname)))
				else:
					frappe.db.set_value("Item", variant.name, field.fieldname, template.get(field.fieldname))
					print ("Updated Item " + variant.name + " Field Changed = " + str(field.label) + 
						" Updated Value to " + str(template.get(field.fieldname)))
				check += 1
		elif field.fieldname == 'description':
			description, long_desc = generate_description(variant)
			if variant.get(field.fieldname) != description:
				if insert_type == "frontend":
					variant.set(field.fieldname, template.get(field.fieldname))
				else:
					frappe.db.set_value("Item", variant.name, field.fieldname, description)
					frappe.db.set_value("Item", variant.name, "web_long_description", long_desc)
					frappe.db.set_value("Item", variant.name, "item_name", long_desc)
					print ("Updated Item " + variant.name + " Field Changed = " + str(field.label) + 
						" Updated Value to " + description)
		if insert_type != "frontend":
			frappe.db.set_value("Item", variant.name, "modified", datetime.datetime.now())
	return check

def web_catalog(it_doc):
	validate_stock_fields(it_doc)
	validate_restriction(it_doc)
	validate_item_defaults(it_doc)
	it_doc.website_image = it_doc.image
	it_doc.thumbnail = it_doc.image	
	if it_doc.pl_item == "Yes":
		it_doc.show_in_website = 1
		if it_doc.has_variants == 0:
			it_doc.show_variant_in_website = 1
		else:
			it_doc.show_variant_in_website = 0
	else:
		it_doc.show_in_website = 0
		it_doc.show_variant_in_website = 0
		
	if it_doc.show_in_website == 1:
		rol = frappe.db.sql("""SELECT warehouse_reorder_level 
			FROM `tabItem Reorder` 
			WHERE parent ='%s' """%(it_doc.name), as_list=1)
		if it_doc.item_defaults:
			for d in it_doc.item_defaults:
				it_doc.website_warehouse = d.default_warehouse
		if rol:
			it_doc.weightage = rol[0][0]

def validate_restriction(it_doc):
	if it_doc.has_variants == 1:
		#Check if the Restrictions Numeric check field is correctly selected
		for d in it_doc.item_variant_restrictions:
			if d.is_numeric == 1:
				if d.allowed_values:
					frappe.throw(("Allowed Values field not allowed for numeric \
						attribute {0}").format(d.attribute))
			elif d.is_numeric == 0:
				if d.rule:
					frappe.throw(("Rule not allowed for non-numeric \
						attribute {0}").format(d.attribute))

def validate_item_defaults(it_doc):
	if it_doc.item_defaults:
		if len(it_doc.item_defaults)>1:
			frappe.throw("Currently Only one line of defaults are supported")
		for d in it_doc.item_defaults:
			if d.default_warehouse:
				def_warehouse = d.default_warehouse
			else:
				frappe.throw("Default Warehouse is Mandatory for \
					Item Code: {}".format(it_doc.name))
			if d.default_price_list:
				def_price_list = d.default_price_list
			else:
				if it_doc.is_sales_item == 1:
					frappe.throw("Default Price List is Mandatory for \
						Item Code: {}".format(it_doc.name))


def generate_description(it_doc):
	if it_doc.variant_of:
		desc = []
		description = ""
		long_desc = ""
		for d in it_doc.attributes:
			concat = ""
			concat1 = ""
			concat2 = ""
			is_numeric = frappe.db.get_value("Item Attribute", d.attribute, "numeric_values")
			use_in_description = frappe.db.sql("""SELECT iva.use_in_description from  
				`tabItem Variant Attribute` iva 
				WHERE iva.parent = '%s' AND iva.attribute = '%s' """ %(it_doc.variant_of, 
					d.attribute), as_list=1)[0][0]
				
			if is_numeric != 1 and use_in_description == 1:
				#Below query gets the values of description mentioned in the Attribute table
				#for non-numeric values
				cond1 = d.attribute
				cond2 = d.attribute_value
				query = """SELECT iav.description, iav.long_description
					FROM `tabItem Attribute Value` iav, `tabItem Attribute` ia
					WHERE iav.parent = '%s' AND iav.parent = ia.name
					AND iav.attribute_value = '%s'""" %(cond1, cond2)				
				vatt_lst =frappe.db.sql(query, as_list=1)
				prefix = frappe.db.sql("""SELECT iva.prefix FROM `tabItem Variant Attribute` iva
					WHERE iva.parent = '%s' AND iva.attribute = '%s' """ % (it_doc.variant_of, 
						d.attribute ), as_list=1)

				suffix = frappe.db.sql("""SELECT iva.suffix FROM `tabItem Variant Attribute` iva
					WHERE iva.parent = '%s' AND iva.attribute = '%s' """ % (it_doc.variant_of, 
						d.attribute ), as_list=1)

				concat = ""
				concat2 = ""
				if prefix[0][0] != '""':
					if vatt_lst[0][0]:
						concat1 = str(prefix[0][0][1:-1]) + str(vatt_lst[0][0][1:-1])
					if vatt_lst[0][1]:
						concat2 = str(prefix[0][0][1:-1]) + str(vatt_lst[0][1][1:-1])
				else:
					if vatt_lst[0][0] != '""':
						concat1 = str(vatt_lst[0][0][1:-1])
					if vatt_lst[0][1] != '""':
						concat2 = str(vatt_lst[0][1][1:-1])

				if suffix[0][0]!= '""':
					concat1 = concat1 + str(suffix[0][0][1:-1])
					concat2 = concat2 + str(suffix[0][0][1:-1])
				desc.extend([[concat1, concat2, d.idx]])
			
			elif is_numeric == 1 and use_in_description == 1:
				concat=""
				concat2 = ""
				#Below query gets the values of description mentioned in the Attribute table
				#for Numeric values
				query1 = """SELECT iva.idx FROM `tabItem Variant Attribute` iva
					WHERE iva.attribute = '%s'""" %d.attribute
					
				prefix = frappe.db.sql("""SELECT iva.prefix FROM `tabItem Variant Attribute` iva
					WHERE iva.parent = '%s' AND iva.attribute = '%s' """ % (it_doc.variant_of, 
						d.attribute ), as_list=1)
					
				suffix = frappe.db.sql("""SELECT iva.suffix FROM `tabItem Variant Attribute` iva
					WHERE iva.parent = '%s' AND iva.attribute = '%s' """ % (it_doc.variant_of, 
						d.attribute ), as_list=1)
					
				concat = ""
				if prefix[0][0] != '""':
					if flt(d.attribute_value) > 0:
						concat = str(prefix[0][0][1:-1]) + str('{0:g}'.format(flt(d.attribute_value)))
				else:
					if flt(d.attribute_value) > 0:
						concat = str('{0:g}'.format(flt(d.attribute_value)))

				if suffix[0][0]!= '""':
					if concat:
						concat = concat + str(suffix[0][0][1:-1])
				desc.extend([[concat, concat, d.idx]])
			
			else:
				query1 = """SELECT iva.idx FROM `tabItem Variant Attribute` iva
					WHERE iva.attribute = '%s'""" %d.attribute	
				desc.extend([["","",frappe.db.sql(query1, as_list=1)[0][0]]])

		desc.sort(key=lambda x:x[2]) #Sort the desc as per priority lowest one is taken first
		for i in range(len(desc)):
			if desc[i][0] != '""':
				description = description + desc[i][0]
			if desc[i][1] != '""':
				long_desc = long_desc + desc[i][1]
	else:
		description = it_doc.name
		long_desc = it_doc.name
	return description, long_desc

def make_route(it_doc):
	route_name = (re.sub('[^A-Za-z0-9]+', ' ', it_doc.item_name))
	it_doc.route = frappe.db.get_value('Item Group', it_doc.item_group, 'route') + '/' + \
		it_doc.scrub(route_name)

def validate_reoder(it_doc):
	for val in it_doc.item_defaults:
		def_warehouse = val.default_warehouse
	for d in it_doc.reorder_levels:
		if d.warehouse != def_warehouse:
			d.warehouse = def_warehouse
	validate_valuation_rate(it_doc)

def validate_valuation_rate(it_doc):
	if it_doc.has_variants == 1 and it_doc.is_sales_item == 1:
		if it_doc.valuation_as_percent_of_default_selling_price == 0:
			frappe.throw("Valuation Rate Percent cannot be ZERO")

def validate_variants(it_doc, comm_type=None):
	user = frappe.session.user
	query = """SELECT role from `tabHas Role` where parent = '%s' """ %user
	roles = frappe.db.sql(query, as_list=1)

	if it_doc.show_in_website == 1:
		if it_doc.image is None:
			frappe.throw("For Website Items, Website Image is Mandatory \
				for Item Code {}".format(it_doc.name))
	if it_doc.variant_of:
		#Check if all variants are mentioned in the Item Variant Table as per the Template.
		template = frappe.get_doc("Item", it_doc.variant_of)
		check_item_defaults(template, it_doc, comm_type)
		template_attribute = []
		variant_attribute = []
		template_restricted_attributes = {}
		template_rest_summary = []
		

		for t in template.attributes:
			template_attribute.append(t.attribute)
		
		count = 0
		for d in it_doc.attributes:
			variant_attribute.append([d.attribute])
			variant_attribute[count].append(d.attribute_value)
			count +=1
		
		#First check the order of all the variants is as per the template or not.
		for i in range(len(template_attribute)):
			if len(template_attribute) == len(variant_attribute) and \
				template_attribute[i] != variant_attribute[i][0]:
				
				frappe.throw(("Item Code: {0} Row# {1} should have {2} as per the template")\
					.format(it_doc.name, i+1, template_attribute[i]))
			
			elif len(template_attribute) != len(variant_attribute):
				frappe.throw(("Item Code: {0} number of attributes not as per the template")\
					.format(it_doc.name))
		
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
		for d in it_doc.attributes:
			is_numeric = frappe.db.get_value("Item Attribute", d.attribute, \
			"numeric_values")
			if is_numeric == 1:
				d.attribute_value = flt(d.attribute_value)
			ctx[d.attribute] =  d.attribute_value

		original_keys = ctx.keys()
			
		for d in it_doc.attributes:
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
							'||': ' or ',
							'&gt;': '>',
							'&lt;': '<'
						}
						for k,v in repls.items():
							rule = rule.replace(k,v)
						try:
							valid = eval(rule, ctx, ctx)
						except Exception as e:
							frappe.throw("\n\n".join(map(str, [rule, {k:v for k,v in ctx.items() if k in original_keys}, e])))
							
						if not valid:
							frappe.throw('Item Code: {0} Rule "{1}" failing for field "{2}"'\
								.format(it_doc.name, rule, d.attribute))
			else:
				if template_restricted_attributes.get(d.attribute, {}).get('allows', False):
					if d.attribute_value not in template_restricted_attributes.get(d.attribute, {})\
						.get('allows', []):
						frappe.throw(("Item Code: {0} Attribute value {1} not allowed")\
							.format(it_doc.name, d.attribute_value))
		
		#Check the limit in the Template
		limit = template.variant_limit
		actual = frappe.db.sql("""SELECT count(name) FROM `tabItem` WHERE variant_of = '%s'""" \
			% template.name, as_list =1)
		
		check = frappe.db.sql("""SELECT name FROM `tabItem` WHERE name = '%s'""" \
			% it_doc.name, as_list = 1)
		
		if check:
			if actual[0][0] > limit:
				frappe.throw(("Template Limit reached. Set Limit = {0} whereas total \
					number of variants = {1} increase the limit to save the variant")\
						.format(limit, actual[0][0]))
			else:
				pass
		else:
			if actual[0][0] >= limit:
				frappe.throw(("Template Limit reached. Set Limit = {0} whereas total \
				number of variants = {1} increase the limit to save New Item Code")\
					.format(limit, actual[0][0]))
	elif it_doc.has_variants != 1:
		if any("System Manager" in s  for s in roles):
			pass
		else:
			frappe.throw("Only System Managers are Allowed to Create Non Template or Variant Items")
	elif it_doc.has_variants == 1:
		if any("System Manager" in s  for s in roles):
			pass
		else:
			frappe.throw("Only System Managers are Allowed to Edit Templates")

def check_item_defaults(template, variant, comm_type=None):
	field_list = ["company", "default_warehouse", "default_price_list", "income_account"]
	if template.item_defaults:
		#Check if Item Defaults exists in the Template
		t_def = 1
	else:
		t_def = 0

	if variant.item_defaults:
		#Check if Item Defaults exists in the Template
		v_def = 1
	else:
		v_def = 0

	if t_def == 1:
		if v_def == 1:
			is_it_def_same = compare_item_defaults(template, variant, field_list, comm_type)
			if is_it_def_same == 1:
				pass
			else:
				copy_item_defaults(template, variant, field_list, comm_type)
		#condition when template defaults are there then copy them
	else:
		frappe.throw("Item Defaults are Mandatory for Template {}".format(template.name))

def compare_item_defaults(template, variant, field_list, comm_type=None):
	i = 0
	for t in template.item_defaults:
		for v in variant.item_defaults:
			for f in field_list:
				if t.get(f) == v.get(f):
					pass
				else:
					copy_item_defaults(template, variant, field_list, comm_type)

def copy_item_defaults(template, variant, field_list, comm_type=None):
	variant.item_defaults = []
	variant_defaults = []
	var_def_dict = {}
	for t in template.item_defaults:
		for f in field_list:
			var_def_dict[f] = t.get(f)
		variant_defaults.append(var_def_dict)
	for i in variant_defaults:
		variant.append("item_defaults", i)
	if comm_type == "backend":
		it_def_name = frappe.db.sql("""SELECT name FROM `tabItem Default` WHERE parent= '%s' AND parenttype='Item'"""%(variant.name), as_list=1)
		if it_def_name:
			for t in template.item_defaults:
				for f in field_list:
					frappe.db.set_value("Item Default", it_def_name[0][0], f, t.get(f))
					frappe.db.set_value("Item", variant.name, "modified", datetime.datetime.now())

def validate_stock_fields(it_doc):
	#As per Company Policy on FIFO method of Valuation is to be Used.
	if it_doc.is_stock_item ==1:
		if it_doc.valuation_method != 'FIFO':
			frappe.throw("Select Valuation method as FIFO for Stock Item")
	if it_doc.is_purchase_item == 1:
		it_doc.default_material_request_type = 'Purchase'
	else:
		it_doc.default_material_request_type = 'Manufacture'

def validate_sales_fields(it_doc):
	if it_doc.is_sales_item == 1:
		if it_doc.sales_uom:
			pass
		else:
			frappe.throw("Sales UoM is Mandatory for Sales Item")
	if it_doc.pack_size == 0:
		frappe.throw("Pack Size should be Greater Than ZERO")
	if it_doc.selling_mov == 0:
		frappe.throw("Selling Minimum Order Value should be Greater than ZERO")