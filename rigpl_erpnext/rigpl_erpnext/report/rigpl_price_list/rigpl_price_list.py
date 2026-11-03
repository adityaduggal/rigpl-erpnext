from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.query_builder.functions import IfNull
from frappe.utils import flt, nowdate
from pypika.terms import Case
from ....utils.item_attribute_utils import attribute_filters, attribute_sort_key, get_attribute_map, \
    get_attribute_meta
from ....utils.item_utils import get_distinct_attributes, get_pricing_rules_for_items


def execute(filters=None):
    """
    Executes the Report
    """
    if not filters:
        filters = {}
    check_filters(filters)
    templates = get_templates(filters)
    columns, attributes, att_details = get_columns(filters, templates)
    data = get_items(attributes, att_details, filters)

    return columns, data


def get_columns(filters, templates):
    """
    Returns Columns based on Filters and Templates found
    """
    if filters.get("price_list_type") == "Price List":
        columns = [
            _("PL ID") + ":Link/Item Price:80",
            {
                "label": _("PL"),
                "fieldname": "pl_name",
                "fieldtype": "Link",
                "options": "Price List",
                "width": 50
            },
            {
                "label": _("List Price"),
                "fieldname": "price",
                "fieldtype": "Currency",
                "width": 70
            },
            _("Cur") + "::40",
            {
                "label": _("Item"),
                "fieldname": "it_name",
                "fieldtype": "Link",
                "options": "Item",
                "width": 120
            }
        ]
    elif filters.get("price_list_type") == "Pricing Rule":
        columns = [
            {
                "label": _("PR ID"),
                "fieldname": "pr_id",
                "fieldtype": "Link",
                "options": "Pricing Rule",
                "width": 80,
                "ignore_permissions": True
            },
            {
                "label": _("Valid Upto"),
                "fieldname": "valid_upto",
                "fieldtype": "Date",
                "width": 80
            },
            {
                "label": _("MoQ"),
                "fieldname": "moq",
                "fieldtype": "Int",
                "width": 50
            },
            {
                "label": _("Price"),
                "fieldname": "price",
                "fieldtype": "Currency",
                "width": 70
            },
            {
                "label": _("Currency"),
                "fieldname": "currency",
                "fieldtype": "",
                "width": 50
            },
            {
                "label": _("Item"),
                "fieldname": "it_name",
                "fieldtype": "Link",
                "options": "Item",
                "width": 120
            }
        ]
    attributes = get_distinct_attributes(
        item_dict=templates, field_name="template")
    att_details = get_attribute_details(attributes, [d.template for d in templates])

    for att in attributes:
        col_dict = frappe._dict({})
        for i in att_details:
            if att.att_name == i["name"]:
                label = i["name_in_template"]
                if i["max_length"] > 10:
                    max_len = 10
                else:
                    max_len = i["max_length"]
                width = 10 * max_len
                if i["numeric_values"] == 1:
                    fd_type = "Float"
                else:
                    fd_type = ""
                col_dict["label"] = label
                col_dict["fieldname"] = att.att_sn
                col_dict["fieldtype"] = fd_type
                col_dict["width"] = width
                columns.append(col_dict.copy())
    columns = columns + [
        {
            "label": _("Is PL"),
            "fieldname": "is_pl",
            "fieldtype": "",
            "width": 40
        },
        {
            "label": _("ROL"),
            "fieldname": "rol",
            "fieldtype": "Int",
            "width": 40
        },
        {
            "label": _("Description"),
            "fieldname": "description",
            "fieldtype": "",
            "width": 300
        }
    ]
    return columns, attributes, att_details


def get_attribute_details(attributes, templates):
    """
    [{name, numeric_values, max_length, name_in_template}] of the report attributes, in 3 queries
    (get_attribute_meta and the field names of the templates) in place of 3 for each attribute.
    """
    names = [att.att_name for att in attributes]
    meta = get_attribute_meta(names)
    field_names = {}
    iva = frappe.qb.DocType("Item Variant Attribute")
    rows = (
        frappe.qb.from_(iva)
        .select(iva.attribute, iva.field_name)
        .where(iva.attribute.isin(names) & iva.parent.isin(templates))
        .run()
    ) if names and templates else []
    # The old query took the first row of GROUP BY field_name: the lowest field name, NULL first
    for attribute, field_name in sorted(rows, key=lambda r: (r[1] is not None, r[1] or "")):
        field_names.setdefault(attribute, field_name)
    details = []
    for att in attributes:
        att_meta = meta.get(att.att_name) or frappe._dict(numeric_values=0, hidden=0, max_length=0)
        sname = field_names.get(att.att_name)
        fd_n = att.att_name.split("_", 1)[1] if "_" in att.att_name else att.att_name
        if att_meta.numeric_values != 1:
            max_length = att_meta.max_length
            name_in_template = att.att_name
            if att_meta.hidden == 1:
                name_in_template = (sname or "").split("(", 1)[0] + "(" + fd_n + ")"
        else:
            max_length = 6
            name_in_template = sname.split("(", 1)[0] + "(" + fd_n + ")" if sname and "(" in sname else att.att_name
        details.append({"name": att.att_name, "numeric_values": att_meta.numeric_values,
            "max_length": int(max_length or 0), "name_in_template": name_in_template})
    return details


