"""SEO Settings and SEO Rules (#261)."""
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_html_for_route
from frappe.website.render import clear_cache
from jinja2 import UndefinedError
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.website_rigpl import item_page
from rigpl_erpnext.website_rigpl.doctype.seo_rule import seo_rule
from rigpl_erpnext.website_rigpl.seo import builder, context, meta
from rigpl_erpnext.website_rigpl.seo.sandbox import render_text

from .test_seo_schema import PREFIX, graphs_of, make_template, prop

ROUTE = "test-rigpl-seo"
PAGE_TITLE = "_Test RIGPL SEO Page"
SETTINGS_VALUES = ("site_name", "title_template", "description_template", "title_limit", "description_limit")


def make_rule(name, **values):
    fields = dict(doctype="SEO Rule", rule_name=PREFIX + name, enabled=1, route_pattern=ROUTE)
    fields.update(values)
    return frappe.get_doc(fields).insert()


def set_settings(**values):
    settings = frappe.get_doc("SEO Settings", "SEO Settings")
    settings.update(dict.fromkeys(SETTINGS_VALUES))
    settings.update(values)
    settings.save()


def web_context(**values):
    fields = dict(route=ROUTE, path=ROUTE, title=PAGE_TITLE, metatags={"title": PAGE_TITLE})
    fields.update(values)
    return frappe._dict(fields)


def build(page=None):
    page = page or web_context()
    errors = []
    doctype = getattr(page.get("doc"), "doctype", None)
    return meta.build_meta(page, meta.find_rule(doctype, page.route), errors), errors


class SeoTestCase(FrappeTestCase):
    def setUp(self):
        # the rules and settings of the site must not change the results
        frappe.db.sql("update `tabSEO Rule` set enabled = 0")
        set_settings()
        self.clear_caches()

    def tearDown(self):
        frappe.db.rollback()
        self.clear_caches()

    def clear_caches(self):
        frappe.local.document_cache.clear()
        frappe.clear_document_cache("SEO Settings", "SEO Settings")
        builder.clear_template_cache()
        frappe.cache().delete_keys(builder.ERROR_CACHE_KEY)
        meta.clear_caches()


class TestTextTemplates(FrappeTestCase):
    def test_plain_text_is_not_an_expression(self):
        self.assertEqual(render_text("Cutting tools in India", {}), "Cutting tools in India")

    def test_text_template(self):
        variables = {"page": {"title": "Drill"}}
        self.assertEqual(render_text("{{ page.title }} | RIGPL", variables), "Drill | RIGPL")

    def test_unknown_name_raises(self):
        with self.assertRaises(UndefinedError):
            render_text("{{ doc.web_item_nme }}", {"doc": {}})


class TestSaveChecks(SeoTestCase):
    def test_rule_needs_doctype_or_route(self):
        with self.assertRaises(frappe.ValidationError):
            make_rule("Empty", route_pattern=None)

    def test_template_syntax_error_blocks_save(self):
        with self.assertRaises(frappe.ValidationError):
            make_rule("Syntax", title_template="{{ page.title ")

    def test_schema_template_row_must_be_page_type(self):
        template = make_template("Site", [prop("name", "x", "Constant")], applies_to="Site")
        with self.assertRaises(frappe.ValidationError):
            make_rule("Wrong", schema_templates=[{"schema_template": template.name}])

    def test_guest_cannot_read_rule(self):
        self.assertFalse(frappe.has_permission("SEO Rule", "read", user="Guest"))

    def test_long_title_warns_and_saves(self):
        with patch.object(seo_rule.frappe, "msgprint") as msgprint:
            rule = make_rule("Long", title_template="x" * 61)
        self.assertIn("61 characters", msgprint.call_args[0][0])
        self.assertTrue(frappe.db.exists("SEO Rule", rule.name))

    def test_long_description_warns_and_saves(self):
        with patch.object(seo_rule.frappe, "msgprint") as msgprint:
            rule = make_rule("Long", description_template="x" * 161)
        self.assertIn("161 characters", msgprint.call_args[0][0])
        self.assertTrue(frappe.db.exists("SEO Rule", rule.name))


class TestMatch(SeoTestCase):
    def test_priority_wins(self):
        make_rule("A", priority=1)
        high = make_rule("B", priority=5)
        self.assertEqual(meta.find_rule(None, ROUTE).name, high.name)

    def test_doctype_and_route_must_both_match(self):
        make_rule("A", reference_doctype="Web Page", route_pattern="test-rigpl-*")
        self.assertIsNone(meta.find_rule("Blog Post", ROUTE))
        self.assertIsNone(meta.find_rule("Web Page", "other"))
        self.assertTrue(meta.find_rule("Web Page", ROUTE))

    def test_disabled_rule_is_ignored(self):
        make_rule("A", enabled=0)
        self.assertIsNone(meta.find_rule(None, ROUTE))

    def test_rule_lookup_queries(self):
        make_rule("A")
        meta.find_rule(None, ROUTE)
        with assert_max_queries(0, test_case=self):
            meta.find_rule(None, ROUTE)


