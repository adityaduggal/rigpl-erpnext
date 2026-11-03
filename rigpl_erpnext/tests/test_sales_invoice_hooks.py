from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.validations import sales_invoice

PL_OPEN = "_Test RIGPL SI PL Open"
PL_BLOCKED = "_Test RIGPL SI PL Blocked"
STOCK_ITEM = "_Test RIGPL SI Stock"
SERVICE_ITEM = "_Test RIGPL SI Service"
SO = "_Test RIGPL SI SO"
TPT_FEDEX = "_Test RIGPL SI FedEx"
FEDEX_ACCOUNT = "_Test RIGPL SI FedEx Account"
TPT_HAND = "_Test RIGPL SI By Hand"


def insert_raw(doctype, name, **fields):
    frappe.get_doc(dict(doctype=doctype, name=name, **fields)).db_insert()


def si_row(idx, item_code=STOCK_ITEM, price_list=PL_OPEN, rate=100.0, **fields):
    return frappe._dict(idx=idx, item_code=item_code, price_list=price_list, price_list_rate=rate, **fields)


def si_doc(rows, **fields):
    # Not a frappe._dict: its .items is the dict method
    values = dict(doctype="Sales Invoice", name="_Test RIGPL SI 1", currency="INR", selling_price_list=PL_OPEN,
        ignore_pricing_rule=0, amended_from=None, transporters=TPT_HAND, lr_no="AB-12 3", taxes_and_charges=None)
    values.update(fields)
    return SimpleNamespace(items=rows, **values)


class SalesInvoiceHookCase(FrappeTestCase):
    def setUp(self):
        insert_raw("Price List", PL_OPEN, price_list_name=PL_OPEN, selling=1, currency="INR", enabled=1)
        insert_raw("Price List", PL_BLOCKED, price_list_name=PL_BLOCKED, selling=1, currency="INR", enabled=1,
            disable_so=1)
        for name, is_stock in ((STOCK_ITEM, 1), (SERVICE_ITEM, 0)):
            insert_raw("Item", name, item_code=name, item_name=name, item_group="All Item Groups",
                stock_uom="Nos", is_stock_item=is_stock)
            for pl in (PL_OPEN, PL_BLOCKED):
                insert_raw("Item Price", frappe.generate_hash(length=10), item_code=name, price_list=pl,
                    price_list_rate=100.0, currency="INR", selling=1)
        insert_raw("Shipping Provider Account", FEDEX_ACCOUNT, account_name=FEDEX_ACCOUNT, provider="FedEx", enabled=1)
        insert_raw("Transporters", TPT_FEDEX, api_mode="Booking and Tracking", shipping_provider_account=FEDEX_ACCOUNT)
        insert_raw("Transporters", TPT_HAND, api_mode="None")

    def tearDown(self):
        frappe.db.rollback()
        for name in (TPT_FEDEX, TPT_HAND):
            frappe.clear_document_cache("Transporters", name)
        frappe.clear_document_cache("Shipping Provider Account", FEDEX_ACCOUNT)


class TestPriceList(SalesInvoiceHookCase):
    def test_so_rows_get_the_so_price_list(self):
        insert_raw("Sales Order Item", "_Test RIGPL SOI 1", parent=SO, parenttype="Sales Order",
            parentfield="items", item_code=STOCK_ITEM, price_list=PL_BLOCKED)
        doc = si_doc([si_row(1, price_list=None, so_detail="_Test RIGPL SOI 1")])
        sales_invoice.validate_price_list(doc, None)
        self.assertEqual(doc.items[0].price_list, PL_BLOCKED)

    def test_empty_price_list_uses_selling_price_list(self):
        doc = si_doc([si_row(1, price_list=None)])
        sales_invoice.validate_price_list(doc, None)
        self.assertEqual(doc.items[0].price_list, PL_OPEN)

    def test_blocked_price_list_throws_only_for_stock_items(self):
        sales_invoice.validate_price_list(si_doc([si_row(1, SERVICE_ITEM, PL_BLOCKED)]), None)
        with self.assertRaisesRegex(frappe.ValidationError, "{} are Blocked".format(PL_BLOCKED)):
            sales_invoice.validate_price_list(si_doc([si_row(1, SERVICE_ITEM, PL_BLOCKED),
                si_row(2, STOCK_ITEM, PL_BLOCKED)]), None)

    def test_rate_mismatch_names_the_first_wrong_row(self):
        doc = si_doc([si_row(1), si_row(2, rate=90.0), si_row(3, SERVICE_ITEM, rate=80.0)])
        with self.assertRaisesRegex(frappe.ValidationError, "in Row# 2 does not match"):
            sales_invoice.validate_price_list(doc, None)

    def test_rate_mismatch_in_other_currency_passes(self):
        sales_invoice.validate_price_list(si_doc([si_row(1, rate=90.0)], currency="USD"), None)

    def test_query_count_does_not_depend_on_rows(self):
        sales_invoice.validate_price_list(si_doc([si_row(1, SERVICE_ITEM, PL_BLOCKED),
            si_row(2, so_detail="_Test RIGPL SOI X")]), None)
        rows = [si_row(i, SERVICE_ITEM, PL_BLOCKED if i % 2 else PL_OPEN) for i in range(1, 11)]
        rows += [si_row(11, so_detail="_Test RIGPL SOI X")]
        with assert_max_queries(4, test_case=self):
            sales_invoice.validate_price_list(si_doc(rows), None)


