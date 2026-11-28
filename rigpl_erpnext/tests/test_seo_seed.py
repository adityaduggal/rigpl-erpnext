"""Default SEO records and the company data that they read (#263)."""
import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.website_rigpl import item_page
from rigpl_erpnext.website_rigpl.doctype.seo_settings.seo_settings import create_records
from rigpl_erpnext.website_rigpl.seo import builder, context, images, locations, meta, organization
from rigpl_erpnext.website_rigpl.doctype.seo_settings import seo_settings
from rigpl_erpnext.website_rigpl.website_data.seo import importer, records
from rigpl_erpnext.website_rigpl.website_data.seo.records import HOME_RULE, SCHEMA_TEMPLATES, SEO_RULES
from rigpl_erpnext.www import llms

TEMPLATE_NAMES = [record["template_name"] for record in SCHEMA_TEMPLATES]
RULE_NAMES = [record["rule_name"] for record in SEO_RULES + [HOME_RULE]]


def add_location(address):
    """A row of SEO Settings > Company Addresses, without the save checks."""
    frappe.get_doc(
        {
            "doctype": "SEO Location",
            "name": frappe.generate_hash(length=10),
            "parent": "SEO Settings",
            "parenttype": "SEO Settings",
            "parentfield": "addresses",
            "address": address,
        }
    ).db_insert()
    frappe.clear_document_cache("SEO Settings", "SEO Settings")


def block_row(web_template, values, idx=1, hide_block=0):
    return frappe._dict(
        web_template=web_template,
        web_template_values=frappe.as_json(values),
        idx=idx,
        hide_block=hide_block,
    )


def delete_seed_records():
    """Rows only. The test rolls back."""
    for doctype, child, names in (
        ("SEO Rule", "SEO Rule Schema Template", RULE_NAMES),
        ("Schema Template", "Schema Template Property", TEMPLATE_NAMES),
    ):
        frappe.db.delete(child, {"parent": ["in", names]})
        frappe.db.delete(doctype, {"name": ["in", names]})


class SeedTestCase(FrappeTestCase):
    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()
        frappe.local.document_cache.clear()
        for doctype in ("SEO Settings", "Website Settings"):
            frappe.clear_document_cache(doctype, doctype)
        builder.clear_template_cache()
        meta.clear_caches()


class TestOrganization(SeedTestCase):
    def setUp(self):
        self.company = frappe.db.get_single_value("Global Defaults", "default_company")
        settings = frappe.get_doc("SEO Settings", "SEO Settings")
        settings.update({"company": None, "addresses": [], "social_group": None})
        settings.save()

    def tearDown(self):
        super().tearDown()
        frappe.clear_document_cache("Company", self.company)

    def set_website(self, **values):
        website = frappe.get_cached_doc("Website Settings", "Website Settings")
        website.update(values)
        return website

    def test_values_come_from_the_company(self):
        frappe.db.set_value("Company", self.company, "phone_no", "+91 00000 00000")
        frappe.clear_document_cache("Company", self.company)
        self.assertEqual(organization.get_organization()["telephone"], "+91 00000 00000")

    def test_company_address_comes_from_the_linked_address(self):
        address = frappe.get_doc(
            {
                "doctype": "Address",
                "address_title": "_Test RIGPL SEO",
                "address_type": "Office",
                "address_line1": "Line 1",
                "city": "Test City",
                "country": "India",
                "state": "Delhi",
                "pincode": "110001",
            }
        )
        # a set name skips the Address autoname rules of rohit_common
        address.name = "_Test RIGPL SEO-Office"
        address.db_insert()
        add_location(address.name)
        values = organization.get_organization()["address"]
        self.assertEqual((values["city"], values["country_code"]), ("Test City", "IN"))

    def test_no_address_gives_empty_dict(self):
        self.assertEqual(organization.get_address(None), {})
        self.assertIsNone(organization.find_company_address("_Test RIGPL No Company"))

    def test_private_logo_is_not_used(self):
        self.set_website(banner_image="/private/files/logo.png")
        self.assertEqual(organization.get_organization()["logo"], "")

    def test_social_links_skip_messages_and_other_groups(self):
        rows = [
            frappe._dict(parent_label="Social", url="https://www.linkedin.com/company/x"),
            frappe._dict(parent_label="Social", url="https://api.whatsapp.com/send?phone=1"),
            frappe._dict(parent_label="Social", url="/about"),
            frappe._dict(parent_label="Company", url="https://example.com"),
        ]
        links = organization.get_social_links(frappe._dict(footer_items=rows), "Social")
        self.assertEqual(links, ["https://www.linkedin.com/company/x"])


