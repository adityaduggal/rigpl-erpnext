"""Default SEO records and the company data that they read (#263)."""
import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.website_rigpl.doctype.seo_settings.seo_settings import create_records
from rigpl_erpnext.website_rigpl.seo import builder, meta, organization
from rigpl_erpnext.website_rigpl.website_data.seo import importer
from rigpl_erpnext.website_rigpl.website_data.seo.records import SCHEMA_TEMPLATES, SEO_RULES

TEMPLATE_NAMES = [record["template_name"] for record in SCHEMA_TEMPLATES]
RULE_NAMES = [record["rule_name"] for record in SEO_RULES]


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
        settings.update({"company": None, "address": None, "social_group": None})
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
        address.db_insert()
        frappe.db.set_value("SEO Settings", None, "address", address.name)
        frappe.clear_document_cache("SEO Settings", "SEO Settings")
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
        self.assertEqual(types, {"Expression", "Template"})

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
