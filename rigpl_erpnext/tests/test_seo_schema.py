"""Schema Template engine (#260)."""
import json
import sys
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_html_for_route, set_request
from frappe.website.render import clear_cache, render
from jinja2 import TemplateSyntaxError, UndefinedError
from jinja2.sandbox import SecurityError
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.website_rigpl import item_page
from rigpl_erpnext.website_rigpl.doctype.schema_template.schema_template import preview
from rigpl_erpnext.website_rigpl.seo import builder, context
from rigpl_erpnext.website_rigpl.seo.sandbox import check_syntax, evaluate

PREFIX = "_Test RIGPL "
ROUTE = "test-rigpl-schema"
PAGE_TITLE = "_Test RIGPL Schema Page"
SCRIPT_START = '<script type="application/ld+json">'
SCRIPT_END = "</script>"


def prop(name, value=None, value_type="Expression", **extra):
    return dict(property=name, value=value, value_type=value_type, **extra)


def template_doc(name, properties, **values):
    fields = dict(
        doctype="Schema Template",
        template_name=PREFIX + name,
        schema_type="Thing",
        applies_to="Component",
        enabled=1,
        properties=properties,
    )
    fields.update(values)
    return frappe.get_doc(fields)


def make_template(name, properties, **values):
    """Raw rows: skips the save checks, so a test can store a bad expression."""
    doc = template_doc(name, properties, **values)
    doc.name = doc.template_name
    doc.db_insert()
    for child in doc.properties:
        child.parent = doc.name
        child.name = frappe.generate_hash(length=10)
        child.db_insert()
    clear_schema_caches(doc.name)
    return doc


def clear_schema_caches(name=None):
    if name:
        frappe.clear_document_cache("Schema Template", name)
    builder.clear_template_cache()
    frappe.cache().delete_keys(builder.ERROR_CACHE_KEY)


def build(templates, variables=None):
    errors = []
    return builder.build_nodes(templates, variables or {}, errors), errors


def graphs_of(html):
    bodies = [part.split(SCRIPT_END)[0] for part in html.split(SCRIPT_START)[1:]]
    return [json.loads(body)["@graph"] for body in bodies]


class SchemaTestCase(FrappeTestCase):
    def setUp(self):
        clear_schema_caches()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()
        frappe.local.document_cache.clear()
        frappe.cache().delete_value("document_cache")
        clear_schema_caches()


class TestSandbox(SchemaTestCase):
    def test_single_expression_returns_native_value(self):
        self.assertEqual(evaluate("{{ doc.qty }}", {"doc": {"qty": 5}}), 5)
        self.assertEqual(evaluate("doc.tags", {"doc": {"tags": ["a", "b"]}}), ["a", "b"])
        self.assertEqual(evaluate("{{ doc.sku }}", {"doc": {"sku": "0012"}}), "0012")

    def test_mixed_source_returns_string(self):
        variables = {"page": {"url": "http://x/a"}}
        self.assertEqual(evaluate("{{ page.url }}#product", variables), "http://x/a#product")
        self.assertEqual(evaluate("{{ 1 }}-{{ 2 }}", {}), "1-2")

    def test_undefined_name_raises(self):
        for source in ("{{ doc.web_item_nme }}", "x {{ doc.web_item_nme }}", "nothing"):
            with self.assertRaises(UndefinedError):
                evaluate(source, {"doc": {}})

    def test_sandbox_has_no_frappe_and_no_writes(self):
        with self.assertRaises(UndefinedError):
            evaluate("frappe.db", {})
        for source in ("doc.update({'a': 1})", "doc.__class__.__mro__"):
            with self.assertRaises((SecurityError, UndefinedError)):
                evaluate(source, {"doc": {}})

    def test_check_syntax(self):
        check_syntax("{{ page.url }}#x")
        check_syntax("doc.name if doc else ''")
        for source in ("{{ page.url ", "doc.name if"):
            with self.assertRaises(TemplateSyntaxError):
                check_syntax(source)