class TestSeed(SeedTestCase):
    def setUp(self):
        delete_seed_records()
        builder.clear_template_cache()
        meta.clear_caches()

    def test_creates_all_records(self):
        self.assertEqual(importer.create_missing_records(), TEMPLATE_NAMES + RULE_NAMES)
        self.assertTrue(frappe.db.get_single_value("SEO Settings", "site_name"))

    def test_second_run_keeps_an_edit(self):
        importer.create_missing_records()
        frappe.db.set_value("SEO Rule", "Web Pages", "title_template", "Edited")
        self.assertEqual(importer.create_missing_records(), [])
        self.assertEqual(frappe.db.get_value("SEO Rule", "Web Pages", "title_template"), "Edited")

    def test_no_constant_values(self):
        types = {row["value_type"] for record in SCHEMA_TEMPLATES for row in record["properties"]}
        self.assertEqual(types, {"Expression", "Template", "Template List"})

    def test_site_templates_build_without_errors(self):
        importer.create_missing_records()
        names = ["Company", "WebPage", "WebSite"]
        templates = [frappe.get_doc("Schema Template", name) for name in names]
        graph, errors, _ = templates[0].render_route("")
        self.assertEqual((graph["@graph"][0]["@type"], errors), ("Organization", []))
        for template in templates[1:]:
            self.assertEqual(template.render_route("")[1], [])

    def test_seed_runs_one_time(self):
        frappe.db.delete("Patch Log", {"patch": importer.SEED_PATCH})
        importer.seed_seo_once()
        self.assertTrue(frappe.db.exists("Schema Template", "Company"))
        delete_seed_records()
        importer.seed_seo_once()
        self.assertFalse(frappe.db.exists("Schema Template", "Company"))

    def test_create_records_needs_write_permission(self):
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            create_records()


class TestHomeBlocks(SeedTestCase):
    """Web Page block markup (#269). Needs a home page with blocks and a published product."""

    def setUp(self):
        delete_seed_records()
        builder.clear_template_cache()
        meta.clear_caches()
        importer.create_missing_records()

    def published_item(self):
        name = frappe.db.get_value("Website Item", {"published": 1})
        if not name:
            self.skipTest("The site has no published Website Item")
        return name

    def blocks(self, *rows):
        return context.get_blocks(frappe._dict(page_blocks=list(rows)))

    def test_linked_products_keep_order_and_skip_unpublished(self):
        item = self.published_item()
        row = block_row("Item Card Group", {"card_1_item": "_Test RIGPL No Item", "card_2_item": item})
        products = self.blocks(row)[0]["products"]
        self.assertEqual([(p["name"], p["position"]) for p in products], [(item, 1)])
        self.assertTrue(products[0]["url"].startswith("http"))

    def test_hidden_block_is_not_used(self):
        row = block_row("RIGPL Contact Strip", {"phone": "1"}, hide_block=1)
        self.assertEqual(self.blocks(row), [])

    def test_slides_come_from_the_slideshow(self):
        slideshow = frappe.get_doc(
            {
                "doctype": "Website Slideshow",
                "slideshow_name": "_Test RIGPL SEO",
                "slideshow_items": [{"image": "/files/a b.png", "heading": "<b>One</b>"}],
            }
        ).insert()
        row = block_row("Slideshow", {"website_slideshow": slideshow.name})
        slide = self.blocks(row)[0]["slides"][0]
        self.assertTrue(slide["image"].endswith("/files/a%20b.png"))
        self.assertEqual(slide["heading"], "One")

    def test_blocks_of_one_type_get_their_own_node(self):
        item = self.published_item()
        values = {"card_1_item": item}
        blocks = self.blocks(
            block_row("Item Card Group", values, idx=1), block_row("Item Card Group", values, idx=2)
        )
        template = frappe.get_doc("Schema Template", "Item Card Group List")
        errors = []
        variables = {"page": {"url": "http://x"}}
        nodes = builder.build_page_nodes([template], variables, blocks, errors)
        self.assertEqual([n["@id"] for n in nodes], ["http://x#itemlist-1", "http://x#itemlist-2"])
        self.assertEqual(errors, [])

    def test_video_needs_title_and_upload_date(self):
        template = frappe.get_doc("Schema Template", "Social Video")
        blocks = self.blocks(block_row("RIGPL Social Feeds", {"youtube_video_id": "abc"}))
        errors = []
        self.assertEqual(builder.build_page_nodes([template], {"page": {}}, blocks, errors), [])
        self.assertEqual(errors, [])

    def test_contact_strip_joins_the_organization(self):
        templates = [frappe.get_doc("Schema Template", name) for name in ("Company", "Contact Strip")]
        blocks = self.blocks(block_row("RIGPL Contact Strip", {"phone": "+91 1"}))
        variables = context.build_variables({"path": "x"})
        nodes = builder.build_page_nodes(templates, variables, blocks, [])
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["contactPoint"]["telephone"], "+91 1")

    def test_home_page_blocks_build_without_errors(self):
        for name in builder.get_template_names("Web Template"):
            graph, errors, _ = frappe.get_doc("Schema Template", name).render_route("")
            self.assertEqual(errors, [], name)


