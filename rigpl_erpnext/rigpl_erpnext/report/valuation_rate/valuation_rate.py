# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils import flt, getdate, nowdate

def execute(filters=None):
	if not filters: filters = {}
	bm = filters.get("bm")
	tt = filters.get("tt")
	
	conditions_it, conditions_pl = get_conditions(bm, filters)
	templates = get_templates(bm, conditions_it, filters)
	
	columns, attributes, att_details =  get_columns(templates)
	items = get_items(conditions_it, conditions_pl, attributes, att_details, filters)

	return columns, items
	
def get_columns(templates):
	columns = [
		_("Item") + ":Link/Item:130", 
		_("Rate") + ":Currency:80", _("Valuation Rate Date") + ":Date:80", 
		_("Base on PL") + ":Link/Price List:80", 
		_("PL Rate") + ":Currency:80", _("%age of PL") + ":Float:80",
		_("Set %age") + ":Float:80"
	]
	
	attributes = []		
	attributes = frappe.db.sql_list("""SELECT DISTINCT(iva.attribute)
		FROM `tabItem Variant Attribute` iva
		WHERE
			iva.parent in (%s)
		ORDER BY iva.idx""" % 
		(', '.join(['%s']*len(templates))), tuple([d.variant_of for d in templates]))
	
	att_details = []
	#above dict would be as below
	#[{name: "Base Material", max_length: 20, numeric_values:0, name_in_template: "bm"}]
	for i in attributes:
		dict = {}
		
		cond = """ attribute = '%s'""" %(i)
		att_name = frappe.db.sql("""SELECT name, attribute, field_name FROM `tabItem Variant Attribute` 
			WHERE {condition} AND parent IN (%s) GROUP BY field_name""".format(condition=cond) \
			%(", ".join(['%s']*len(templates))), \
			tuple([d.variant_of for d in templates]), as_dict=1)
		
		attr = frappe.get_doc("Item Attribute", i)
		dict["name"] = i
		dict["numeric_values"] = attr.numeric_values
		if attr.numeric_values != 1:
			max_length = frappe.db.sql("""SELECT MAX(CHAR_LENGTH(attribute_value))
				FROM `tabItem Attribute Value` WHERE parent = '%s'"""%(i), as_list=1)
			if attr.hidden == 1:
				s = att_name[0].field_name
				n = i.split('_', 1)[1]
				nit = s.split('(', 1)[0] + "(" + n + ")"
				name_in_template = nit
			else:
				name_in_template = att_name[0].attribute
		else:
			max_length = [[6]]
			s = att_name[0].field_name
			if '_' in i:
				n = i.split('_', 1)[1]
			else:
				n = i
			if '(' in s:
				nit = s.split('(', 1)[0] + "(" + n + ")"
			else:
				nit = i
			name_in_template = nit
			
		dict["max_length"] = int(max_length[0][0])
		dict["name_in_template"] = name_in_template
		att_details.append(dict.copy())

	for att in attributes:
		for i in att_details:
			if att == i["name"]:
				label = i["name_in_template"]
				if i["max_length"] > 10:
					max = 10
				else:
					max = i["max_length"]
				width = 10 * max
				if i["numeric_values"] == 1:
					col = ":Float:%s" %(width)
				else:
					col = "::%s" %(width)
				columns = columns + [(label + col)]
	
	columns = columns +  \
		[_("Description") + "::400"] + [_("EOL") + ":Date:80"] + [_("Created By") + "::150"] + \
		[_("Creation") + ":Date:150"]

	
	return columns, attributes, att_details
	
def get_items(conditions_it, conditions_pl, attributes, att_details, filters):
	att_join = ''
	att_query = ''
	att_order = ''
	for att in attributes:
		att_trimmed = att.replace(" ", "")
		for i in att_details:
			if att == i["name"]:
				if i["numeric_values"] == 1:
					att_query += """, CAST(%s.attribute_value AS DECIMAL(8,3))""" %(att_trimmed)
					att_order += """CAST(%s.attribute_value AS DECIMAL(8,3)), """ %(att_trimmed)
				else:
					att_query += """, IFNULL(%s.attribute_value, "-")""" %(att_trimmed)
					att_order += """%s.attribute_value, """ %(att_trimmed)
				
		att_join += """LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent
			AND %s.attribute = '%s'""" %(att_trimmed,att_trimmed,att_trimmed,att)

	query = """SELECT it.name, it.valuation_rate, it.valuation_rate_date, itp.price_list, 
		itp.price_list_rate,  (it.valuation_rate/itp.price_list_rate*100), 
		it.valuation_as_percent_of_default_selling_price %s, 
		it.description, IFNULL(it.end_of_life, '2099-12-31'),
		IFNULL(it.owner, "X"), it.creation
		FROM `tabItem` it
			LEFT JOIN `tabItem Price` itp ON it.name = itp.item_code %s
			%s %s 
		ORDER BY %s it.name""" %(att_query, conditions_pl, att_join, conditions_it, att_order)

	items = frappe.db.sql(query, as_list=1)

	return items