class TestUpdateFields(SalesInvoiceHookCase):
    def insert_track(self, name, **fields):
        insert_raw("Carrier Tracking", name, document="Sales Invoice", carrier_name=TPT_FEDEX,
            awb_number="AWB-" + name, **fields)

    def test_track_of_the_invoice(self):
        self.insert_track("_Test RIGPL CT 1", document_name="_Test RIGPL SI 1")
        doc = si_doc([])
        sales_invoice.update_fields(doc)
        self.assertEqual((doc.transporters, doc.lr_no), (TPT_FEDEX, "AWB-_Test RIGPL CT 1"))

    def test_track_of_the_cancelled_invoice(self):
        self.insert_track("_Test RIGPL CT 2", document_name="", reference_document_name="_Test RIGPL SI 0")
        doc = si_doc([], amended_from="_Test RIGPL SI 0")
        sales_invoice.update_fields(doc)
        self.assertEqual(doc.lr_no, "AWB-_Test RIGPL CT 2")

    def test_no_track(self):
        doc = si_doc([], transporters=TPT_FEDEX)
        sales_invoice.update_fields(doc)
        self.assertEqual(doc.lr_no, "NA")
        doc = si_doc([])
        sales_invoice.update_fields(doc)
        self.assertEqual(doc.lr_no, "AB123")

    def test_check_existing_track(self):
        self.insert_track("_Test RIGPL CT 3", document_name="_Test RIGPL SI 1")
        self.insert_track("_Test RIGPL CT 4", document_name="_Test RIGPL SI 1", docstatus=2)
        self.assertEqual(sales_invoice.check_existing_track("Sales Invoice", "_Test RIGPL SI 1"),
            [["_Test RIGPL CT 3"]])
        self.assertIsNone(sales_invoice.check_existing_track("Sales Invoice", "_Test RIGPL O'Brien"))

    def test_is_tracked_transporter(self):
        self.assertEqual(sales_invoice.is_tracked_transporter(si_doc([], transporters=TPT_FEDEX), None), 1)
        self.assertEqual(sales_invoice.is_tracked_transporter(si_doc([]), None), 0)


class TestUntrackedStockItems(SalesInvoiceHookCase):
    def doc(self, count=1):
        rows = [si_row(i, SERVICE_ITEM) for i in range(1, count)] + [si_row(count, STOCK_ITEM)]
        return si_doc(rows, ignore_pricing_rule=1)

    def test_only_system_manager_can_submit(self):
        with patch.object(frappe, "get_roles", return_value=["Accounts User"]):
            with self.assertRaisesRegex(frappe.ValidationError, "ask a System Manager"):
                sales_invoice.check_untracked_stock_items(self.doc())
        with patch.object(frappe, "get_roles", return_value=["System Manager"]):
            sales_invoice.check_untracked_stock_items(self.doc())

    def test_rows_with_so_or_service_items_pass(self):
        with patch.object(frappe, "get_roles", return_value=["Accounts User"]):
            sales_invoice.check_untracked_stock_items(si_doc([si_row(1, SERVICE_ITEM)], ignore_pricing_rule=1))
            sales_invoice.check_untracked_stock_items(si_doc([si_row(1, sales_order=SO)], ignore_pricing_rule=1))
            sales_invoice.check_untracked_stock_items(si_doc([si_row(1)], ignore_pricing_rule=0))

    def test_query_count_does_not_depend_on_rows(self):
        with patch.object(frappe, "get_roles", return_value=["System Manager"]):
            sales_invoice.check_untracked_stock_items(self.doc(1))
            with assert_max_queries(1, test_case=self):
                sales_invoice.check_untracked_stock_items(self.doc(10))


class TestTrialTracking(SalesInvoiceHookCase):
    def setUp(self):
        super().setUp()
        insert_raw("Sales Order", SO, track_trial=1)
        insert_raw("Sales Order", SO + " Plain", track_trial=0)
        for i in range(1, 6):
            insert_raw("Delivery Note Item", "_Test RIGPL DNI {}".format(i), parent="_Test RIGPL DN",
                parenttype="Delivery Note", parentfield="items", so_detail="_Test RIGPL SOI {}".format(i))
            insert_raw("Trial Tracking", "_Test RIGPL TT {}".format(i),
                prevdoc_detail_docname="_Test RIGPL SOI {}".format(i))

    def invoice_nos(self):
        return dict(frappe.get_all("Trial Tracking", filters={"name": ("like", "_Test RIGPL TT %")},
            fields=["name", "invoice_no"], as_list=1))

    def test_set_and_clear(self):
        doc = si_doc([si_row(1, sales_order=SO, dn_detail="_Test RIGPL DNI 1"),
            si_row(2, sales_order=SO, so_detail="_Test RIGPL SOI 2"),
            si_row(3, sales_order=SO + " Plain", dn_detail="_Test RIGPL DNI 3"), si_row(4)])
        sales_invoice.set_trial_invoice(doc, doc.name)
        nos = self.invoice_nos()
        self.assertEqual([nos["_Test RIGPL TT {}".format(i)] for i in range(1, 5)],
            [doc.name, doc.name, None, None])
        sales_invoice.set_trial_invoice(doc, None)
        self.assertFalse(any(self.invoice_nos().values()))

    def test_query_count_does_not_depend_on_rows(self):
        rows = [si_row(i, sales_order=SO, dn_detail="_Test RIGPL DNI {}".format(i)) for i in range(1, 6)]
        sales_invoice.set_trial_invoice(si_doc(rows[:1]), "_Test RIGPL SI 1")
        with assert_max_queries(5, test_case=self):
            sales_invoice.set_trial_invoice(si_doc(rows), "_Test RIGPL SI 1")
        self.assertEqual(set(self.invoice_nos().values()), {"_Test RIGPL SI 1"})
