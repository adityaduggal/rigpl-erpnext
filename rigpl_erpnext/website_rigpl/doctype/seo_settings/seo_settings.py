# Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt
import re

import frappe
from frappe.model.document import Document
from frappe.utils import escape_html

from rigpl_erpnext.website_rigpl.seo import locations, meta
from rigpl_erpnext.website_rigpl.website_data.seo.importer import create_missing_records

# SEO Settings owns only the lines between the markers of robots.txt
ROBOTS_BEGIN = "# BEGIN RIGPL SEO"
ROBOTS_END = "# END RIGPL SEO"
ROBOTS_SECTION = re.compile(
    r"\n*^{}$.*?^{}$\n?".format(ROBOTS_BEGIN, ROBOTS_END), re.MULTILINE | re.DOTALL
)
USER_AGENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._/-]*$")


class SEOSettings(Document):
    def validate(self):
        meta.check_templates(
            self, ("site_name", "title_template", "description_template", "llms_body")
        )
        self.check_addresses()
        for agent in get_crawlers(self.get("denied_ai_crawlers")):
            if not USER_AGENT.match(agent):
                frappe.throw(
                    "Denied AI Crawlers: {} is not a user agent name".format(escape_html(agent)),
                    frappe.ValidationError,
                )

    def check_addresses(self):
        names = [row.address for row in self.get("addresses") or []]
        if not names:
            return
        filters = {"name": ["in", names], "is_your_company_address": 1, "disabled": 0}
        valid = set(frappe.get_all("Address", filters=filters, pluck="name"))
        wrong = [name for name in names if name not in valid]
        if wrong:
            frappe.throw(
                "Not an enabled company address: {}".format(escape_html(", ".join(wrong))),
                frappe.ValidationError,
            )
        locations.warn_missing_coordinates(names)

    def on_update(self):
        write_robots(get_crawlers(self.get("denied_ai_crawlers")))
        meta.clear_caches()


def get_crawlers(text: str) -> list:
    return list(dict.fromkeys(line.strip() for line in (text or "").splitlines() if line.strip()))


def make_robots(text: str, crawlers: list) -> str:
    """`text` with the section of the denied crawlers. The other lines stay as they are."""
    # a Code or Text field can have Windows line ends
    kept = ROBOTS_SECTION.sub("\n", (text or "").replace("\r\n", "\n")).rstrip("\n")
    if not crawlers:
        return kept
    rules = "\n\n".join("User-agent: {}\nDisallow: /".format(agent) for agent in crawlers)
    section = "\n".join((ROBOTS_BEGIN, rules, ROBOTS_END))
    return "{}\n\n{}\n".format(kept, section) if kept else section + "\n"


def write_robots(crawlers: list) -> None:
    old = frappe.db.get_single_value("Website Settings", "robots_txt") or ""
    if not crawlers and ROBOTS_BEGIN not in old:
        return
    new = make_robots(old, crawlers)
    if new != old:
        frappe.db.set_value("Website Settings", None, "robots_txt", new)
        frappe.clear_document_cache("Website Settings", "Website Settings")


@frappe.whitelist()
def create_records() -> list:
    """Creates the default Schema Templates and SEO Rules that do not exist."""
    if not frappe.has_permission("SEO Settings", "write"):
        frappe.throw("No permission to write SEO Settings", frappe.PermissionError)
    return create_missing_records()
