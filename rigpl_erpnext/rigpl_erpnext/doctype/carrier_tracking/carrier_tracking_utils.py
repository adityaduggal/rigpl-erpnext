# Copyright (c) 2026, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.desk.reportview import get_match_cond


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def company_address_query(doctype, txt, searchfield, start, page_len, filters):
    """
    Fetch addresses where is_your_company_address=1 and disabled=0.
    Uses direct SQL to bypass field-level permlevel checks on is_your_company_address.
    """
    searchfields = frappe.get_meta("Address").get_search_fields()
    if searchfield and searchfield not in searchfields:
        searchfields.append(searchfield)

    search_condition = " or ".join(
        f"`tabAddress`.`{field}` like %(txt)s"
        for field in searchfields
    )
    if not search_condition:
        search_condition = "`tabAddress`.`name` like %(txt)s"

    return frappe.db.sql(
        """SELECT `tabAddress`.name, `tabAddress`.city, `tabAddress`.country
        FROM `tabAddress`
        WHERE
            `tabAddress`.is_your_company_address = 1 AND
            ifnull(`tabAddress`.disabled, 0) = 0 AND
            ({search_condition})
            {mcond}
        ORDER BY
            if(locate(%(_txt)s, `tabAddress`.name), locate(%(_txt)s, `tabAddress`.name), 99999),
            `tabAddress`.idx desc, `tabAddress`.name
        LIMIT %(start)s, %(page_len)s""".format(
            search_condition=search_condition,
            mcond=get_match_cond(doctype),
        ),
        {
            "txt": "%" + txt + "%",
            "_txt": txt.replace("%", ""),
            "start": start,
            "page_len": page_len,
        },
    )


@frappe.whitelist()
def get_default_from_address(document, document_name):
    """
    Get the default from_address for a Carrier Tracking based on the linked
    Sales Invoice or Purchase Order's tax template.
    Returns the address name or None.
    """
    if document == "Sales Invoice":
        taxes_and_charges = frappe.db.get_value("Sales Invoice", document_name, "taxes_and_charges")
        if taxes_and_charges:
            return frappe.db.get_value(
                "Sales Taxes and Charges Template", taxes_and_charges, "from_address"
            )
    elif document == "Purchase Order":
        taxes_and_charges = frappe.db.get_value("Purchase Order", document_name, "taxes_and_charges")
        if taxes_and_charges:
            return frappe.db.get_value(
                "Purchase Taxes and Charges Template", taxes_and_charges, "from_address"
            )
    return None
