"""
One-time import of the v12 website into v13 DB documents, so website managers can
edit it in Desk: the v12 theme (app SCSS) becomes Website Theme "rigpl-v12", and the
v12 home page (app-code www/index.html) becomes Page Builder blocks in Web Page "home".

Run it with the manual patch rigpl_erpnext.patches.manual.import_website_data.
Data that the v12 DB already has (Homepage, Homepage Section, Contact Us Settings)
is read from the site at import time. home.json holds only the values that were
hard-coded in the v12 code. See website_rigpl/README.md.
"""
from __future__ import annotations

import json
import os

import frappe
from frappe.website.render import clear_cache
from frappe.website.router import resolve_route

IMPORT_PATCH = "rigpl_erpnext.patches.manual.import_website_data"
SKIP_PATCH = "rigpl_erpnext.patches.manual.skip_website_data_import"

ITEM_CARDS_PER_BLOCK = 12  # card slots in the "Item Card Group" web template
REQUIRED_TEMPLATES = (
    "Slideshow",
    "Item Card Group",
    "RIGPL Latest Blogs",
    "RIGPL Homepage Section",
    "RIGPL Social Feeds",
    "RIGPL Contact Strip",
)


def load_json(name: str) -> dict:
    return json.loads(read_data_file(f"{name}.json"))


def read_data_file(file_name: str) -> str:
    with open(os.path.join(os.path.dirname(__file__), file_name)) as f:
        return f.read()


def import_theme(seed: dict | None = None) -> bool:
    """Create the v12 colors and Website Theme. Returns False when the theme already exists."""
    seed = seed or load_json("theme")
    for name, color in seed["colors"].items():
        if frappe.db.exists("Color", name):
            print(f"Color {name} already exists. It was not changed.")
        else:
            frappe.get_doc({"doctype": "Color", "name": name, "color": color}).insert()

    theme_name = seed["theme"]["theme"]
    if frappe.db.exists("Website Theme", theme_name):
        print(f"Website Theme {theme_name} already exists. It was not changed.")
        return False

    theme = frappe.get_doc({"doctype": "Website Theme", **seed["theme"]})
    theme.custom_scss = read_data_file(seed["custom_scss_file"])
    theme.insert()  # validate() compiles the SCSS and throws on an error
    print(f"Website Theme {theme.name} was imported. CSS: {theme.theme_url}")
    return True


def set_default_theme(theme_name: str) -> bool:
    """Make `theme_name` the website theme, but only when no real theme is set yet."""
    current = frappe.db.get_single_value("Website Settings", "website_theme")
    if current and current != "Standard":
        print(f"Website Settings theme {current} is kept. It was not changed to {theme_name}.")
        return False

    frappe.db.set_single_value("Website Settings", "website_theme", theme_name)
    clear_cache()
    print(f"Website Settings theme changed from {current!r} to {theme_name!r}.")
    return True


def import_home_page(seed: dict | None = None) -> bool:
    """Create or fill the home Web Page. Returns False when the page already has content."""
    seed = seed or load_json("home")
    if frappe.db.exists("Web Page", seed["name"]):
        page = frappe.get_doc("Web Page", seed["name"])
        if page.page_blocks or page.main_section or page.main_section_md or page.main_section_html:
            print(f"Web Page {page.name} already has content. It was not changed.")
            return False
    else:
        page = frappe.new_doc("Web Page")
        page.name = seed["name"]

    missing = [name for name in REQUIRED_TEMPLATES if not frappe.db.exists("Web Template", name)]
    if missing:
        frappe.throw(
            "Web Templates not found: {}. Run bench migrate first.".format(", ".join(missing)),
            title="Web Template Not Found",
        )

    homepage = frappe.get_single("Homepage")
    page.update(
        {
            "title": homepage.title or homepage.company,
            "meta_title": homepage.title,
            "meta_description": homepage.description,
            "route": seed["route"],
            "content_type": "Page Builder",
            "published": 1,
            "full_width": 1,
            "show_title": 0,
        }
    )
    page.set("page_blocks", build_home_blocks(seed, homepage))
    page.save()
    print(f"Web Page {page.name} was imported with {len(page.page_blocks)} blocks at /{page.route}.")
    return True


