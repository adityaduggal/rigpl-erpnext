"""
ERPNext's guest API for the products and sub-categories of a category page, with the
sub-categories in sales order (#103). `hooks.py` `override_whitelisted_methods` sends
`erpnext.e_commerce.api.get_product_filter_data` here. ERPNext orders them by name.
"""
from __future__ import annotations

from typing import Dict, List

import frappe
from erpnext.e_commerce.api import get_product_filter_data as erpnext_get_product_filter_data


@frappe.whitelist(allow_guest=True)
def get_product_filter_data(query_args=None):
    """ERPNext's result, with `sub_categories` ordered by Item Group `weightage`."""
    result = erpnext_get_product_filter_data(query_args)
    sub_categories = result.get("sub_categories") if isinstance(result, dict) else None
    if not sub_categories:
        return result

    weightages = dict(
        frappe.get_all(
            "Item Group",
            filters={"name": ("in", [group.name for group in sub_categories])},
            fields=["name", "weightage"],
            as_list=True,
        )
    )
    return dict(result, sub_categories=sort_sub_categories(sub_categories, weightages))


def sort_sub_categories(sub_categories: List[dict], weightages: Dict[str, int]) -> List[dict]:
    """Highest Item Group `weightage` first (the sales rank job sets it, #101), then by name."""
    return sorted(sub_categories, key=lambda group: (-(weightages.get(group["name"]) or 0), group["name"]))