class TestPrecedence(SeoTestCase):
    def test_rule_beats_settings(self):
        set_settings(title_template="Settings", description_template="Settings text")
        make_rule("A", title_template="Rule")
        values, _ = build()
        self.assertEqual(values["title"], "Rule")
        self.assertEqual(values["metatags"]["description"], "Settings text")

    def test_document_field_beats_rule(self):
        make_rule("A", title_template="Rule")
        values, _ = build(web_context(doc=frappe._dict(meta_title="Own")))
        self.assertEqual((values["title"], values["metatags"]["og:title"]), ("Own", "Own"))

    def test_route_meta_beats_all(self):
        make_rule("A", title_template="Rule", description_template="Rule text")
        frappe.get_doc(
            {
                "doctype": "Website Route Meta",
                "__newname": ROUTE,
                "meta_tags": [{"key": "title", "value": "Route"}, {"key": "description", "value": "Row"}],
            }
        ).insert()
        values, _ = build(web_context(doc=frappe._dict(meta_title="Own")))
        tags = values["metatags"]
        self.assertEqual(values["title"], "Route")
        self.assertEqual((tags["description"], tags["og:description"]), ("Row", "Row"))

    def test_no_values_changes_nothing(self):
        page = web_context(doc=frappe._dict(meta_title="Own"))
        self.assertEqual(build(page)[0], {})

    def test_empty_render_keeps_lower_value(self):
        set_settings(title_template="Settings")
        make_rule("A", title_template="{{ '' }}")
        self.assertEqual(build()[0]["title"], "Settings")

    def test_bad_template_keeps_lower_value_and_collects_error(self):
        set_settings(title_template="Settings")
        rule = make_rule("A", title_template="{{ doc.nope }}")
        values, errors = build()
        self.assertEqual(values["title"], "Settings")
        self.assertEqual([(e.template, e.property) for e in errors], [(rule.name, "title")])

    def test_description_loses_html_and_gets_limit(self):
        make_rule("A", description_template="<p>" + "word " * 60 + "</p>")
        description = build()[0]["metatags"]["description"]
        self.assertNotIn("<", description)
        self.assertLessEqual(len(description), 160)
        self.assertTrue(description.endswith("word"))

    def test_noindex_stays(self):
        make_rule("A", robots_template="index,follow")
        page = web_context(metatags={"robots": "noindex,nofollow"})
        self.assertEqual(build(page)[0], {})

    def test_canonical_is_encoded(self):
        make_rule("A", canonical_template='a"b')
        self.assertTrue(build()[0]["canonical"].endswith("/a%22b"))

    def test_title_cannot_close_the_title_tag(self):
        make_rule("A", title_template="A &lt;/title&gt; B")
        title = build()[0]["title"]
        self.assertNotIn("<", title)
        self.assertNotIn("&lt;", title)

    def test_site_name_replaces_erpnext(self):
        set_settings(site_name="Brand")
        page = web_context(metatags={"og:site_name": "ERPNext"})
        self.assertEqual(build(page)[0]["metatags"]["og:site_name"], "Brand")
        self.assertEqual(page.metatags["og:site_name"], "ERPNext")

    def test_page_without_document(self):
        make_rule("A", description_template="About {{ page.h1 }}")
        description = build()[0]["metatags"]["description"]
        self.assertEqual(description, "About " + PAGE_TITLE)


class TestHook(SeoTestCase):
    def test_preview_skips_rules(self):
        make_rule("A", title_template="Rule")
        values = {}
        frappe.flags[context.PREVIEW_FLAG] = True
        try:
            item_page.add_meta_tags(web_context(), values)
        finally:
            frappe.flags[context.PREVIEW_FLAG] = None
        self.assertEqual(values, {})

    def test_meta_failure_leaves_page(self):
        values = {}
        with patch.object(meta, "find_rule", side_effect=ValueError("boom")):
            item_page.add_meta_tags(web_context(), values)
        self.assertEqual(values, {})

    def test_rule_save_clears_cache(self):
        self.assertIsNone(meta.find_rule(None, ROUTE))
        make_rule("A")
        self.assertTrue(meta.find_rule(None, ROUTE))


class TestPageOutput(SeoTestCase):
    def setUp(self):
        super().setUp()
        frappe.get_doc(
            {
                "doctype": "Web Page",
                "title": PAGE_TITLE,
                "route": ROUTE,
                "published": 1,
                "content_type": "HTML",
                "main_section_html": "<p>x</p>",
            }
        ).insert()
        clear_cache()

    def test_hook_writes_rule_tags(self):
        make_rule("A", reference_doctype="Web Page", description_template="Rule {{ page.h1 }}")
        html = get_html_for_route(ROUTE)
        self.assertIn('<meta name="description" content="Rule {}">'.format(PAGE_TITLE), html)

    def test_rule_schema_template_is_in_graph(self):
        template = make_template("Typed", [prop("name", "typed", "Constant")], applies_to="Page Type")
        make_rule("A", schema_templates=[{"schema_template": template.name}])
        nodes = graphs_of(get_html_for_route(ROUTE))[0]
        self.assertEqual([node.get("name") for node in nodes].count("typed"), 1)