def build_home_blocks(seed: dict, homepage) -> list[dict]:
    """The blocks in the same order as the sections of the v12 index page."""
    return [
        *slideshow_blocks(homepage.slideshow),
        *product_blocks(seed["products"]["title"], [row.item_code for row in homepage.products]),
        make_block("RIGPL Latest Blogs", seed["blogs"]),
        *homepage_section_blocks(),
        make_block("RIGPL Social Feeds", seed["social"]),
        contact_block(seed["contact"]),
    ]


def slideshow_blocks(slideshow: str | None) -> list[dict]:
    if not slideshow:
        return []
    if not frappe.db.exists("Website Slideshow", slideshow):
        frappe.throw(f"Website Slideshow {slideshow} (set in Homepage) does not exist.")
    return [make_block("Slideshow", {"website_slideshow": slideshow}, add_container=0)]


def product_blocks(title: str, website_items: list[str]) -> list[dict]:
    """Item Card Group blocks, 12 cards each. Homepage product rows hold Website Item names in v13."""
    missing = [name for name in website_items if not frappe.db.exists("Website Item", name)]
    if missing:
        frappe.throw(
            "These Homepage products have no Website Item: {}".format(", ".join(missing)),
            title="Homepage Product Not Found",
        )

    blocks = []
    for start in range(0, len(website_items), ITEM_CARDS_PER_BLOCK):
        chunk = website_items[start : start + ITEM_CARDS_PER_BLOCK]
        values = {f"card_{i}_item": name for i, name in enumerate(chunk, start=1)}
        if not blocks:
            values["title"] = title
        blocks.append(make_block("Item Card Group", values))
    return blocks


def homepage_section_blocks() -> list[dict]:
    sections = frappe.get_all("Homepage Section", order_by="section_order asc", pluck="name")
    return [make_block("RIGPL Homepage Section", {"homepage_section": name}) for name in sections]


def contact_block(contact: dict) -> dict:
    values = {
        **contact,
        "email": frappe.db.get_single_value("Contact Us Settings", "email_id"),
        "phone": frappe.db.get_single_value("Contact Us Settings", "phone"),
    }
    return make_block("RIGPL Contact Strip", values, add_shade=1)


def make_block(web_template: str, values: dict, add_container: int = 1, add_shade: int = 0) -> dict:
    return {
        "web_template": web_template,
        "web_template_values": json.dumps(values, indent=1),
        "add_container": add_container,
        "add_shade": add_shade,
        "add_top_padding": 1,
        "add_bottom_padding": 1,
    }


def set_home_page(route: str) -> bool:
    """Point Website Settings.home_page to `route`, but only when the current value is broken."""
    current = frappe.db.get_single_value("Website Settings", "home_page")
    if current and resolve_route(current.strip("/")):
        print(f"Website Settings home page /{current} works. It was not changed.")
        return False

    frappe.db.set_single_value("Website Settings", "home_page", route)
    frappe.cache().delete_key("home_page")
    clear_cache()
    print(f"Website Settings home page changed from {current!r} to {route!r}.")
    return True


def clear_cache_on_blog_change(doc, method=None):
    """Blog Post doc_event: the RIGPL Latest Blogs block on cached pages must show the change."""
    clear_cache()


def notify_pending_website_import():
    """after_migrate: remind the admin until one of the manual website patches was run."""
    if frappe.db.exists("Patch Log", {"patch": ["in", [IMPORT_PATCH, SKIP_PATCH]]}):
        return

    site = frappe.local.site
    print(
        "\nrigpl_erpnext: the v12 website (theme and home page) is not imported.\n"
        f"  To import it:  bench --site {site} run-patch {IMPORT_PATCH}\n"
        f"  To skip it and hide this message:  bench --site {site} run-patch {SKIP_PATCH}\n"
        "  Read rigpl_erpnext/website_rigpl/README.md first.\n"
    )