class TestNavigation(SeedTestCase):
    """Navigation and breadcrumb markup (#264)."""

    def test_crumbs_are_the_visible_breadcrumb(self):
        parents = [{"name": name, "route": name.lower()} for name in ("A", "B", "C", "D")]
        web_context = {"path": "x", "title": "Page", "parents": parents}
        crumbs = context.get_crumbs(web_context, "Shown | Brand")
        self.assertEqual([c["name"] for c in crumbs], ["B", "C", "D", "Shown | Brand"])
        self.assertEqual([c["position"] for c in crumbs], [1, 2, 3, 4])
        self.assertTrue(crumbs[-1]["url"].endswith("/x"))

    def test_index_parent_is_the_site_root(self):
        web_context = {"path": "x", "title": "P", "parents": [{"label": "Home", "route": "index"}]}
        self.assertEqual(context.get_crumbs(web_context)[0]["url"], context.get_url("/"))

    def test_no_crumbs_without_a_visible_breadcrumb(self):
        parents = [{"name": "Home", "route": "/"}]
        self.assertEqual(context.get_crumbs({"title": "P"}), [])
        self.assertEqual(context.get_crumbs({"parents": parents, "no_breadcrumbs": 1}), [])

    def test_top_bar_skips_rows_without_a_link(self):
        rows = [
            frappe._dict(label="Products", url=None),
            frappe._dict(label="Drills", url=" hss drills"),
            frappe._dict(label="Menu", url="#"),
        ]
        links = context.get_top_bar({"top_bar_items": rows})
        self.assertEqual([(link["position"], link["name"]) for link in links], [(1, "Drills")])
        self.assertTrue(links[0]["url"].endswith("/hss%20drills"))

    def test_live_page_has_the_breadcrumb_and_navigation(self):
        delete_seed_records()
        builder.clear_template_cache()
        meta.clear_caches()
        importer.create_missing_records()
        route = frappe.db.get_value("Item Group", {"show_in_website": 1, "lft": [">", 5]}, "route")
        if not route:
            self.skipTest("The site has no Item Group page")
        web_context = context.get_route_context(route)
        values = {"title": "Shown"}
        item_page.write_schema_graph(web_context, values, dict(web_context))
        graph = json.loads(values["head_include"].split('ld+json">')[-1].split("</script>")[0])["@graph"]
        crumbs = [node for node in graph if node["@type"] == "BreadcrumbList"][0]["itemListElement"]
        self.assertEqual(crumbs[-1]["name"], "Shown")
        self.assertTrue([node for node in graph if node["@type"] == "SiteNavigationElement"])


