from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils import flt, getdate, nowdate
from ....utils.item_utils import get_distinct_attributes, get_pricing_rule_for_item


def execute(filters=None):
    """
    Executes the Report
    """
    if not filters:
        filters = {}
    bmat = filters.get("bm")
    conditions_it = get_conditions(filters)[0]
    templates = get_templates(bmat, conditions_it, filters)
    columns, attributes, att_details = get_columns(filters, templates)
    # frappe.throw(str(columns))
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
    att_details = []
    # above dict would be as below
    #[{name: "Base Material", max_length: 20, numeric_values:0, name_in_template: "bm"}]
    for att in attributes:
        at_dt = {}

        cond = f""" attribute = '{att.att_name}'"""
        att_name = frappe.db.sql("""SELECT name, attribute, field_name
            FROM `tabItem Variant Attribute`
            WHERE {condition} AND parent IN (%s) GROUP BY field_name""".format(condition=cond)
                                 % (", ".join(['%s']*len(templates))),
                                 tuple([d.template for d in templates]), as_dict=1)

        attr = frappe.get_doc("Item Attribute", att.att_name)
        at_dt["name"] = att.att_name
        at_dt["numeric_values"] = attr.numeric_values
        if attr.numeric_values != 1:
            max_length = frappe.db.sql(f"""SELECT MAX(CHAR_LENGTH(attribute_value))
                FROM `tabItem Attribute Value` WHERE parent = '{att.att_name}'""", as_list=1)
            if attr.hidden == 1:
                sname = att_name[0].field_name
                fd_n = (att.att_name).split('_', 1)[1]
                nit = sname.split('(', 1)[0] + "(" + fd_n + ")"
                name_in_template = nit
            else:
                name_in_template = att_name[0].attribute
        else:
            max_length = [[6]]
            sname = att_name[0].field_name
            if '_' in att.att_name:
                fd_n = (att.att_name).split('_', 1)[1]
            else:
                fd_n = att.att_name
            if sname and '(' in sname:
                nit = sname.split('(', 1)[0] + "(" + fd_n + ")"
            else:
                nit = att.att_name
            name_in_template = nit
        at_dt["max_length"] = int(max_length[0][0])
        at_dt["name_in_template"] = name_in_template
        att_details.append(at_dt.copy())

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


