# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from operator import itemgetter


def execute(filters=None):
    cond_rest = get_conditions(filters)
    bm = filters.get("bm")
    columns, rest_details, restrictions = get_columns(filters)

    data = get_data(cond_rest, restrictions, rest_details, filters)
    return columns, data


def get_columns(filters):
    columns = [
        "BT Name:Link/BOM Template RIGPL:100"
    ]
    restrictions = frappe.db.sql("""SELECT DISTINCT(ivr.attribute) AS attribute, ivr.is_numeric AS numeric_val
    FROM `tabItem Variant Restrictions` ivr 
    WHERE parenttype = 'BOM Template RIGPL' AND parentfield = 'fg_restrictions' """, as_dict=1)
    restrictions = sorted(restrictions, key=itemgetter("numeric_val", "attribute"))
    rest_details = []
    for rest in restrictions:
        temp_dict = {}
        temp_dict["name"] = rest.attribute
        temp_dict["is_numeric"] = rest.numeric_val
        if rest.numeric_val != 1:
            max_length = frappe.db.sql("""SELECT MAX(CHAR_LENGTH(attribute_value)) FROM `tabItem Attribute Value` WHERE 
                parent = '%s'""" % (rest.attribute), as_list=1)
            temp_dict["max_length"] = max_length[0][0]
        else:
            temp_dict["max_length"] = 6
        rest_details.append(temp_dict.copy())
    for rest in rest_details:
        col_string = str(rest.get("name")) + '::' + str(rest.get("max_length")*8)
        columns.append(col_string)
    columns.append('# of Ops:In:50, ')
    columns.append('Routing:Link/Routing:150, ')
    columns.append('Remarks::300, ')
    columns.append('Formula::300')
    return columns, rest_details, restrictions


def get_data(cond_rest, restrictions, att_details, filters):
    att_join = ''
    att_query = ''
    att_order = ''
    for att in restrictions:
        att_trimmed = (att.attribute).replace(" ", "")
        for i in att_details:
            if att.attribute == i["name"]:
                att_query += """, IFNULL(%s.allowed_values, "-")""" % att_trimmed
                att_order += """%s.allowed_values, """ % att_trimmed

        att_join += """ LEFT JOIN `tabItem Variant Restrictions` %s ON bt.name = %s.parent
            AND %s.parentfield = 'fg_restrictions' AND %s.attribute = '%s'""" % \
                    (att_trimmed, att_trimmed, att_trimmed, att_trimmed, att.attribute)

    query = """SELECT bt.name %s, (SELECT COUNT(name) FROM `tabBOM Operation` WHERE 
        parenttype = 'BOM Template RIGPL' AND parent = bt.name),bt.routing, bt.remarks, bt.formula
        FROM `tabBOM Template RIGPL` bt %s %s
        ORDER BY %s bt.name""" % (att_query, att_join, cond_rest, att_order)
    data = frappe.db.sql(query, as_list=1)
    return data


def get_conditions(filters):
    cond_rest = ""

    if filters.get("rm"):
        cond_rest += " AND IsRM.allowed_values = '%s'" % filters.get("rm")

    if filters.get("bm"):
        cond_rest += " AND BaseMaterial.allowed_values = '%s'" % filters.get("bm")

    if filters.get("series"):
        cond_rest += " AND Series.allowed_values = '%s'" % filters.get("series")

    if filters.get("quality"):
        cond_rest += " AND %sQuality.allowed_values = '%s'" % (bm, filters.get("quality"))

    if filters.get("spl"):
        cond_rest += " AND SpecialTreatment.allowed_values = '%s'" % filters.get("spl")

    if filters.get("purpose"):
        cond_rest += " AND Purpose.allowed_values = '%s'" % filters.get("purpose")

    if filters.get("type"):
        cond_rest += " AND TypeSelector.allowed_values = '%s'" % filters.get("type")

    if filters.get("mtm"):
        cond_rest += " AND MaterialtoMachine.allowed_values = '%s'" % filters.get("mtm")

    if filters.get("tt"):
        cond_rest += " AND ToolType.allowed_values = '%s'" % filters.get("tt")

    return cond_rest


def define_join(string, table_name, allowed_values):
    string += """ LEFT JOIN `tabItem Variant Restrictions` %s ON bt.name = %s.parent AND %s.attribute = '%s' AND 
    %s.parentfield = 'fg_restrictions' AND %s.parenttype = 'BOM Template RIGPL'""" % \
              (table_name, table_name, table_name, table_name, table_name, allowed_values)
    return string


def get_joins(bm, cond_rest, filters):
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
        tab = '%s Quality' % (bm)
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

    return query_join