class TestCatalog(SeedTestCase):
    """Product and category markup (#265, #266). Needs published products on the site."""

    def setUp(self):
        delete_seed_records()
        builder.clear_template_cache()
        meta.clear_caches()
        importer.create_missing_records()

    def route(self, doctype, filters):
        route = frappe.db.get_value(doctype, filters, "route")
        if not route:
            self.skipTest("The site has no page: {}".format(doctype))
        return route

    def graph(self, template, route):
        graph, errors, _ = frappe.get_doc("Schema Template", template).render_route(route)
        self.assertEqual(errors, [])
        return graph["@graph"]

    def test_template_page_has_one_product_for_each_table_row(self):
        route = self.route("Website Item", {"published": 1, "has_variants": 1})
        name = frappe.db.get_value("Website Item", {"route": route})
        group = self.graph("Product Group", route)[0]
        self.assertEqual(len(group["hasVariant"]), len(context.get_variant_table(name)["rows"]))

    def test_variants_above_the_limit_have_only_the_address_and_code(self):
        route = self.route("Website Item", {"published": 1, "has_variants": 1})
        frappe.db.set_value("SEO Settings", None, "variant_limit", 1)
        frappe.clear_document_cache("SEO Settings", "SEO Settings")
        variants = self.graph("Product Group", route)[0]["hasVariant"]
        if len(variants) < 2:
            self.skipTest("The template has one variant")
        self.assertEqual(set(variants[0]), {"@type", "@id", "sku", "url"})

    def test_guest_with_hidden_price_gets_no_offer(self):
        cart = frappe._dict(enabled=1, show_price=1, hide_price_for_guest=1, price_list="x")
        with patch.object(context, "get_ecommerce", return_value=lambda: cart):
            self.assertIsNone(context.Offers(["x"]).get("x", "u", 1))

    def test_shipping_charge_comes_from_the_matching_row(self):
        rows = [
            frappe._dict(from_value=0, to_value=1000, shipping_amount=100),
            frappe._dict(from_value=1001, to_value=0, shipping_amount=500),
        ]
        rule = {"based_on": "Net Total", "conditions": rows, "amount": 0}
        self.assertEqual(context.get_shipping_charge(rule, 10), 100)
        self.assertEqual(context.get_shipping_charge(rule, 2000), 500)
        self.assertIsNone(context.get_shipping_charge(dict(rule, conditions=rows[:1]), 2000))

    def test_incomplete_return_policy_is_not_output(self):
        settings = frappe._dict(return_policy="MerchantReturnFiniteReturnWindow", return_days=0)
        self.assertEqual(organization.get_return_policy(settings, "IN"), {})
        settings.return_days = 15
        self.assertEqual(organization.get_return_policy(settings, "IN")["days"], 15)

    def test_template_page_queries_do_not_grow_with_the_variants(self):
        route = self.route("Website Item", {"published": 1, "has_variants": 1})
        doc = context.get_route_context(route)["doc"]
        context.get_catalog(doc)  # fills the document caches
        with assert_max_queries(20):
            context.get_catalog(doc)

    def test_category_page_lists_its_products_or_sub_categories(self):
        route = self.route("Item Group", {"show_in_website": 1, "lft": [">", 5]})
        page = self.graph("Collection Page", route)[0]
        self.assertTrue(page["mainEntity"]["itemListElement"])


class TestImages(SeedTestCase):
    """Image alt text and the image check (#267)."""

    def add_file(self, url, comment=None):
        file = frappe.get_doc({"doctype": "File", "file_url": url, "file_name": url.rsplit("/", 1)[-1]})
        file.name = frappe.generate_hash(length=10)
        file.db_insert()
        if comment:
            file.add_comment("Comment", comment)

    def page(self, html, **values):
        return frappe.get_doc(
            dict(
                doctype="Web Page",
                title="_Test RIGPL Images",
                route="test-rigpl-images",
                content_type="HTML",
                main_section_html=html,
                **values,
            )
        )

    def test_readable_name(self):
        self.assertEqual(
            images.get_readable_name("/files/Carbide_End_Mills-1-145a048.jpg"), "Carbide End Mills 1 1"
        )
        for name in ("Untitled.jpg", "fVLyrOC.png", "334_Series.jpg", "C311.jpg"):
            self.assertEqual(images.get_readable_name("/files/" + name), "")

    def test_comment_wins_over_the_file_name(self):
        url = "/files/_test rigpl carbide drill.png"
        self.add_file(url, "<p>Alt: Step drill</p>")
        self.assertEqual(images.get_file_alts(["http://x/files/_test%20rigpl%20carbide%20drill.png"]), {url: "Step drill"})

    def test_only_images_without_alt_are_filled(self):
        html = (
            '<img src="/files/a.png" alt="Own"><img src="/files/a.png">'
            '<img width="1" src="http://t/p"><script>var x = "<img src=1>";</script>'
        )
        filled = images.add_alt(html, {"/files/a.png": 'A "b"'}, "Page")
        self.assertIn('<img src="/files/a.png" alt="Own">', filled)
        self.assertIn('<img alt="A &quot;b&quot;" src="/files/a.png">', filled)
        self.assertIn('<img alt="" width="1"', filled)
        self.assertIn('"<img src=1>"', filled)

    def test_item_gets_the_comment_text(self):
        self.add_file("/files/_t1.png", "Alt: Tool")
        doc = frappe._dict(doctype="Website Item", website_image="/files/_t1.png")
        images.fill_page(frappe._dict(doc=doc), {}, "Page")
        self.assertEqual(doc.website_image_alt, "Tool")

    def test_new_image_without_alt_stops_the_save(self):
        with self.assertRaises(frappe.ValidationError):
            images.validate_images(self.page('<img src="/files/_x1.png">'))
        for html in (
            '<img src="/files/_x1.png" alt="Drill">',
            '<img src="/files/_x1.png" alt="">',
            '<img src="/files/carbide drill.png">',
            '<img src="https://example.com/x.png">',
        ):
            images.validate_images(self.page(html))

    def test_old_image_and_system_save_only_warn(self):
        html = '<img src="/files/_x1.png">'
        doc = self.page(html)
        doc._doc_before_save = self.page(html)
        images.validate_images(doc)
        doc = self.page(html)
        doc.flags.ignore_permissions = True
        images.validate_images(doc)

    def test_meta_image_address_is_encoded(self):
        web_context = frappe._dict(path="x", metatags={"image": "/files/a b.png"})
        tags = meta.build_meta(web_context, None, [])["metatags"]
        self.assertTrue(tags["image"].endswith("/files/a%20b.png"))


