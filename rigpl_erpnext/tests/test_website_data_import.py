import io
import json
import os
from contextlib import redirect_stdout
from unittest.mock import patch

import frappe
from frappe.modules.patch_handler import update_patch_log
from frappe.tests.utils import FrappeTestCase
from frappe.website.doctype.website_theme.website_theme import WebsiteTheme

from rigpl_erpnext.website_rigpl.website_data import importer

TEMPLATE_DIR = os.path.join(os.path.dirname(importer.__file__), "..", "web_template")
TEST_SEED = dict(importer.load_json("home"), name="_test-rigpl-home", route="test-rigpl-home")
DONE_PATCHES = [importer.IMPORT_PATCH, importer.SKIP_PATCH]
# Every hex value in version-12 public/scss/variables.scss and index.scss
V12_COLORS = {"#8BBF46", "#191B69", "#18427B", "#E2DBD4", "#7F8487", "#F7FAFC", "#D1D8DD", "#CED5DB", "#333333", "#FFFFFF"}


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


TEST_THEME_SEED = make_test_theme_seed()


def load_test_seed(name):
    return TEST_THEME_SEED if name == "theme" else TEST_SEED


def render_web_template(scrubbed_name, values):
    with open(os.path.join(TEMPLATE_DIR, scrubbed_name, scrubbed_name + ".html")) as f:
        return frappe.render_template(f.read(), dict(values, values=values))


def block_values(block):
    return json.loads(block.web_template_values)


class TestWebsiteDataImport(FrappeTestCase):
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

    def test_theme_seed_has_every_v12_color(self):
        colors = set(importer.load_json("theme")["colors"].values())
        self.assertEqual(colors, V12_COLORS)

    def test_set_default_theme_replaces_empty_or_standard(self):
        for current in ("", "Standard"):
            frappe.db.set_single_value("Website Settings", "website_theme", current)
            self.assertTrue(importer.set_default_theme("_test-rigpl-v12"))
            self.assertEqual(frappe.db.get_single_value("Website Settings", "website_theme"), "_test-rigpl-v12")

    def test_set_default_theme_keeps_a_chosen_theme(self):
        frappe.db.set_single_value("Website Settings", "website_theme", "Custom")
        self.assertFalse(importer.set_default_theme("_test-rigpl-v12"))
        self.assertEqual(frappe.db.get_single_value("Website Settings", "website_theme"), "Custom")


class TestImportWebsiteOnce(FrappeTestCase):
    def setUp(self):
        frappe.db.delete("Patch Log", {"patch": ["in", DONE_PATCHES]})

    def tearDown(self):
        frappe.db.rollback()

    @patch.object(WebsiteTheme, "generate_bootstrap_theme")
    @patch.object(importer, "can_compile_scss", return_value=True)
    @patch.object(importer, "load_json", side_effect=load_test_seed)
    def test_first_run_imports_and_writes_patch_log(self, _seed, _can_compile, _compile):
        importer.import_website_once()

        self.assertTrue(frappe.db.exists("Website Theme", "_test-rigpl-v12"))
        self.assertTrue(frappe.db.exists("Web Page", TEST_SEED["name"]))
        self.assertTrue(frappe.db.exists("Patch Log", {"patch": importer.IMPORT_PATCH}))

    @patch.object(importer, "can_compile_scss", return_value=True)
    def test_second_run_does_not_import(self, _can_compile):
        with patch.object(importer, "import_website"):
            importer.import_website_once()
        with patch.object(importer, "import_website") as import_website:
            importer.import_website_once()
        import_website.assert_not_called()
        self.assertEqual(frappe.db.count("Patch Log", {"patch": importer.IMPORT_PATCH}), 1)

    @patch.object(importer, "can_compile_scss", return_value=True)
    def test_skip_patch_row_stops_the_import(self, _can_compile):
        update_patch_log(importer.SKIP_PATCH)
        with patch.object(importer, "import_website") as import_website:
            importer.import_website_once()
        import_website.assert_not_called()

    @patch.object(importer, "can_compile_scss", return_value=False)
    def test_no_scss_compile_skips_the_import_and_tells_the_user(self, _can_compile):
        output = io.StringIO()
        with patch.object(importer, "import_website") as import_website, redirect_stdout(output):
            importer.import_website_once()

        import_website.assert_not_called()
        self.assertFalse(frappe.db.exists("Patch Log", {"patch": importer.IMPORT_PATCH}))
        self.assertIn("Node 14", output.getvalue())

    @patch.object(WebsiteTheme, "generate_bootstrap_theme")
    @patch.object(importer, "can_compile_scss", return_value=True)
    @patch.object(importer, "load_json", side_effect=load_test_seed)
    def test_failed_import_undoes_changes_and_does_not_raise(self, _seed, _can_compile, _compile):
        error_logs = frappe.db.count("Error Log", {"method": importer.IMPORT_ERROR_TITLE})
        output = io.StringIO()
        with patch.object(importer, "import_home_page", side_effect=frappe.ValidationError("broken")):
            with redirect_stdout(output):
                importer.import_website_once()

        self.assertFalse(frappe.db.exists("Website Theme", "_test-rigpl-v12"))
        self.assertFalse(frappe.db.exists("Patch Log", {"patch": importer.IMPORT_PATCH}))
        self.assertEqual(frappe.db.count("Error Log", {"method": importer.IMPORT_ERROR_TITLE}), error_logs + 1)
        self.assertIn("not imported", output.getvalue())
