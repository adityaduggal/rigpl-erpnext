# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe


def execute(filters=None):
    bm = filters.get("bm")
    conditions_it = get_conditions(bm, filters)
    columns = get_columns(filters)

    data = get_data(conditions_it, filters)
    return columns, data


def get_columns(filters):
    columns = [
        "Process Sheet:Link/Process Sheet:100", "Item:Link/Item:100", "BM::100", "TT::100", "SPL::100", "Qual::100",
        "Brand::100", "D1:Float:80", "W1:Float:80", "L1:Float:80", "D2:Float:80", "L2:Float:80", "Qty:Float:80",
        "Completed Qty:Float:80", "Status::100", "BT:Link/BOM Template RIGPL:100"
    ]
    return columns


def get_data(conditions_it, filters):
    query = """SELECT ps.name, ps.production_item, bm.attribute_value, tt.attribute_value, spl.attribute_value, 
    qual.attribute_value, brand.attribute_value, 
    bt.formula
        FROM `tabBOM Template RIGPL` bt %s %s
        ORDER BY %s bt.name""" % (conditions_it)
    data = frappe.db.sql(query, as_list=1)
    return data


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


def get_conditions(bm, filters):
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

    if filters.get("show_in_website") == 1:
        conditions_it += " and it.show_variant_in_website =%s" % filters.get("show_in_website")

    if filters.get("item"):
        conditions_it += " and it.name = '%s'" % filters.get("item")

    if filters.get("variant_of"):
        conditions_it += " and it.variant_of = '%s'" % filters.get("variant_of")

    return conditions_it
