"""
ERPNext's guest API for the price and stock of one item, with the stock capped (#127).
`hooks.py` `override_whitelisted_methods` sends
`erpnext.e_commerce.shopping_cart.product_info.get_product_info_for_website` here.
"""
import frappe

from rigpl_erpnext.website_rigpl.catalog import cap_product_info
from rigpl_erpnext.website_rigpl.compat import get_ecommerce

erpnext_get_product_info_for_website = get_ecommerce("get_product_info_for_website")


@frappe.whitelist(allow_guest=True)
def get_product_info_for_website(item_code, skip_quotation_creation=False):
    """ERPNext's result, with `product_info.stock_qty` as the capped label."""
    result = erpnext_get_product_info_for_website(item_code, skip_quotation_creation)
    return frappe._dict(result, product_info=cap_product_info(result.get("product_info") or {}))
