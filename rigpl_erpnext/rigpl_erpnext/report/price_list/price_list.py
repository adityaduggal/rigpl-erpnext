from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils import flt, getdate, nowdate

def execute(filters=None):
	if not filters: filters = {}
	bm = filters["bm"]
	tt = filters["tt"]
	conditions_it, conditions_pl = get_conditions(bm, filters)
	templates = get_templates(bm, conditions_it, filters)

	columns, attributes, att_details = get_columns(templates)
	data = get_items(conditions_it, conditions_pl, attributes, att_details, filters)

	return columns, data

def get_columns(templates):
	columns = [
		_("PL ID") + ":Link/Item Price:80", _("PL") + "::50",
		_("List Price") + ":Currency:70", _("Cur") + "::40", 
		_("Item") + ":Link/Item:120"
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
		if attr.numeric_values <> 1:
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
	columns = columns + [_("Is PL") + "::40"] + [_("ROL") + ":Int:40"] + \
			[_("Description") + "::300"]
	return columns, attributes, att_details

def get_items(conditions_it, conditions_pl, attributes, att_details, filters):
	att_join = ''
	att_query = ''
	att_order = ''
	pl = " AND itp.price_list = '%s'" % filters.get("pl")
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
				
		att_join += """ LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent
			AND %s.attribute = '%s'""" %(att_trimmed,att_trimmed,att_trimmed,att)

	query = """SELECT IFNULL(itp.name, "-"), IFNULL(itp.price_list, "-"), itp.price_list_rate, 
		IFNULL(itp.currency, "-"), it.name %s, IFNULL(it.pl_item, "-"),
		IF(ro.warehouse_reorder_level =0, NULL, ro.warehouse_reorder_level),
		it.description
		FROM `tabItem` it 
			LEFT JOIN `tabItem Price` itp ON it.name = itp.item_code %s
			LEFT JOIN `tabItem Reorder` ro ON it.name = ro.parent 
				AND ro.warehouse = it.default_warehouse %s
		WHERE 
			IFNULL(it.end_of_life, '2099-12-31') > CURDATE() %s
		ORDER BY %s it.name""" %(att_query, pl, att_join, conditions_it, att_order)
	
	data = frappe.db.sql(query, as_list=1)
	
	return data

def define_join(string, tab,val):
	string += """ LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent
			AND %s.attribute = '%s'""" %(tab, tab, tab, val)
	return string
	
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
		FROM `tabItem` it %s 
		WHERE IFNULL(it.end_of_life, '2099-12-31') > CURDATE() %s""" %(query_join, conditions_it)
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
		conditions_pl += " AND itp.price_list = '%s'" % filters["pl"]
	
	if filters.get("eol"):
		conditions_it += " WHERE IFNULL(it.end_of_life, '2099-12-31') > '%s'" % filters["eol"]

	if filters.get("bm"):
		conditions_it += " AND BaseMaterial.attribute_value = '%s'" % filters["bm"]
		
	if filters.get("series"):
		conditions_it += " AND Series.attribute_value = '%s'" % filters["series"]

	if filters.get("quality"):
		conditions_it += " AND %sQuality.attribute_value = '%s'" % (bm, filters["quality"])

	if filters.get("spl"):
		conditions_it += " AND SpecialTreatment.attribute_value = '%s'" % filters["spl"]

	if filters.get("purpose"):
		conditions_it += " AND Purpose.attribute_value = '%s'" % filters["purpose"]
		
	if filters.get("type"):
		conditions_it += " AND TypeSelector.attribute_value = '%s'" % filters["type"]
		
	if filters.get("mtm"):
		conditions_it += " AND MaterialtoMachine.attribute_value = '%s'" % filters["mtm"]
		
	if filters.get("tt"):
		conditions_it += " AND ToolType.attribute_value = '%s'" % filters["tt"]

	if filters.get("item"):
		conditions_it += " and it.name = '%s'" % filters["item"]
	
	if filters.get("is_pl"):
		conditions_it += " AND it.pl_item = 'Yes'"
	
	if filters.get("template"):
		conditions_it += " AND it.variant_of = '%s'" % filters["template"]

	return conditions_it, conditions_pl