def get_items(attributes, att_details, filters):
    """
    Returns items for the Attributes and Filters
    """
    conditions_it = get_conditions(filters=filters)[0]
    att_join = ''
    att_query = ''
    att_order = ''
    data = []
    plist = " AND itp.price_list = '%s'" % filters.get("pl")
    for att in attributes:
        att_trimmed = (att.att_name).replace(" ", "")
        for i in att_details:
            if att.att_name == i["name"]:
                if i["numeric_values"] == 1:
                    att_query += f""", CAST({att_trimmed}.attribute_value AS DECIMAL(8,3)) \
                    AS {att.att_sn}"""
                    att_order += f"""CAST({att_trimmed}.attribute_value AS DECIMAL(8,3)), """
                else:
                    att_query += f""", IFNULL({att_trimmed}.attribute_value, "-") AS {att.att_sn}"""
                    att_order += f"""{att_trimmed}.attribute_value, """

        att_join += f""" LEFT JOIN `tabItem Variant Attribute` {att_trimmed}
        ON it.name = {att_trimmed}.parent AND {att_trimmed}.attribute = '{att.att_name}'"""
    if filters.get("price_list_type") == "Price List":
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
            ORDER BY %s it.name""" % (att_query, plist, att_join, conditions_it, att_order)
        data = frappe.db.sql(query, as_list=1)
    elif filters.get("price_list_type") == "Pricing Rule":
        query = f"""SELECT it.name {att_query}, IFNULL(it.pl_item, '-') as pl_item,
        IF(ro.warehouse_reorder_level =0, NULL, ro.warehouse_reorder_level) as rol, it.description
        FROM `tabItem` it
            LEFT JOIN `tabItem Reorder` ro ON it.name = ro.parent
            AND ro.warehouse = it.default_warehouse {att_join}
        WHERE it.has_variants = 0 AND IFNULL(it.end_of_life, '2099-12-31') > CURDATE()
        {conditions_it} ORDER BY {att_order} it.name"""
        data_dict = frappe.db.sql(query, as_dict=1)
        for itm in data_dict:
            rows = []
            frm_dt = filters.get("valid_from")
            to_dt = filters.get("valid_upto")
            prule = get_pricing_rule_for_item(
                it_name=itm.name, frm_dt=frm_dt, to_dt=to_dt)
            if prule:
                for prl in prule:
                    drow = [prl.name, prl.valid_upto, prl.min_qty,
                            prl.rate, prl.currency, itm.name]
                    rows.append(drow)
            else:
                if filters.get("show_zero") == 1:
                    drow = [None, None, None, None, None, itm.name]
                    rows.append(drow)
                else:
                    drow = []
            if rows:
                for n_row in rows:
                    for att in attributes:
                        if not itm.get(att.att_sn, None) or itm.get(att.att_sn) == "None":
                            n_row += [None]
                        else:
                            n_row += [itm.get(att.att_sn)]
                    n_row += [itm.pl_item, itm.rol, itm.description]
            for n_row in rows:
                data.append(n_row)
    else:
        frappe.throw(f"Wrong Price List Type Selected {filters.get('price_list_type')}")

    return data


def define_join(string, tab, val):
    """
    Defines the Joins to be used for the Item Attributes
    """
    string += """ LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent
            AND %s.attribute = '%s'""" % (tab, tab, tab, val)
    return string


def get_templates(bmat, conditions_it, filters):
    """
    Returns Templates based on Conditions, Base Material and other filters
    """
    query_join = ""

    if filters.get("bm"):
        tab = 'Base Material'
        query_join = define_join(query_join, tab.replace(" ", ""), tab)

    if filters.get("tt"):
        tab = 'Tool Type'
        query_join = define_join(query_join, tab.replace(" ", ""), tab)

    if filters.get("quality"):
        tab = '%s Quality' % (bmat)
        query_join = define_join(query_join, tab.replace(" ", ""), tab)

    if filters.get("series"):
        tab = 'Series'
        query_join = define_join(query_join, tab.replace(" ", ""), tab)

    query = f"""SELECT DISTINCT(it.variant_of) as template FROM `tabItem` it {query_join}
        WHERE IFNULL(it.end_of_life, '2099-12-31') > CURDATE() {conditions_it}"""
    templates = frappe.db.sql(query, as_dict=1)

    if not templates:
        frappe.throw("No Temps in the given Criterion")
    return templates


def get_conditions(filters):
    """
    Gets conditions based on the Filters
    """
    conditions_it = ""
    conditions_pl = ""
    cond_pr = ""
    user_roles = frappe.get_roles(frappe.session.user)

    # Only allow Enabled Prices for Non-System Managers
    pld = frappe.get_doc("Price List", filters.get("pl"))
    if pld.enabled == 0 or pld.selling == 0 or pld.disable_so == 1:
        if "System Manager" not in user_roles:
            frappe.throw("Price List Selected is Not Allowed for Reporting")

    if filters.get("price_list_type") == "Price List":
        if filters.get("pl"):
            conditions_pl += " AND itp.price_list = '%s'" % filters.get("pl")
    else:
        if filters.get("valid_upto"):
            cond_pr += f" AND pr.valid_upto >= '{filters.get('valid_upto')}'"
        else:
            frappe.throw("Valid Upto Date is needed for Special Pricing")
        if filters.get("valid_from"):
            cond_pr += f" AND pr.valid_from >= '{filters.get('valid_from')}'"

    if filters.get("eol"):
        conditions_it += " WHERE IFNULL(it.end_of_life, '2099-12-31') > '%s'" % filters.get(
            "eol")

    if filters.get("bm"):
        conditions_it += " AND BaseMaterial.attribute_value = '%s'" % filters.get(
            "bm")

    if filters.get("series"):
        conditions_it += " AND Series.attribute_value = '%s'" % filters.get(
            "series")

    if filters.get("quality"):
        bm = filters.get("bm")
        conditions_it += " AND %sQuality.attribute_value = '%s'" % (
            bm, filters.get("quality"))

    if filters.get("tt"):
        conditions_it += " AND ToolType.attribute_value = '%s'" % filters.get(
            "tt")
    else:
        if "System Manager" not in user_roles:
            frappe.throw("Please select Tool Type to Proceed")

    if filters.get("item"):
        conditions_it += " and it.name = '%s'" % filters.get("item")

    if filters.get("is_pl"):
        conditions_it += f" AND it.pl_item = '{filters.get('is_pl')}'"

    if filters.get("template"):
        conditions_it += f" AND it.variant_of = {filters.get('template')}"

    return conditions_it, conditions_pl, cond_pr
