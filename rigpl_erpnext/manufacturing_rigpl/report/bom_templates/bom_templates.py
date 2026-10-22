# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import Count
from pypika.terms import Criterion
from ....utils.item_attribute_utils import attribute_sort_key, chunks, get_attribute_meta
from ....utils.report_utils import blank_zeros

BT = "BOM Template RIGPL"
FG = "fg_restrictions"


def execute(filters=None):
    values = get_restriction_values(filters)
    attributes = get_column_attributes(filters)
    columns = get_columns(attributes)
    data = get_data(attributes, values)
    return columns, data


def get_restriction_values(filters):
    """
    Returns {attribute: value} for the restriction filters
    """
    if filters.get("quality") and not filters.get("bm"):
        frappe.throw("Select Base Material before Selecting Quality")
    values = {
        "Base Material": filters.get("bm"),
        "Special Treatment": filters.get("spl"),
        "Tool Type": filters.get("tt"),
    }
    if filters.get("quality"):
        values["%s Quality" % filters["bm"]] = filters["quality"]
    return {attribute: value for attribute, value in values.items() if value}


def get_column_attributes(filters):
    """
    Returns the text attributes in the FG restrictions of the templates that match the Base
    Material and Tool Type filters, by name. These two filters look at all restriction tables.
    """
    ivr = frappe.qb.DocType("Item Variant Restrictions")
    query = (
        frappe.qb.from_(ivr)
        .select(ivr.attribute)
        .distinct()
        .where(ivr.parenttype == BT)
        .where(ivr.parentfield == FG)
        .where(ivr.is_numeric == 0)
    )
    for attribute, key in (("Base Material", "bm"), ("Tool Type", "tt")):
        if filters.get(key):
            match = frappe.qb.DocType("Item Variant Restrictions").as_("match_" + key)
            query = query.where(
                ivr.parent.isin(
                    frappe.qb.from_(match)
                    .select(match.parent)
                    .where(match.attribute == attribute)
                    .where(match.allowed_values == filters[key])
                )
            )
    return sorted(row[0] for row in query.run())


def get_columns(attributes):
    meta = get_attribute_meta(attributes)
    columns = ["BT Name:Link/BOM Template RIGPL:100"]
    for attribute in attributes:
        max_length = meta[attribute].max_length if attribute in meta else 0
        columns.append("%s::%s" % (attribute, (max_length or 6) * 8))
    columns += ["# of Ops:Int:50", "Routing:Link/Routing:150", "Remarks::400", "Formula::400"]
    return columns


def get_data(attributes, values):
    bt = frappe.qb.DocType(BT)
    templates = (
        frappe.qb.from_(bt)
        .select(bt.name, bt.routing, bt.remarks, bt.formula)
        .where(bt.docstatus == 0)
        .where(restriction_filters(bt.name, values))
        .run(as_dict=True)
    )
    names = [d.name for d in templates]
    restrictions = get_restriction_map(names, attributes)
    op_counts = get_operation_counts(names)
    templates.sort(key=lambda d: (attribute_sort_key(restrictions.get(d.name, {}), attributes, set()), d.name))
    data = []
    for d in templates:
        allowed = restrictions.get(d.name, {})
        row = [d.name] + [allowed_or_dash(allowed.get(attribute)) for attribute in attributes]
        row += [op_counts.get(d.name, 0), d.routing, d.remarks, d.formula]
        data.append(blank_zeros(row))
    return data


def restriction_filters(template_field, values):
    """
    Returns a criterion: `template_field` is a template with each allowed value in its FG restrictions
    """
    ivr = frappe.qb.DocType("Item Variant Restrictions")
    criteria = []
    for attribute, value in values.items():
        templates = (
            frappe.qb.from_(ivr)
            .select(ivr.parent)
            .where(ivr.parentfield == FG)
            .where(ivr.attribute == attribute)
            .where(ivr.allowed_values == value)
        )
        criteria.append(template_field.isin(templates))
    return Criterion.all(criteria)


def get_restriction_map(templates, attributes):
    """
    Returns {template: {attribute: allowed values}} from the FG restrictions
    """
    restrictions = {}
    if not attributes:
        return restrictions
    ivr = frappe.qb.DocType("Item Variant Restrictions")
    for chunk in chunks(templates):
        rows = (
            frappe.qb.from_(ivr)
            .select(ivr.parent, ivr.attribute, ivr.allowed_values)
            .where(ivr.parent.isin(chunk))
            .where(ivr.parentfield == FG)
            .where(ivr.attribute.isin(attributes))
            .run()
        )
        for parent, attribute, allowed_values in rows:
            restrictions.setdefault(parent, {})[attribute] = allowed_values
    return restrictions


def get_operation_counts(templates):
    op_counts = {}
    bop = frappe.qb.DocType("BOM Operation")
    for chunk in chunks(templates):
        rows = (
            frappe.qb.from_(bop)
            .select(bop.parent, Count(bop.name))
            .where(bop.parenttype == BT)
            .where(bop.parent.isin(chunk))
            .groupby(bop.parent)
            .run()
        )
        op_counts.update(dict(rows))
    return op_counts


def allowed_or_dash(value):
    return "-" if value is None else value