class TestHeadings(SeedTestCase):
    """One H1 on each page (#268)."""

    def web_page(self, **values):
        doc = frappe._dict(doctype="Web Page", title="Doc", content_type="HTML", route="x")
        return frappe._dict(dict(doc=doc, title="Brand - Doc", title_prefix="Brand", path="x"), **values)

    def headings(self, web_context, **values):
        item_page.add_headings(web_context, values, dict(web_context))
        return values

    def test_title_tag_keeps_the_seo_title_and_the_page_shows_the_h1(self):
        values = self.headings(self.web_page(main_section="<p>a</p>"), title="SEO Title")
        self.assertEqual((values["seo_title"], values["title"]), ("SEO Title", "Doc"))

    def test_page_without_h1_gets_a_hidden_one(self):
        values = self.headings(self.web_page(main_section="<p>a</p>"))
        self.assertEqual(values["main_section"], '<h1 class="sr-only">Doc</h1><p>a</p>')

    def test_page_with_h1_gets_no_second_one(self):
        for web_context in (
            self.web_page(main_section="<H1>a</H1>"),
            self.web_page(main_section="a", header="<h1>Doc</h1>"),
        ):
            self.assertNotIn("main_section", self.headings(web_context))

    def test_hidden_header_does_not_count(self):
        values = self.headings(self.web_page(main_section="a", header="<h1>Doc</h1>", no_header=1))
        self.assertIn("sr-only", values["main_section"])

    def test_page_without_document_keeps_its_own_browser_title(self):
        values = self.headings(frappe._dict(title="Brand - Contact", title_prefix="Brand", path="contact"))
        self.assertEqual((values.get("seo_title"), values["title"]), (None, "Contact"))

    def test_title_tag_comes_from_seo_title(self):
        self.assertEqual(frappe.get_hooks("base_template")[-1], "templates/rigpl_base.html")
        self.assertTrue(frappe.get_jenv().get_template("templates/rigpl_base.html"))


class TestSocialFeeds(SeedTestCase):
    """The script addresses and the height are fields of the block (#269)."""

    def render(self, **values):
        template = frappe.get_doc("Web Template", "RIGPL Social Feeds")
        values.update(twitter_handle="h", facebook_id="f", youtube_channel_id="c")
        return template.render(values)

    def test_empty_fields_keep_the_provider_addresses(self):
        html = self.render()
        for text in ("platform.twitter.com/widgets.js", "connect.facebook.net", "apis.google.com", "500px"):
            self.assertIn(text, html)

    def test_fields_replace_the_defaults(self):
        html = self.render(twitter_script_url='https://example.com/"x.js', timeline_height="300")
        self.assertIn("max-height: 300px", html)
        self.assertIn("https://example.com/&#34;x.js", html)
        self.assertNotIn("platform.twitter.com/widgets.js", html)


