"""
`/llms.txt` (#271): the text of SEO Settings > llms.txt Body, for AI assistants. A site with
the setting off shows the 404 page.
"""
import frappe

from rigpl_erpnext.website_rigpl.seo.builder import BuildError, log_errors
from rigpl_erpnext.website_rigpl.seo.context import build_variables, get_listing_variables
from rigpl_erpnext.website_rigpl.seo.sandbox import render_text

# a saved setting or a new post must show at once
no_cache = 1


def get_context(context):
    settings = frappe.get_cached_doc("SEO Settings", "SEO Settings")
    if not settings.get("llms_enabled"):
        raise frappe.PageDoesNotExistError
    variables = dict(build_variables({"path": "llms.txt"}), **get_listing_variables())
    try:
        text = render_text(settings.get("llms_body"), variables)
    except Exception as e:
        message = "{}: {}".format(type(e).__name__, e)
        log_errors([BuildError("SEO Settings", "llms_body", message)], "llms.txt")
        raise frappe.PageDoesNotExistError
    return {"llms_txt": text}
