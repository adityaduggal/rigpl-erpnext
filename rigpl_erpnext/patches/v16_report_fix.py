# -*- coding: utf-8 -*-
# Copyright (c) 2026, Rohit Industries Ltd.
# Monkey patch for v16 report filter validation issues

import frappe
from frappe import _
import json


def patched_validate_filters_permissions(report_name, filters=None, user=None, js_filters=None):
    """
    V15-style validation - only validates filters from report.json, ignores js_filters.
    This is a workaround for v16's broken filter validation that doesn't respect ignore_link_validation.
    """
    if not filters:
        return

    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except (json.JSONDecodeError, TypeError):
            return

    report = frappe.get_doc("Report", report_name)
    
    # ONLY validate filters from report.json (like v15 did)
    # Skip js_filters validation entirely
    for field in report.filters:
        if field.fieldname in filters and field.fieldtype == "Link":
            linked_doctype = field.options
            from frappe.permissions import has_permission
            
            if not has_permission(
                doctype=linked_doctype, 
                ptype="read", 
                doc=filters[field.fieldname], 
                user=user
            ) and not has_permission(
                doctype=linked_doctype, 
                ptype="select", 
                doc=filters[field.fieldname], 
                user=user
            ):
                frappe.throw(
                    _("You do not have permission to access {0}: {1}.").format(
                        linked_doctype, filters[field.fieldname]
                    )
                )


def apply_report_patches():
    """Apply monkey patches for v16 report issues"""
    import frappe.desk.query_report
    frappe.desk.query_report.validate_filters_permissions = patched_validate_filters_permissions

