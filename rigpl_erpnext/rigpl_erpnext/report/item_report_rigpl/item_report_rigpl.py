from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.query_builder.functions import IfNull
from frappe.utils import flt
from ....utils.item_attribute_utils import (
    attribute_filters,
    attribute_sort_key,
    chunks,
    get_attribute_details,
    get_attribute_map,
    get_attribute_values,
)
from ....utils.report_utils import blank_zeros
from ....utils.stock_utils import get_reorder_levels


def execute(filters=None):
    """
    Executes the report
    """
    if not filters:
        filters = {}
    check_tool_type(filters)
    items = get_item_list(filters)
    templates = list(dict.fromkeys(d.variant_of for d in items))
    if not templates:
        frappe.throw("No Temps in the given Criterion")

    att_details = get_attribute_details([t for t in templates if t])
    columns = get_columns(att_details)
    data = get_data(items, att_details)
    return columns, data


def check_tool_type(filters):
    if not filters.get("tt") and "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw("Please Select Tool Type")


def get_item_list(filters):
    """
    Returns the Items for the filters, with the Item fields of the report
    """
    it = frappe.qb.DocType("Item")
    query = (
        frappe.qb.from_(it)
        .select(
            it.name,
            it.lead_time_days,
            it.pack_size,
            it.selling_mov,
            it.min_order_qty,
            it.pl_item,
            it.stock_maintained,
            it.variant_of,
            it.description,
            it.end_of_life,
            it.owner,
            it.creation,
        )
        .where(attribute_filters(it.name, get_attribute_values(filters)))
    )
    if filters.get("eol"):
        query = query.where(IfNull(it.end_of_life, "2099-12-31") > filters["eol"])
    if filters.get("show_in_website") == 1:
        query = query.where(it.pl_item == 1)
    if filters.get("item"):
        query = query.where(it.name == filters["item"])
    if filters.get("variant_of"):
        query = query.where(it.variant_of == filters["variant_of"])
    return query.run(as_dict=True)


def get_columns(att_details):
    """
    Returns columns for the Report based on the attributes of the Templates
    """
    columns = [_("Item") + ":Link/Item:130"]
    for att in att_details:
        width = 10 * min(att.max_length, 10)
        col_type = "Float" if att.numeric_values == 1 else ""
        columns.append("%s:%s:%s" % (att.name_in_template, col_type, width))

    columns += [
        _("Lead Time") + ":Int:40",
        _("Pack Size") + ":Int:40",
        _("Selling MoV") + ":Int:40",
        _("Purchase MoQ") + ":Int:40",
        _("Is PL") + "::40",
        _("TOD") + "::40",
        _("ROL") + ":Int:40",
        _("Template or Variant Of") + ":Link/Item:300",
        _("Def Warehouse") + "::50",
        _("Def PL") + "::50",
        _("Description") + "::400",
        _("EOL") + ":Date:80",
        _("Created By") + "::150",
        _("Creation") + ":Date:150",
    ]
    return columns


def get_data(items, att_details):
    """
    Returns the report rows, sorted by the attribute columns and then the Item name
    """
    names = [d.name for d in items]
    attributes = [att.name for att in att_details]
    numeric = {att.name for att in att_details if att.numeric_values == 1}
    att_map = get_attribute_map(names, attributes)
    rol_dict = get_reorder_levels(names)
    defaults = get_item_defaults(names)
    items.sort(
        key=lambda d: (attribute_sort_key(att_map.get(d.name, {}), attributes, numeric), d.name)
    )

    data = []
    for d in items:
        values = att_map.get(d.name, {})
        row = [d.name]
        for att in attributes:
            value = values.get(att)
            if att in numeric:
                row.append(None if value is None else round(flt(value), 3))
            else:
                row.append("-" if value is None else value)
        default = defaults.get(d.name, {})
        row += [
            d.lead_time_days or None,
            d.pack_size or None,
            d.selling_mov or None,
            d.min_order_qty or None,
            "Yes" if d.pl_item else "No",
            "Yes" if d.stock_maintained else "No",
            rol_dict.get(d.name) or None,
            d.variant_of,
            if_none(default.get("default_warehouse"), "X"),
            if_none(default.get("default_price_list"), "X"),
            d.description,
            if_none(d.end_of_life, "2099-12-31"),
            d.owner,
            d.creation,
        ]
        data.append(blank_zeros(row))
    return data


def get_item_defaults(items):
    """
    Returns {item: first Item Default row by idx}
    """
    ide = frappe.qb.DocType("Item Default")
    defaults = {}
    for chunk in chunks(items):
        rows = (
            frappe.qb.from_(ide)
            .select(ide.parent, ide.default_warehouse, ide.default_price_list)
            .where(ide.parent.isin(chunk) & (ide.parenttype == "Item"))
            .orderby(ide.idx)
            .run(as_dict=True)
        )
        for row in rows:
            defaults.setdefault(row.parent, row)
    return defaults


def if_none(value, default):
    return default if value is None else value
