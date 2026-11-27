# Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt
"""The 2 new RM limits of RIGPL Settings (#257). A new single field has no value until it is set."""

import frappe
from frappe.utils import flt

DEFAULTS = {"rm_max_qty_difference_percent": 20, "rm_max_difference_value": 25000}


def execute():
    frappe.reload_doc("rigpl_erpnext", "doctype", "rigpl_settings")
    for field, value in DEFAULTS.items():
        if not flt(frappe.db.get_single_value("RIGPL Settings", field)):
            frappe.db.set_value("RIGPL Settings", "RIGPL Settings", field, value)