class TestHomepageSection(SeedTestCase):
    """The cards of a Homepage Section block (#269)."""

    def setUp(self):
        delete_seed_records()
        builder.clear_template_cache()
        meta.clear_caches()
        importer.create_missing_records()

    def nodes(self, cards):
        section = frappe.get_doc(
            {"doctype": "Homepage Section", "section_cards": cards, "section_order": 1}
        )
        section.name = "_Test RIGPL Section"
        section.flags.name_set = True
        section.insert()
        row = block_row("RIGPL Homepage Section", {"homepage_section": section.name})
        template = frappe.get_doc("Schema Template", "Homepage Section List")
        errors = []
        built = builder.build_page_nodes(
            [template], {"page": {"url": "u"}}, context.get_blocks(frappe._dict(page_blocks=[row])), errors
        )
        self.assertEqual(errors, [])
        return built

    def test_cards_make_an_item_list(self):
        node = self.nodes([{"title": "One", "content": "<p>Text</p>", "route": "/a"}])[0]
        element = node["itemListElement"][0]
        self.assertEqual((node["name"], element["name"], element["description"]), ("_Test RIGPL Section", "One", "Text"))
        self.assertTrue(element["url"].endswith("/a"))

    def test_section_without_cards_makes_no_node(self):
        self.assertEqual(self.nodes([]), [])


class TestContentPages(SeedTestCase):
    """Blog posts, About and Contact (#270)."""

    def setUp(self):
        delete_seed_records()
        builder.clear_template_cache()
        meta.clear_caches()
        importer.create_missing_records()

    def live_graph(self, route):
        web_context = context.get_route_context(route)
        values = {}
        item_page.write_schema_graph(web_context, values, dict(web_context))
        script = values["head_include"].split('ld+json">')[-1].split("</script>")[0]
        return json.loads(script)["@graph"]

    def test_about_and_contact_change_the_web_page_type(self):
        for route, schema_type in (("about", "AboutPage"), ("contact", "ContactPage")):
            pages = [n for n in self.live_graph(route) if n.get("@id", "").endswith("#webpage")]
            self.assertEqual([n["@type"] for n in pages], [schema_type])

    def test_blog_post_has_author_and_image(self):
        filters = {"published": 1, "blogger": ["is", "set"]}
        route = frappe.db.get_value("Blog Post", filters, "route")
        if not route:
            self.skipTest("The site has no published Blog Post")
        post = [n for n in self.live_graph(route) if n["@type"] == "BlogPosting"][0]
        self.assertEqual(post["author"]["@type"], "Person")
        self.assertTrue(post["author"]["name"] and post["datePublished"] and post["dateModified"])

    def test_private_avatar_and_user_are_not_output(self):
        row = frappe._dict(full_name="A", bio="<p>B</p>", avatar="/private/files/a.png")
        with patch.object(frappe.db, "get_value", return_value=row):
            self.assertEqual(context.get_author("x"), {"name": "A", "description": "B", "image": ""})


class TestAIAssistants(SeedTestCase):
    """llms.txt, AI crawlers and FAQ markup (#271)."""

    def settings(self, **values):
        settings = frappe.get_doc("SEO Settings", "SEO Settings")
        settings.update(values)
        settings.save()

    def test_denied_crawlers_keep_the_other_robots_lines(self):
        text = "User-agent: *\nDisallow: /desk"
        denied = seo_settings.make_robots(text, ["GPTBot"])
        self.assertIn("User-agent: GPTBot\nDisallow: /", denied)
        self.assertTrue(denied.startswith(text))
        self.assertEqual(seo_settings.make_robots(denied, ["GPTBot"]), denied)
        self.assertEqual(seo_settings.make_robots(denied, []), text)

    def test_save_writes_the_robots_section(self):
        self.settings(denied_ai_crawlers="GPTBot\nGPTBot\n")
        robots = frappe.db.get_single_value("Website Settings", "robots_txt")
        self.assertEqual(robots.count("User-agent: GPTBot"), 1)

    def test_bad_crawler_name_stops_the_save(self):
        with self.assertRaises(frappe.ValidationError):
            self.settings(denied_ai_crawlers="x: y")

    def test_llms_txt_follows_the_setting(self):
        self.settings(llms_enabled=1, llms_body="# {{ site.brand }} test")
        text = llms.get_context({})["llms_txt"]
        self.assertTrue(text.endswith(" test"))
        self.settings(llms_enabled=0)
        with self.assertRaises(frappe.PageDoesNotExistError):
            llms.get_context({})

    def test_default_llms_body_renders(self):
        self.settings(llms_enabled=1, llms_body=records.LLMS_BODY)
        self.assertIn("## Product categories", llms.get_context({})["llms_txt"])

    def test_faq_markup_is_off_until_enabled(self):
        delete_seed_records()
        builder.clear_template_cache()
        importer.create_missing_records()
        if not frappe.db.exists("Web Template", "RIGPL FAQ"):
            self.skipTest("Run migrate to get the Web Template")
        template = frappe.get_doc("Schema Template", "FAQ Page")
        self.assertFalse(template.enabled)
        template.enabled = 1
        blocks = context.get_blocks(
            frappe._dict(page_blocks=[block_row("RIGPL FAQ", {"questions": [{"question": "Q", "answer": "A"}]})])
        )
        node = builder.build_page_nodes([template], {"page": {"url": "u"}}, blocks, [])[0]
        self.assertEqual(node["mainEntity"][0]["acceptedAnswer"]["text"], "A")


