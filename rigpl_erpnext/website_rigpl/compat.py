"""
The ERPNext e-commerce functions that the website uses, found where the installed version
keeps them (#82). ERPNext v13 and v14 have them in `erpnext.e_commerce` and
`erpnext.utilities.product`. From v15 they are in the `webshop` app.

The webshop paths are not tested yet: check them at the v15 upgrade
(`patches/v13/NOTES_v14_upgrade.md`).
"""
import importlib
from typing import Callable, Dict, List, Tuple

ERPNEXT = "erpnext.e_commerce"
WEBSHOP = "webshop.webshop"

ECOMMERCE: Dict[str, List[Tuple[str, str]]] = {
    "get_shopping_cart_settings": [
        (f"{ERPNEXT}.doctype.e_commerce_settings.e_commerce_settings", "get_shopping_cart_settings"),
        (f"{WEBSHOP}.doctype.webshop_settings.webshop_settings", "get_shopping_cart_settings"),
    ],
    "get_cart_quotation": [
        (f"{ERPNEXT}.shopping_cart.cart", "_get_cart_quotation"),
        (f"{WEBSHOP}.shopping_cart.cart", "_get_cart_quotation"),
    ],
    "place_order": [
        (f"{ERPNEXT}.shopping_cart.cart", "place_order"),
        (f"{WEBSHOP}.shopping_cart.cart", "place_order"),
    ],
    "get_product_info_for_website": [
        (f"{ERPNEXT}.shopping_cart.product_info", "get_product_info_for_website"),
        (f"{WEBSHOP}.shopping_cart.product_info", "get_product_info_for_website"),
    ],
    "get_product_filter_data": [
        (f"{ERPNEXT}.api", "get_product_filter_data"),
        (f"{WEBSHOP}.api", "get_product_filter_data"),
    ],
    "make_website_item": [
        (f"{ERPNEXT}.doctype.website_item.website_item", "make_website_item"),
        (f"{WEBSHOP}.doctype.website_item.website_item", "make_website_item"),
    ],
    "get_web_item_qty_in_stock": [
        ("erpnext.utilities.product", "get_web_item_qty_in_stock"),
        (f"{WEBSHOP}.utils.product", "get_web_item_qty_in_stock"),
    ],
    "adjust_qty_for_expired_items": [
        ("erpnext.utilities.product", "adjust_qty_for_expired_items"),
        (f"{WEBSHOP}.utils.product", "adjust_qty_for_expired_items"),
    ],
}


def get_ecommerce(name: str) -> Callable:
    """The function `name` from the first module in `ECOMMERCE[name]` that imports.
    It imports at call time, so a test that patches the ERPNext function is seen.
    Only a missing module moves on to the next path. Any other error in the module is raised."""
    tried = []
    for module_path, attr in ECOMMERCE[name]:
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError as e:
            if not e.name or not module_path.startswith(e.name):
                raise
            tried.append(module_path)
            continue
        return getattr(module, attr)
    raise ImportError(f"{name}: no e-commerce module found. Tried: {', '.join(tried)}")