class TestPermissions(SchemaTestCase):
    def test_only_website_manager_has_permissions(self):
        meta = frappe.get_meta("Schema Template")
        self.assertEqual({p.role for p in meta.permissions}, {"Website Manager"})
        self.assertFalse(frappe.has_permission("Schema Template", "read", user="Guest"))


class TestBuilder(SchemaTestCase):
    def test_bad_property_drops_only_itself(self):
        template = make_template("A", [prop("name", "{{ doc.title }}"), prop("sku", "{{ doc.nope }}")])
        nodes, errors = build([template], {"doc": {"title": "T"}})
        self.assertEqual(nodes, [{"@type": "Thing", "name": "T"}])
        self.assertEqual([e.property for e in errors], ["sku"])

    def test_output_parses_and_cannot_close_the_script(self):
        template = make_template("A", [prop("name", "{{ doc.title }}")])
        title = "a</script><b>&"
        graph = builder.build_graph([template], {"doc": {"title": title}}, [])
        script = builder.to_script(graph)
        self.assertEqual(script.count(SCRIPT_END), 1)
        self.assertEqual(graphs_of(script)[0][0]["name"], title)

    def test_empty_values_dropped_zero_kept(self):
        template = make_template("A", [prop("price", "{{ 0 }}"), prop("a", "''"), prop("b", "[]")])
        nodes, errors = build([template])
        self.assertEqual(nodes, [{"@type": "Thing", "price": 0}])
        self.assertEqual(errors, [])

    def test_iterate_over_and_condition(self):
        rows = {"rows": [{"n": 1}, {"n": 2}, {"n": 3}]}
        template = make_template(
            "A", [prop("position", "row.n", condition="row.n > 1"), prop("name", "x", "Constant")],
            iterate_over="rows",
        )
        nodes, _ = build([template], rows)
        self.assertEqual([n.get("position") for n in nodes], [None, 2, 3])

        off = make_template("B", [prop("name", "x", "Constant")], condition="false")
        self.assertEqual(build([off]), ([], []))

        wrong = make_template("C", [prop("name", "x", "Constant")], iterate_over="{{ 5 }}")
        nodes, errors = build([wrong])
        self.assertEqual((nodes, [e.property for e in errors]), ([], ["iterate_over"]))

    def test_linked_template_and_list(self):
        child = make_template("Child", [prop("name", "x", "Constant")])
        parent = make_template(
            "Parent",
            [
                prop("one", value_type="Template", linked_template=child.name),
                prop("many", value_type="Template List", linked_template=child.name),
            ],
        )
        nodes, errors = build([parent])
        node = {"@type": "Thing", "name": "x"}
        self.assertEqual((nodes[0]["one"], nodes[0]["many"], errors), (node, [node], []))

    def test_cycle_is_an_error_not_a_crash(self):
        link = lambda name: prop("next", value_type="Template", linked_template=PREFIX + name)
        first = make_template("A", [prop("name", "a", "Constant"), link("B")])
        make_template("B", [prop("name", "b", "Constant"), link("A")])
        nodes, errors = build([first])
        self.assertEqual(nodes[0]["next"]["name"], "b")
        self.assertEqual(len(errors), 1)
        self.assertIn("Cycle", errors[0].message)

    def test_same_id_merges(self):
        first = make_template("A", [prop("name", "a", "Constant")], id_expression="'x#a'")
        second = make_template("B", [prop("sku", "s", "Constant")], id_expression="'x#a'")
        nodes, _ = build([first, second])
        self.assertEqual(nodes, [{"@type": "Thing", "@id": "x#a", "name": "a", "sku": "s"}])

    def test_unserialisable_value_drops_property(self):
        template = make_template("A", [prop("name", "x", "Constant"), prop("bad", "{{ doc.items }}")])
        nodes, errors = build([template], {"doc": {}})
        self.assertEqual(nodes, [{"@type": "Thing", "name": "x"}])
        self.assertEqual([e.property for e in errors], ["bad"])

    def test_log_errors_once_per_hour(self):
        error = builder.BuildError(PREFIX + "Logged", "sku", "UndefinedError: nope")
        before = frappe.db.count("Error Log")
        builder.log_errors([error], ROUTE)
        builder.log_errors([error], ROUTE)
        self.assertEqual(frappe.db.count("Error Log"), before + 1)
        log = frappe.get_last_doc("Error Log")
        self.assertIn(ROUTE, log.method)
        self.assertIn(PREFIX + "Logged", log.error)

    def test_cached_build_runs_no_query(self):
        make_template("A", [prop("name", "x", "Constant")], applies_to="Site")

        def build_site():
            names = builder.get_template_names("Site")
            templates = [frappe.get_cached_doc("Schema Template", name) for name in names]
            builder.build_graph(templates, {"page": {"url": "u"}, "site": {}, "doc": {}}, [])

        build_site()
        with assert_max_queries(0, test_case=self):
            build_site()


