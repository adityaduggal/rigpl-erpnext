# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

from frappe.utils import formatdate, nowdate
import frappe
from rohit_common.utils.file_rules import clear_rule_cache

from rigpl_erpnext.rigpl_erpnext.doctype.important_documents import important_documents as idoc
from rigpl_erpnext.tests.test_item_attribute_utils import add_item_attribute
from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw

USER = "_test_rigpl_idoc_search@example.com"
CUSTOMER, HIDDEN = "_Test RIGPL IDoc Customer", "_Test RIGPL IDoc Hidden Customer"
TXT = "_Test RIGPL IDoc"


def insert_order(customer, date, docstatus=1):
	return raw("Sales Order", customer=customer, customer_name=customer, transaction_date=date,
		docstatus=docstatus)


def insert_order_item(order, idx, item_code, description):
	return raw("Sales Order Item", parent=order, parenttype="Sales Order", parentfield="items", idx=idx,
		item_code=item_code, description=description)


def orders(txt=TXT):
	return idoc.sales_order_query("Sales Order", txt, "name", 0, 20, {})


def order_items(order, txt=""):
	return idoc.sales_order_item_query("Sales Order Item", txt, "name", 0, 20, {"sales_order": order})


class TestImportantDocumentSearch(ReportTestCase):
	def restrict_user_to(self, customer):
		# db_insert, no hooks: the User hooks commit in tests
		raw("User", name=USER, email=USER, first_name="_Test RIGPL IDoc", user_type="System User", enabled=1)
		raw("Has Role", parent=USER, parenttype="User", parentfield="roles", role="Sales User")
		raw("Customer", name=customer, customer_name=customer)
		frappe.clear_cache(user=USER)
		frappe.get_doc(dict(doctype="User Permission", user=USER, allow="Customer", for_value=customer,
			apply_to_all_doctypes=1)).insert(ignore_permissions=True)
		frappe.set_user(USER)

	def test_submitted_orders_latest_first(self):
		old = insert_order(CUSTOMER, "2026-01-05")
		new = insert_order(CUSTOMER, "2026-03-05")
		insert_order(CUSTOMER, "2026-04-05", docstatus=0)

		rows = orders()

		self.assertEqual([row[0] for row in rows], [new, old])
		self.assertEqual(list(rows[0][1:]), [formatdate("2026-03-05"), CUSTOMER])

	def test_order_search_text(self):
		insert_order(CUSTOMER, "2026-01-05")
		other = insert_order(HIDDEN, "2026-01-05")

		self.assertEqual([row[0] for row in orders(HIDDEN)], [other])
		self.assertEqual([row[0] for row in orders(other)], [other])

	def test_items_in_idx_order_without_html(self):
		order = insert_order(CUSTOMER, "2026-01-05")
		second = insert_order_item(order, 2, "_Test IDoc B", "Reamer")
		first = insert_order_item(order, 1, "_Test IDoc A", "<div><p>Drill 6mm</p></div>")

		rows = order_items(order)

		self.assertEqual([list(row) for row in rows], [
			[first, "#1 _Test IDoc A", "Drill 6mm"], [second, "#2 _Test IDoc B", "Reamer"]])
		self.assertEqual([row[0] for row in order_items(order, "Reamer")], [second])

	def test_no_items_without_a_sales_order(self):
		insert_order_item(insert_order(CUSTOMER, "2026-01-05"), 1, "_Test IDoc A", "Drill")

		self.assertEqual(order_items(None), [])
		self.assertEqual(order_items(["!=", ""]), [])

	def test_user_permission_on_customer(self):
		mine = insert_order(CUSTOMER, "2026-01-05")
		hidden = insert_order(HIDDEN, "2026-02-05")
		my_item = insert_order_item(mine, 1, "_Test IDoc A", "Drill")
		insert_order_item(hidden, 1, "_Test IDoc B", "Reamer")
		self.restrict_user_to(CUSTOMER)

		self.assertEqual([row[0] for row in orders()], [mine])
		self.assertEqual([row[0] for row in order_items(mine)], [my_item])
		self.assertEqual(order_items(hidden), [])

	def test_values_of_a_sales_order_item(self):
		order = insert_order(CUSTOMER, "2026-01-05")
		row = insert_order_item(order, 1, "_Test IDoc A", "Drill")

		self.assertEqual(idoc.get_sales_order_item_values(row), {"item": "_Test IDoc A", "description": "Drill"})

	def test_no_values_of_an_order_the_user_cannot_read(self):
		row = insert_order_item(insert_order(HIDDEN, "2026-01-05"), 1, "_Test IDoc B", "Reamer")
		self.restrict_user_to(CUSTOMER)

		self.assertRaises(frappe.PermissionError, idoc.get_sales_order_item_values, row)

	def test_category_name_of_tool_types_only(self):
		add_item_attribute("_Test RIGPL IDoc Attribute", 0, ["_Test IDoc Not A Tool Type"])
		other = frappe.db.get_value("Item Attribute Value", {"parent": "_Test RIGPL IDoc Attribute"})
		value = raw("Item Attribute Value", parent="Tool Type", parenttype="Item Attribute",
			parentfield="item_attribute_values", attribute_value="_Test IDoc Tool", abbr="_TIT")

		self.assertEqual(idoc.get_category_name(value), "_Test IDoc Tool")
		self.assertIsNone(idoc.get_category_name(other))

	def test_categories_are_tool_types_with_abbr_and_long_description(self):
		add_item_attribute("_Test RIGPL IDoc Attribute", 0, ["_Test IDoc Not A Tool Type"])
		value = raw("Item Attribute Value", parent="Tool Type", parenttype="Item Attribute",
			parentfield="item_attribute_values", attribute_value="_Test IDoc Tool", abbr="_TIT",
			long_description="_Test IDoc Long")

		rows = idoc.category_query("Item Attribute Value", "_Test IDoc", "name", 0, 20, {})

		self.assertEqual([list(row) for row in rows], [[value, "_Test IDoc Tool", "_TIT", "_Test IDoc Long"]])