HOURS = "day,opens,closes\nMonday,9:00,17:30\nTuesday,9:00,17:30\nSaturday,09:00,13:00\nSunday,,\n"


class TestLocations(SeedTestCase):
    """LocalBusiness from the company addresses (#272)."""

    def test_parse_hours(self):
        hours = locations.parse_hours(HOURS + "area_served,India; Nepal\n")
        self.assertEqual(hours["days"]["Monday"], ("09:00", "17:30"))
        self.assertNotIn("Sunday", hours["days"])
        self.assertEqual(hours["area_served"], ["India", "Nepal"])

    def test_bad_rows_name_the_row(self):
        for text, message in (
            ("a,b,c\n", "Row 1"),
            ("day,opens,closes\nFunday,9:00,10:00\n", "Row 2"),
            ("day,opens,closes\nMonday,9,10:00\n", "Row 2"),
            ("day,opens,closes\nMonday,10:00,09:00\n", "Row 2"),
            ("day,opens,closes\nMonday,9:00,10:00\nMonday,9:00,10:00\n", "Row 3"),
        ):
            with self.assertRaisesRegex(ValueError, message):
                locations.parse_hours(text)

    def test_weekly_off_and_holidays_are_closed(self):
        days = locations.parse_hours(HOURS)["days"]
        rows = locations.make_opening_hours(days, {"weekly_off": "Saturday", "dates": ["2030-01-01"]})
        self.assertEqual(rows[0]["days"], ["Monday", "Tuesday"])
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[1]["opens"], rows[1]["closes"], rows[1]["valid_from"]), ("00:00", "00:00", "2030-01-01"))
        self.assertEqual(locations.make_opening_hours({}, {"dates": ["2030-01-01"]}), [])

    def test_hours_file_name(self):
        self.assertTrue(locations.is_hours_file("working_hours_BGH-1.csv", "BGH-1"))
        self.assertTrue(locations.is_hours_file("working_hours_BGH-1a1b2c3.csv", "BGH-1"))
        self.assertFalse(locations.is_hours_file("working_hours_BGH-2.csv", "BGH-1"))

    def test_bad_hours_file_stops_the_upload(self):
        file = frappe._dict(
            attached_to_doctype="Address",
            file_name="working_hours_x.csv",
            get_content=lambda: "wrong",
        )
        with self.assertRaises(frappe.ValidationError):
            locations.validate_hours_file(file)

    def test_contact_page_has_each_location(self):
        delete_seed_records()
        builder.clear_template_cache()
        meta.clear_caches()
        importer.create_missing_records()
        name = frappe.db.get_value("Address", {"is_your_company_address": 1, "disabled": 0})
        if not name:
            self.skipTest("The site has no company address")
        frappe.db.delete("SEO Location", {"parent": "SEO Settings"})
        add_location(name)
        graph, errors, _ = frappe.get_doc("Schema Template", "Local Business").render_route("contact")
        self.assertEqual(errors, [])
        business = [n for n in graph["@graph"] if n["@type"] == "LocalBusiness"]
        self.assertEqual(len(business), 1)
        self.assertTrue(business[0]["name"] and business[0]["address"])
