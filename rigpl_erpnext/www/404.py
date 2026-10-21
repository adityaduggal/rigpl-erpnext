"""
The 404 page. An old website URL gets a 301 to its current page (#84). Other paths show
the Frappe 404 page.
"""
import frappe

from rigpl_erpnext.website_rigpl.legacy_routes import get_legacy_target

no_cache = 1


def get_context(context):
    request = getattr(frappe.local, "request", None)
    target = get_legacy_target(request.path) if request else None
    if target:
        frappe.flags.redirect_location = "/" + target
        raise frappe.Redirect
