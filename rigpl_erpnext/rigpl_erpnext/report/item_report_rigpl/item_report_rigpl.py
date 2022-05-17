from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    """
    Executes the report
    """
    if not filters:
        filters = {}
    bmat = filters.get("bm")
    conditions_it = get_conditions(bmat, filters)
    templates = get_templates(bmat, conditions_it, filters)

    columns, attributes, att_details = get_columns(templates)
    data = get_items(conditions_it, attributes, att_details)

    return columns, data


def get_columns(templates):
    """
    Returns columns for the Report based on the Templates
    """
    columns = [
            _("Item") + ":Link/Item:130"
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
    for row in attributes:
        format_dict = frappe._dict({})
        cond = f""" attribute = '{row}'"""
        att_name = frappe.db.sql("""SELECT name, attribute, field_name
            FROM `tabItem Variant Attribute` WHERE {condition} AND parent IN (%s)
            GROUP BY field_name""".format(condition=cond)
                %(", ".join(['%s']*len(templates))),
                tuple([d.variant_of for d in templates]), as_dict=1)

        attr = frappe.get_doc("Item Attribute", row)
        format_dict["name"] = row
        format_dict["numeric_values"] = attr.numeric_values
        if attr.numeric_values != 1:
            max_length = frappe.db.sql("""SELECT MAX(CHAR_LENGTH(attribute_value))
				FROM `tabItem Attribute Value` WHERE parent = '%s'""" %(row), as_list=1)
            if attr.hidden == 1:
                sname = att_name[0].field_name
                n_row = row.split('_', 1)[1]
                nit = sname.split('(', 1)[0] + "(" + n_row + ")"
                name_in_template = nit
            else:
                name_in_template = att_name[0].attribute
        else:
            max_length = [[6]]
            sname = att_name[0].field_name
            if '_' in row:
                n_row = row.split('_', 1)[1]
            else:
                n_row = row
            if sname and '(' in sname:
                nit = sname.split('(', 1)[0] + "(" + n_row + ")"
            else:
                nit = row
            name_in_template = nit

        format_dict["max_length"] = int(max_length[0][0])
        format_dict["name_in_template"] = name_in_template
        att_details.append(format_dict.copy())

    for att in attributes:
        for i in att_details:
            if att == i["name"]:
                label = i["name_in_template"]
                if i["max_length"] > 10:
                    wd_max = 10
                else:
                    wd_max = i["max_length"]
                width = 10 * wd_max
                if i["numeric_values"] == 1:
                    col = ":Float:%s" %(width)
                else:
                    col = "::%s" %(width)
                columns = columns + [(label + col)]

    columns = columns + [_("Lead Time") + ":Int:40"] + [_("Pack Size") + ":Int:40"] + \
            [_("Selling MoV") + ":Int:40"] + [_("Purchase MoQ") + ":Int:40"] + \
            [_("Is PL") + "::40"] + [_("TOD") + "::40"] +[_("ROL") + ":Int:40"] + \
            [_("Template or Variant Of") + ":Link/Item:300"] + \
            [_("Def Warehouse") + "::50"] + [_("Def PL") + "::50"] + \
            [_("Description") + "::400"] + [_("EOL") + ":Date:80"] + [_("Created By") + "::150"] + \
            [_("Creation") + ":Date:150"]

    return columns, attributes, att_details

def define_join(string, tab,val):
    """
    Defines join for SQL query for attribute
    """
    string += """ LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent
			AND %s.attribute = '%s'""" %(tab, tab, tab, val)
    return string

def get_templates(bmat, conditions_it, filters):
    """
    Returns templates based on conditions and filters
    """
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
        tab = '%s Quality' %(bmat)
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

    if not templates:
        frappe.throw("No Temps in the given Criterion")
    return templates

def get_items(conditions_it, attributes, att_details):
    """
    Retunrs Items based on Conditions, Attributes and Attribute Details
    """
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

    query = """SELECT it.name %s, IF(it.lead_time_days =0, NULL, it.lead_time_days),
		IF(it.pack_size =0, NULL, it.pack_size),
		IF(it.selling_mov =0, NULL, it.selling_mov),
		IF(it.min_order_qty =0, NULL, it.min_order_qty),
		IFNULL(it.pl_item, "-"), IFNULL(it.stock_maintained, "-"),
		IF(ro.warehouse_reorder_level =0, NULL, ro.warehouse_reorder_level),
		it.variant_of, IFNULL(def.default_warehouse, "X"),
		IFNULL(def.default_price_list, 'X'),
		it.description, IFNULL(it.end_of_life, '2099-12-31'),
		it.owner, it.creation
		FROM `tabItem` it
			LEFT JOIN `tabItem Reorder` ro ON it.name = ro.parent
			LEFT JOIN `tabItem Default` def ON it.name = def.parent
			%s %s
		ORDER BY %s it.name""" %(att_query, att_join, conditions_it, att_order)

    data = frappe.db.sql(query, as_list=1)
    return data


def get_conditions(bmat, filters):
    """
    Returns Conditions based on filters selected
    """
    conditions_it = ""

    if filters.get("eol"):
        conditions_it += " WHERE IFNULL(it.end_of_life, '2099-12-31') > '%s'" % filters.get("eol")

    if filters.get("rm"):
        conditions_it += " AND IsRM.attribute_value = '%s'" % filters.get("rm")

    if filters.get("bm"):
        conditions_it += " AND BaseMaterial.attribute_value = '%s'" % filters.get("bm")

    if filters.get("series"):
        conditions_it += " AND Series.attribute_value = '%s'" % filters.get("series")

    if filters.get("quality"):
        conditions_it += " AND %sQuality.attribute_value = '%s'" % (bmat, filters.get("quality"))

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
    else:
        user_roles = frappe.get_roles(frappe.session.user)
        if "System Manager" not in user_roles:
            frappe.throw("Please Select Tool Type")

    if filters.get("show_in_website") ==1:
        conditions_it += " and it.show_variant_in_website =%s" % filters.get("show_in_website")

    if filters.get("item"):
        conditions_it += " and it.name = '%s'" % filters.get("item")

    if filters.get("variant_of"):
        conditions_it += " and it.variant_of = '%s'" % filters.get("variant_of")

    return conditions_it