class WebPageTestCase(SchemaTestCase):
    def setUp(self):
        super().setUp()
        self.web_page = frappe.get_doc(
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

    def tearDown(self):
        super().tearDown()
        clear_cache()


class TestPageOutput(WebPageTestCase):
    def render_nodes(self):
        graphs = graphs_of(get_html_for_route(ROUTE))
        self.assertEqual(len(graphs), 1)
        return graphs[0]

    def test_site_template_is_in_the_page(self):
        make_template("Site", [prop("name", "{{ page.h1 }}")], applies_to="Site")
        self.assertIn(PAGE_TITLE, [node.get("name") for node in self.render_nodes()])

    def test_bad_property_page_still_renders(self):
        template = make_template(
            "Site", [prop("name", "ok", "Constant"), prop("sku", "{{ doc.nope }}")], applies_to="Site"
        )
        set_request(method="GET", path=ROUTE)
        response = render()
        self.assertEqual(response.status_code, 200)
        self.assertIn("ok", [n.get("name") for n in graphs_of(frappe.safe_decode(response.get_data()))[0]])
        self.assertTrue(frappe.db.exists("Error Log", {"error": ["like", "%{}%".format(template.name)]}))

    def test_template_save_shows_after_cache_clear(self):
        template = template_doc(
            "Site", [prop("name", "old", "Constant")], applies_to="Site", sample_route=ROUTE
        ).insert()
        self.assertIn("old", [node.get("name") for node in self.render_nodes()])
        template.properties[0].value = "new"
        template.save()
        self.assertIn("new", [node.get("name") for node in self.render_nodes()])

    def test_engine_failure_keeps_the_page(self):
        make_template("Site", [prop("name", "x", "Constant")], applies_to="Site")
        with patch.object(builder, "build_graph", side_effect=ValueError("boom")):
            set_request(method="GET", path=ROUTE)
            response = render()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(SCRIPT_START, frappe.safe_decode(response.get_data()))

    def test_context_has_no_document_objects(self):
        variables = context.build_variables({"doc": self.web_page, "route": ROUTE, "parents": [self.web_page]})
        self.assertIs(type(variables["doc"]), dict)
        self.assertIs(type(variables["page"]["parents"][0]), dict)

    def test_item_page_values_are_kept(self):
        make_template("Site", [prop("name", "x", "Constant")], applies_to="Site")
        values = {}
        meta = '<meta name="x">'
        item_page.add_schema_graph(frappe._dict(route=ROUTE, head_include=meta), values)
        self.assertTrue(values["head_include"].startswith(meta + SCRIPT_START))

    def test_page_route_is_the_path(self):
        web_context = {"route": "blog", "path": "blog/general/" + ROUTE}
        page = context.build_variables(web_context)["page"]
        self.assertEqual(page["route"], "blog/general/" + ROUTE)
        self.assertTrue(page["url"].endswith("/blog/general/" + ROUTE))

    def test_h1_has_no_title_prefix(self):
        web_context = {"route": ROUTE, "title": "Brand - " + PAGE_TITLE, "title_prefix": "Brand"}
        page = context.build_variables(web_context)["page"]
        self.assertEqual((page["title"], page["h1"]), ("Brand - " + PAGE_TITLE, PAGE_TITLE))

    def test_route_is_rendered_as_guest_and_the_session_comes_back(self):
        users = []
        session = frappe.local.session
        before = (session.user, session.sid, session.data)
        with patch.object(context, "get_context", side_effect=lambda r: users.append(frappe.session.user)):
            context.get_route_context(ROUTE)
        self.assertEqual(users, ["Guest"])
        self.assertEqual((session.user, session.sid, session.data), before)

    def test_logging_failure_keeps_the_page(self):
        make_template("Site", [prop("name", "x", "Constant")], applies_to="Site")
        values = {}
        with patch.object(builder, "build_graph", side_effect=ValueError("boom")):
            with patch.object(builder, "log_errors", side_effect=ValueError("no log")):
                item_page.add_schema_graph(frappe._dict(route=ROUTE), values)
        self.assertEqual(values, {})

    def test_import_failure_keeps_the_page(self):
        values = {}
        with patch.dict(sys.modules, {builder.__name__: None}):
            item_page.add_schema_graph(frappe._dict(route=ROUTE), values)
        self.assertEqual(values, {})


class TestSaveChecks(WebPageTestCase):
    def new_template(self, properties, **values):
        values.setdefault("sample_route", ROUTE)
        return template_doc("Saved", properties, **values)

    def assert_blocked(self, text, properties, **values):
        with self.assertRaisesRegex(frappe.ValidationError, text):
            self.new_template(properties, **values).insert()

    def test_syntax_error_blocks_save(self):
        self.assert_blocked("Row 1 Value", [prop("name", "{{ page.title ")], enabled=0)

    def test_missing_type_property_blocks_save(self):
        self.assert_blocked("price", [prop("url", "page.url")], schema_type="Offer")

    def test_product_needs_one_of_offers_review_rating(self):
        self.assert_blocked("offers or review", [prop("name", "page.title")], schema_type="Product")
        self.new_template(
            [prop("name", "page.title"), prop("review", "r", "Constant")], schema_type="Product"
        ).insert()

    def test_merchant_listing_needs_image(self):
        self.assert_blocked(
            "image",
            [prop("name", "page.title"), prop("offers", "o", "Constant")],
            schema_type="Product",
            merchant_listing=1,
        )

    def test_required_row_empty_on_sample_route_blocks_save(self):
        self.assert_blocked("sku has no value", [prop("sku", "doc.get('nope')", required=1)])

    def test_bad_optional_property_saves_with_warning(self):
        frappe.clear_messages()
        doc = self.new_template([prop("name", "page.title"), prop("sku", "doc.nope")]).insert()
        self.assertTrue(frappe.db.exists("Schema Template", doc.name))
        self.assertIn("sku", json.dumps(frappe.get_message_log()))

    def test_disabled_template_saves_incomplete(self):
        self.new_template([], schema_type="Offer", enabled=0).insert()

    def test_save_clears_template_cache(self):
        builder.get_template_names("Site")
        doc = self.new_template([prop("name", "page.title")], applies_to="Site").insert()
        self.assertIn(doc.name, builder.get_template_names("Site"))


class TestPreview(WebPageTestCase):
    def setUp(self):
        super().setUp()
        self.template = make_template("Preview", [prop("name", "page.h1"), prop("sku", "doc.nope")])

    def test_preview_returns_graph_and_errors(self):
        result = preview(self.template.name, ROUTE)
        self.assertEqual(json.loads(result["json"])["@graph"][0]["name"], PAGE_TITLE)
        self.assertEqual([e["property"] for e in result["errors"]], ["sku"])

    def test_preview_needs_write_permission(self):
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            preview(self.template.name, ROUTE)

    def test_preview_unknown_route_throws(self):
        with self.assertRaises(frappe.PageDoesNotExistError):
            preview(self.template.name, "test-rigpl-no-such-page")
