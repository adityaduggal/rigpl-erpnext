# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import date, datetime

from frappe.utils import getdate
from rohit_common.utils.rohit_common_utils import fn_check_digit, fn_next_string

from rigpl_erpnext.utils.item_utils import *

from ...utils.lead_time_utils import get_item_lead_time
from ...utils.stock_utils import get_max_lead_times


def validate(doc, method):
    if doc.variant_of:
        template = frappe.get_doc("Item", doc.variant_of)
        if doc.lead_time_days == 0 and not doc.is_new():
            ldt_dict = get_item_lead_time(doc.name)
            if ldt_dict.avg_days_wt == 0:
                lead_time = get_max_lead_times(doc.name)
                if lead_time > 0:
                    doc.lead_time_days = lead_time
            else:
                doc.lead_time_days = ldt_dict.avg_days_wt
        if doc.get("__islocal") == 1:
            check_item_defaults(template, doc)
        else:
            check_and_copy_attributes_to_variant(template, doc, insert_type="frontend")

    validate_variants(doc)
    validate_attribute_numeric(doc)
    validate_reoder(doc)
    web_catalog(doc)
    doc.page_name = doc.item_name
    description, long_desc = generate_description(doc)
    doc.description = description
    # doc.web_long_description = long_desc
    doc.item_name = long_desc
    doc.item_code = doc.name

    if (
        getdate(doc.end_of_life)
        < datetime.datetime.strptime("2099-12-31", "%Y-%m-%d").date()
    ):
        doc.disabled = 1
        doc.pl_item = "No"
        doc.show_variant_in_website = 0
        doc.show_in_website = 0

    if doc.disabled == 1:
        if getdate(doc.end_of_life) > date.today():
            doc.end_of_life = date.today()

        doc.pl_item = "No"
        doc.show_variant_in_website = 0
        doc.show_in_website = 0

    if doc.variant_of is None:
        doc.item_name = doc.name
        doc.item_code = doc.name
        doc.page_name = doc.name
        doc.description = doc.name
    else:
        set_website_specs(doc, method)


def autoname(doc, method):
    if doc.variant_of:
        (serial, code) = generate_item_code(doc, method)
        doc.name = code
        doc.page_name = doc.name
        nxt_serial = fn_next_string(doc, serial[0][0])
        frappe.db.set_value("Item Attribute Value", serial[0][1], "serial", nxt_serial)


def generate_item_code(doc, method):
    if doc.variant_of:
        code = ""
        abbr = []
        for d in doc.attributes:
            is_numeric = frappe.db.get_value(
                "Item Attribute", d.attribute, "numeric_values"
            )
            use_in_item_code = frappe.db.get_value(
                "Item Attribute", d.attribute, "use_in_item_code"
            )
            if is_numeric != 1 and use_in_item_code == 1:
                cond1 = d.attribute
                cond2 = d.attribute_value
                query = """SELECT iav.abbr from `tabItem Attribute Value` iav,
				`tabItem Attribute` ia
				WHERE iav.parent = '%s' AND iav.parent = ia.name
				AND iav.attribute_value = '%s'""" % (
                    cond1,
                    cond2,
                )

                # Get serial from Tool Type (This is HARDCODED)
                # TODO: Put 1 custom field in Item Attribute checkbox "Use for Serial Number"
                # now also add a validation that you cannot use more than 1 attributes which
                # have use for serial no.
                if cond1 == "Tool Type":
                    query2 = (
                        """SELECT iav.serial, iav.name from `tabItem Attribute Value` iav
						WHERE iav.parent = 'Tool Type' AND iav.attribute_value= '%s'"""
                        % cond2
                    )
                    serial = frappe.db.sql(query2, as_list=1)

                abbr.extend(frappe.db.sql(query, as_list=1))
                abbr[len(abbr) - 1].append(d.idx)
        abbr.sort(
            key=lambda x: x[1]
        )  # Sort the abbr as per priority lowest one is taken first

        for i in range(len(abbr)):
            if abbr[i][0] != '""':
                code = code + abbr[i][0]
        if len(serial[0][0]) > 2:
            code = code + serial[0][0]
        else:
            frappe.throw("Serial length is lower than 3 characters")
        chk_digit = fn_check_digit(code)
        code = code + str(chk_digit)
        return serial, code


# Set the Website Specifications automatically from Template, Attribute and Variant Table
# This is done only for Variants which are shown on website
def set_website_specs(doc, method):
    if doc.show_variant_in_website == 1:
        template = frappe.get_doc("Item", doc.variant_of)
        web_spec = []
        for temp_att in template.attributes:
            temp = []
            if temp_att.use_in_description == 1:
                attribute_doc = frappe.get_doc("Item Attribute", temp_att.attribute)
                att_val = frappe.db.sql(
                    """SELECT attribute_value
					FROM `tabItem Variant Attribute`
					WHERE parent = '%s' AND attribute = '%s'"""
                    % (doc.name, temp_att.attribute),
                    as_list=1,
                )
                for att in doc.attributes:
                    if att.attribute == attribute_doc.name:
                        if attribute_doc.numeric_values == 1:
                            temp.insert(0, temp_att.field_name)
                            temp.insert(1, str(att.attribute_value))
                        else:
                            lng_desc = frappe.db.sql(
                                """SELECT long_description FROM `tabItem Attribute Value`
							WHERE parent = '%s' AND attribute_value = '%s'"""
                                % (attribute_doc.name, att.attribute_value),
                                as_list=1,
                            )
                            temp.insert(0, temp_att.field_name)
                            temp.insert(1, lng_desc[0][0][1:-1])
                        web_spec.append(temp)
                        break
        doc.set("website_specifications", [])
        for label, desc in web_spec:
            row = doc.append("website_specifications")
            row.label = label
            row.description = desc