def get_items(attributes, att_details, filters):
    """
    Returns the report rows. The attribute values come from get_attribute_map and the rows are
    sorted in Python (#131), in place of 1 LEFT JOIN for each attribute.
    """
    numeric = {d["name"] for d in att_details if d["numeric_values"] == 1}
    names = [att.att_name for att in attributes]
    it = frappe.qb.DocType("Item")
    ro = frappe.qb.DocType("Item Reorder")
    rol = Case().when(ro.warehouse_reorder_level == 0, None).else_(ro.warehouse_reorder_level)
    query = (
        frappe.qb.from_(it)
        .left_join(ro).on((ro.parent == it.name) & (ro.warehouse == it.default_warehouse))
        .select(it.name, it.pl_item, rol.as_("rol"), it.description)
        .orderby(it.name)
    )
    query = add_item_filters(query, it, filters)
    if filters.get("price_list_type") == "Price List":
        itp = frappe.qb.DocType("Item Price")
        query = (query.left_join(itp).on((itp.item_code == it.name) & (itp.price_list == filters.get("pl")))
            .select(IfNull(itp.name, "-").as_("price_id"), IfNull(itp.price_list, "-").as_("price_list"),
                itp.price_list_rate, IfNull(itp.currency, "-").as_("currency")))
    elif filters.get("price_list_type") == "Pricing Rule":
        query = query.where(it.has_variants == 0)
    else:
        frappe.throw(f"Wrong Price List Type Selected {filters.get('price_list_type')}")
    rows = query.run(as_dict=1)
    att_map = get_attribute_map({row.name for row in rows}, names)
    rows.sort(key=lambda row: attribute_sort_key(att_map.get(row.name, {}), names, numeric))

    def attribute_cols(item):
        values = att_map.get(item, {})
        return [(flt(values[att], 3) if att in numeric else values[att]) if values.get(att) is not None
            else (None if att in numeric else "-") for att in names]

    data = []
    if filters.get("price_list_type") == "Price List":
        for row in rows:
            data.append([row.price_id, row.price_list, row.price_list_rate, row.currency, row.name]
                + attribute_cols(row.name) + ["Yes" if row.pl_item else "No", row.rol, row.description])
        return data

    rules = get_pricing_rules_for_items([row.name for row in rows], filters.get("valid_from"),
        filters.get("valid_upto"))
    for row in rows:
        item_rules = [[prl.name, prl.valid_upto, prl.min_qty, prl.rate, prl.currency, row.name]
            for prl in rules.get(row.name, [])]
        if not item_rules and filters.get("show_zero") == 1:
            item_rules = [[None, None, None, None, None, row.name]]
        tail = [None if not value or value == "None" else value for value in attribute_cols(row.name)] \
            + ["Yes" if row.pl_item else "No", row.rol, row.description]
        data.extend(rule + tail for rule in item_rules)
    return data


def add_item_filters(query, it, filters):
    """The Item filters of the report: not end of life, the attribute values and the Item fields."""
    bm = filters.get("bm")
    query = query.where(IfNull(it.end_of_life, "2099-12-31") > nowdate())
    if filters.get("eol"):
        query = query.where(IfNull(it.end_of_life, "2099-12-31") > filters["eol"])
    query = query.where(attribute_filters(it.name, {
        "Base Material": bm,
        "Series": filters.get("series"),
        f"{bm} Quality": filters.get("quality") if bm else None,
        "Tool Type": filters.get("tt"),
    }))
    if filters.get("item"):
        query = query.where(it.name == filters["item"])
    # The filter is a Yes/No select; pl_item is a Check (#106)
    if filters.get("is_pl") in ("Yes", "No"):
        query = query.where(it.pl_item == (1 if filters.get("is_pl") == "Yes" else 0))
    if filters.get("template"):
        query = query.where(it.variant_of == filters["template"])
    return query


def get_templates(filters):
    """
    Returns Templates based on Base Material and other filters
    """
    it = frappe.qb.DocType("Item")
    query = add_item_filters(frappe.qb.from_(it).select(it.variant_of.as_("template")).distinct(), it, filters)
    templates = query.run(as_dict=1)
    if not templates:
        frappe.throw("No Temps in the given Criterion")
    return templates


def check_filters(filters):
    """
    Only a System Manager can report a disabled or non-selling Price List, or all Tool Types
    """
    is_manager = "System Manager" in frappe.get_roles(frappe.session.user)
    pld = frappe.db.get_value("Price List", filters.get("pl"), ["enabled", "selling", "disable_so"], as_dict=1)
    if not pld:
        frappe.throw("Select a Price List")
    if (pld.enabled == 0 or pld.selling == 0 or pld.disable_so == 1) and not is_manager:
        frappe.throw("Price List Selected is Not Allowed for Reporting")
    if filters.get("price_list_type") != "Price List" and not filters.get("valid_upto"):
        frappe.throw("Valid Upto Date is needed for Special Pricing")
    if not filters.get("tt") and not is_manager:
        frappe.throw("Please select Tool Type to Proceed")