def get_templates(bm, conditions_it, filters):
	query_join = ""
	if filters.get("rm"):
		tab = 'Is RM'
		query_join = define_join(query_join, tab.replace(" ", ""), tab)
		
	if filters.get("bm"):
		tab = 'Base Material'
		query_join = define_join(query_join, tab.replace(" ", ""), tab)
		
	if filters.get("tt"):
		tab = 'Tool Type'
		query_join = define_join(query_join, tab.replace(" ", ""), tab)
		
	if filters.get("quality"):
		tab = '%s Quality' %(bm)
		query_join = define_join(query_join, tab.replace(" ", ""), tab)
		
	if filters.get("series"):
		tab = 'Series'
		query_join = define_join(query_join, tab.replace(" ", ""), tab)
		
	if filters.get("spl"):
		tab = 'Special Treatment'
		query_join = define_join(query_join, tab.replace(" ", ""), tab)
		
	if filters.get("purpose"):
		tab = 'Purpose'
		query_join = define_join(query_join, tab.replace(" ", ""), tab)
		
	if filters.get("type"):
		tab = 'Type Selector'
		query_join = define_join(query_join, tab.replace(" ", ""), tab)
		
	if filters.get("mtm"):
		tab = 'Material to Machine'
		query_join = define_join(query_join, tab.replace(" ", ""), tab)
		
	query = """SELECT DISTINCT(it.variant_of) 
		FROM `tabItem` it %s %s""" %(query_join, conditions_it)
		
	templates = frappe.db.sql(query, as_dict=1)
	
	if templates:
		pass
	else:
		frappe.throw("No Temps in the given Criterion")
	
	return templates
	
def get_conditions(bm, filters):
	conditions_it = ""
	conditions_pl = ""
	
	if filters.get("pl"):
		conditions_pl += " AND itp.price_list = '%s'" % filters.get("pl")
		
	if filters.get("eol"):
		conditions_it += " WHERE IFNULL(it.end_of_life, '2099-12-31') > '%s'" % filters.get("eol")
	
	if filters.get("rm"):
		conditions_it += " AND IsRM.attribute_value = '%s'" % filters.get("rm")

	if filters.get("bm"):
		conditions_it += " AND BaseMaterial.attribute_value = '%s'" % filters.get("bm")
		
	if filters.get("series"):
		conditions_it += " AND Series.attribute_value = '%s'" % filters.get("series")

	if filters.get("quality"):
		conditions_it += " AND %sQuality.attribute_value = '%s'" % (bm, filters.get("quality"))

	if filters.get("spl"):
		conditions_it += " AND SpecialTreatment.attribute_value = '%s'" % filters.get("spl")

	if filters.get("purpose"):
		conditions_it += " AND Purpose.attribute_value = '%s'" % filters.get("purpose")
		
	if filters.get("type"):
		conditions_it += " AND TypeSelector.attribute_value = '%s'" % filters.get("type")
		
	if filters.get("mtm"):
		conditions_it += " AND MaterialtoMachine.attribute_value = '%s'" % filters.get("mtm")
		
	if filters.get("tt"):
		conditions_it += " AND ToolType.attribute_value = '%s'" % filters.get("tt")

	if filters.get("show_in_website") ==1:
		conditions_it += " and it.show_in_website =%s" % filters.get("show_in_website")

	if filters.get("item"):
		conditions_it += " and it.name = '%s'" % filters.get("item")
	
	if filters.get("variant_of"):
		conditions_it += " and it.variant_of = '%s'" % filters.get("variant_of")
		
	return conditions_it, conditions_pl

def define_join(string, tab,val):
	string += """ LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent
			AND %s.attribute = '%s'""" %(tab, tab, tab, val)
	return string
