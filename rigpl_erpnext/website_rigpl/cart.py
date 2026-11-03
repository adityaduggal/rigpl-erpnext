"""
ERPNext's place order, with the capped stock in the "Only ... in Stock" message (#127).
`hooks.py` `override_whitelisted_methods` sends
`erpnext.e_commerce.shopping_cart.cart.place_order` here.
"""
import frappe
from frappe import _
from frappe.utils import cint, flt

from rigpl_erpnext.website_rigpl.catalog import cap_stock, get_stock_cap_settings
from rigpl_erpnext.website_rigpl.compat import get_ecommerce

get_shopping_cart_settings = get_ecommerce("get_shopping_cart_settings")
_get_cart_quotation = get_ecommerce("get_cart_quotation")
erpnext_place_order = get_ecommerce("place_order")
get_web_item_qty_in_stock = get_ecommerce("get_web_item_qty_in_stock")


@frappe.whitelist()
def place_order():
    """Check the stock first, then place the order with ERPNext's code."""
    check_cart_stock(_get_cart_quotation())
    return erpnext_place_order()


def check_cart_stock(quotation) -> None:
    """ERPNext place_order's check of the ordered qty against the website stock (cart.py), run
    before it. ERPNext's message shows the real stock; this one shows the capped label.
    ERPNext's own "Not in Stock" check stays as it is, because it shows no quantity.
    """
    if cint(get_shopping_cart_settings().allow_items_not_in_stock):
        return

    cap, cap_label, zero_label = get_stock_cap_settings()
    for item in quotation.get("items"):
        if not frappe.db.get_value("Item", item.item_code, "is_stock_item"):
            continue
        stock = get_web_item_qty_in_stock(item.item_code, "website_warehouse")
        if not cint(stock.in_stock):
            continue
        stock_qty = flt(stock.stock_qty[0][0])
        if flt(item.qty) > stock_qty:
            frappe.throw(
                _("Only {0} in Stock for item {1}").format(
                    cap_stock(stock_qty, cap, cap_label, zero_label), item.item_code
                )
            )