class NoSiteRulesTestCase(ReportTestCase):
	def setUp(self):
		# The rules of the site must not apply here. The rollback restores them.
		frappe.db.sql("update `tabFile Attachment Rule` set enabled = 0")
		clear_rule_cache()

	def tearDown(self):
		super().tearDown()
		clear_rule_cache()


class TestImportantDocumentValues(NoSiteRulesTestCase):
	def sales_order_drawing(self):
		order = insert_order(CUSTOMER, "2026-01-05")
		row = insert_order_item(order, 1, "_Test IDoc A", "<div><p>Order Drill</p></div>")
		raw("Item", name="_Test IDoc A", item_code="_Test IDoc A", description="Item Drill", has_variants=0)
		return frappe.get_doc(dict(doctype="Important Documents", type="Drawing", drawing_based_on="Sales Order",
			sales_order=order, sales_order_item=row, customer=CUSTOMER, item="_Test IDoc A", template=0))

	def test_description_of_the_sales_order_item_stays(self):
		doc = self.sales_order_drawing()

		self.assert_queries(2, doc.validate)

		self.assertEqual(doc.description, "Order Drill")
		self.assertEqual(doc.title, "DWG: Sales Order: {}: {}: _Test IDoc A".format(CUSTOMER, doc.sales_order))

	def test_empty_template_means_not_a_template(self):
		# The form cleared the check box with ""
		doc = self.sales_order_drawing()
		doc.template = ""

		doc.validate()

		self.assertEqual(doc.item, "_Test IDoc A")

	def test_title_leaves_out_empty_parts(self):
		doc = frappe.get_doc(dict(doctype="Important Documents", type="Standard", standard_number="338"))

		doc.validate()

		self.assertEqual(doc.title, "STD: 338")

	def test_standard_year_range(self):
		doc = frappe.get_doc(dict(doctype="Important Documents", type="Standard", standard_year=1899))

		message = "from 1900 to {}, not 1899".format(nowdate()[:4])
		self.assertRaisesRegex(frappe.ValidationError, message, doc.validate)


class TestImportantDocumentAttachments(NoSiteRulesTestCase):
	def setUp(self):
		super().setUp()
		raw("Customer", name=CUSTOMER, customer_name=CUSTOMER)

	def add_rule(self):
		specs = [dict(label=label, name_pattern=pattern, allowed_extensions=extensions, min_count=1,
			max_count=1, private_only=1) for label, pattern, extensions in
			(("2D Drawing", "{name}-2D", "pdf"), ("3D Model", "{name}-3D", "sldprt"))]
		frappe.get_doc(dict(doctype="File Attachment Rule", title="_Test IDoc Drawing", apply_to="DocType",
			document_type="Important Documents", enabled=1, condition='doc.type == "Drawing"',
			specs=specs)).insert()

	def new_drawing(self):
		frappe.clear_messages()
		return frappe.get_doc(dict(doctype="Important Documents", type="Drawing", drawing_based_on="Customer",
			customer=CUSTOMER, description="_Test IDoc Drawing")).insert()

	def attach(self, doc, *suffixes):
		for suffix in suffixes:
			file_name = doc.name + suffix
			raw("File", file_name=file_name, file_url="/private/files/" + file_name, file_size=10, is_private=1,
				attached_to_doctype=doc.doctype, attached_to_name=doc.name)

	def assert_warnings(self, *titles):
		messages = [frappe.parse_json(message) for message in frappe.local.message_log]
		self.assertEqual([(m.get("title"), m.get("indicator")) for m in messages],
			[(title, "orange") for title in titles])

	def test_without_a_rule_save_warns_and_submit_fails(self):
		doc = self.new_drawing()

		self.assert_warnings("No Attachment Rule")
		self.assertRaisesRegex(frappe.ValidationError, "No File Attachment Rule", doc.submit)

	def test_wrong_files_warn_on_save_and_stop_the_submit(self):
		self.add_rule()
		doc = self.new_drawing()
		self.attach(doc, "-old.pdf")
		frappe.clear_messages()

		doc.save()

		self.assert_warnings("Attachments Not Ready")
		self.assertRaisesRegex(frappe.ValidationError, "does not match", doc.submit)

	def test_correct_files_submit_without_a_warning(self):
		self.add_rule()
		doc = self.new_drawing()
		self.attach(doc, "-2D.pdf", "-3D.sldprt")
		frappe.clear_messages()

		doc.submit()

		self.assertEqual(doc.docstatus, 1)
		self.assert_warnings()
