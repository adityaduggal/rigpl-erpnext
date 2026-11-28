"""
The company data of `site.organization` (#262, #263). Each key is always present, so an
expression does not fail on a site that has no value.
"""
from __future__ import annotations

from typing import List, Optional
from urllib.parse import urlsplit

import frappe
from frappe.utils import cint

from .sandbox import abs_url

SCHEMA = "https://schema.org/"
DEFAULT_SOCIAL_GROUP = "Social"
# a message link is not a profile of the company
MESSAGE_HOSTS = ("api.whatsapp.com", "wa.me")


def get_organization() -> dict:
    settings = frappe.get_cached_doc("SEO Settings", "SEO Settings")
    website = frappe.get_cached_doc("Website Settings", "Website Settings")
    name = settings.get("company") or frappe.db.get_single_value("Global Defaults", "default_company")
    company = frappe.get_cached_doc("Company", name) if name else frappe._dict()
    established = company.get("date_of_establishment")
    postal = get_address(settings.get("address") or find_company_address(name))
    country = postal.get("country_code") or get_country_code(company.get("country"))
    return {
        "return_policy": get_return_policy(settings, country),
        "brand": website.title_prefix or company.get("company_name") or "",
        "legal_name": company.get("company_name") or "",
        "email": company.get("email") or "",
        "telephone": company.get("phone_no") or "",
        "founding_date": str(established) if established else "",
        "logo": get_public_url(website.banner_image),
        "same_as": get_social_links(website, settings.get("social_group") or DEFAULT_SOCIAL_GROUP),
        "address": postal,
    }


def get_return_policy(settings, country: str) -> dict:
    """An empty dict if SEO Settings has no complete return policy."""
    category = settings.get("return_policy")
    finite = category == "MerchantReturnFiniteReturnWindow"
    days = cint(settings.get("return_days"))
    if not category or not country or (finite and not days):
        return {}
    fees, method = settings.get("return_fees"), settings.get("return_method")
    return {
        "category": SCHEMA + category,
        "country": country,
        "days": days if finite else "",
        "fees": SCHEMA + fees if fees else "",
        "method": SCHEMA + method if method else "",
    }


def get_country_code(country: Optional[str]) -> str:
    code = frappe.db.get_value("Country", country, "code", cache=True) if country else ""
    return (code or "").upper()


def find_company_address(company: Optional[str]) -> Optional[str]:
    if not company:
        return None
    filters = [
        ["Dynamic Link", "link_doctype", "=", "Company"],
        ["Dynamic Link", "link_name", "=", company],
        ["Address", "is_your_company_address", "=", 1],
        ["Address", "disabled", "=", 0],
    ]
    order_by = "`tabAddress`.is_primary_address desc, `tabAddress`.name asc"
    names = frappe.get_all("Address", filters=filters, order_by=order_by, limit=1, pluck="name")
    return names[0] if names else None


def get_address(name: Optional[str]) -> dict:
    """An empty dict if there is no address."""
    if not name:
        return {}
    address = frappe.get_cached_doc("Address", name)
    lines = (address.address_line1, address.address_line2)
    return {
        "street": ", ".join(line.strip() for line in lines if line and line.strip()),
        "city": address.city or "",
        "state": address.state or "",
        "pincode": address.pincode or "",
        "country_code": get_country_code(address.country),
    }


def get_social_links(website, group: str) -> List[str]:
    urls = [(row.url or "").strip() for row in website.footer_items if row.parent_label == group]
    return [
        url.replace(" ", "%20")
        for url in urls
        if url.startswith(("http://", "https://")) and urlsplit(url).netloc not in MESSAGE_HOSTS
    ]


def get_public_url(path: Optional[str]) -> str:
    # visitors cannot load a private file
    return "" if not path or path.startswith("/private/") else abs_url(path)
