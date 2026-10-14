import json
import os
import unittest
from unittest.mock import patch

import frappe
from frappe.website.doctype.website_theme.website_theme import WebsiteTheme

from rigpl_erpnext.website_rigpl.website_data import importer

TEMPLATE_DIR = os.path.join(os.path.dirname(importer.__file__), "..", "web_template")
TEST_SEED = dict(importer.load_json("home"), name="_test-rigpl-home", route="_test-rigpl-home")


def make_test_theme_seed():
    """The real theme seed with test names, so the test never touches the real records."""
    seed = importer.load_json("theme")
    seed["colors"] = {"_test-" + name: color for name, color in seed["colors"].items()}
    seed["theme"] = dict(
        seed["theme"],
        theme="_test-rigpl-v12",
        primary_color="_test-" + seed["theme"]["primary_color"],
        dark_color="_test-" + seed["theme"]["dark_color"],
    )
    return seed


def render_web_template(scrubbed_name, values):
    with open(os.path.join(TEMPLATE_DIR, scrubbed_name, scrubbed_name + ".html")) as f:
        return frappe.render_template(f.read(), dict(values, values=values))


def block_values(block):
    return json.loads(block.web_template_values)


class TestWebsiteDataImport(unittest.TestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_products_are_split_into_blocks_of_twelve(self):
        items = [f"WEB-ITM-{i:04d}" for i in range(29)]
        with patch.object(frappe.db, "exists", return_value=True):
            blocks = importer.product_blocks("Products", items)

        cards = [[k for k in json.loads(b["web_template_values"]) if k.endswith("_item")] for b in blocks]
        self.assertEqual([len(c) for c in cards], [12, 12, 5])
        self.assertEqual(json.loads(blocks[0]["web_template_values"])["title"], "Products")
        self.assertNotIn("title", json.loads(blocks[1]["web_template_values"]))

    def test_missing_website_item_raises(self):
        with self.assertRaises(frappe.ValidationError):
            importer.product_blocks("Products", ["_Test Missing Website Item"])

    def test_missing_slideshow_raises(self):
        with self.assertRaises(frappe.ValidationError):
            importer.slideshow_blocks("_Test Missing Slideshow")

    def test_import_creates_published_page_once(self):
        self.assertTrue(importer.import_home_page(TEST_SEED))

        page = frappe.get_doc("Web Page", TEST_SEED["name"])
        self.assertEqual(page.published, 1)
        self.assertEqual(page.content_type, "Page Builder")
        templates = [b.web_template for b in page.page_blocks]
        sections = frappe.db.count("Homepage Section")
        self.assertEqual(templates.count("RIGPL Homepage Section"), sections)
        self.assertEqual(templates[-2:], ["RIGPL Social Feeds", "RIGPL Contact Strip"])
        self.assertEqual(block_values(page.page_blocks[-2])["twitter_handle"], "rigpl1")

        modified = page.modified
        self.assertFalse(importer.import_home_page(TEST_SEED))
        self.assertEqual(frappe.db.get_value("Web Page", page.name, "modified"), modified)

    def test_set_home_page_keeps_a_working_value(self):
        with patch.object(importer, "resolve_route", return_value={"page": 1}):
            frappe.db.set_single_value("Website Settings", "home_page", "about")
            self.assertFalse(importer.set_home_page("_test-rigpl-home"))
        self.assertEqual(frappe.db.get_single_value("Website Settings", "home_page"), "about")

    def test_set_home_page_replaces_a_broken_value(self):
        with patch.object(importer, "resolve_route", return_value=None):
            frappe.db.set_single_value("Website Settings", "home_page", "index")
            self.assertTrue(importer.set_home_page("_test-rigpl-home"))
        self.assertEqual(frappe.db.get_single_value("Website Settings", "home_page"), "_test-rigpl-home")

    def test_social_feeds_escape_values(self):
        html = render_web_template("rigpl_social_feeds", {"twitter_handle": '"><script>x</script>'})
        self.assertNotIn("<script>x</script>", html)
        self.assertIn("&#34;&gt;&lt;script&gt;", html)

    def test_contact_strip_links(self):
        html = render_web_template(
            "rigpl_contact_strip", {"email": "sales@rigpl.com", "phone": "+91-85869 23456"}
        )
        self.assertIn('href="mailto:sales@rigpl.com"', html)
        self.assertIn('href="tel:+91-8586923456"', html)

    @patch.object(WebsiteTheme, "generate_bootstrap_theme")
    def test_import_theme_creates_colors_and_theme_once(self, _compile):
        seed = make_test_theme_seed()
        frappe.get_doc({"doctype": "Color", "name": "_test-rigpl-v12-green", "color": "#000000"}).insert()

        self.assertTrue(importer.import_theme(seed))

        for name in seed["colors"]:
            self.assertTrue(frappe.db.exists("Color", name))
        self.assertEqual(frappe.db.get_value("Color", "_test-rigpl-v12-green", "color"), "#000000")
        theme = frappe.get_doc("Website Theme", "_test-rigpl-v12")
        self.assertEqual(theme.custom, 1)
        self.assertEqual(theme.primary_color, "_test-rigpl-v12-green")
        self.assertIn("border-top: 5px solid $primary", theme.custom_scss)

        self.assertFalse(importer.import_theme(seed))
        self.assertEqual(frappe.db.get_value("Website Theme", theme.name, "modified"), theme.modified)

    def test_set_default_theme_replaces_empty_or_standard(self):
        for current in ("", "Standard"):
            frappe.db.set_single_value("Website Settings", "website_theme", current)
            self.assertTrue(importer.set_default_theme("_test-rigpl-v12"))
            self.assertEqual(frappe.db.get_single_value("Website Settings", "website_theme"), "_test-rigpl-v12")

    def test_set_default_theme_keeps_a_chosen_theme(self):
        frappe.db.set_single_value("Website Settings", "website_theme", "Custom")
        self.assertFalse(importer.set_default_theme("_test-rigpl-v12"))
        self.assertEqual(frappe.db.get_single_value("Website Settings", "website_theme"), "Custom")
