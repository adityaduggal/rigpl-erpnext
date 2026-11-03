"""
Payment Entry, Bank Account, Holiday List, Important Documents and Purchase Invoice checks after the
move from '%s' SQL to parameters (#187). Each name or value has a quote: the old code put it into the
SQL text and failed.
"""
from types import SimpleNamespace

import frappe

from rigpl_erpnext.hr_rigpl.validations import holiday_list
from rigpl_erpnext.rigpl_erpnext.validations import bank_account, payment_entry
from rigpl_erpnext.rigpl_erpnext.validations.purchase_invoice import create_valuation_rate
from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw

PARTY = "_Test RIGPL O'Brien Bank Party"
ACCOUNT = "_Test RIGPL O'Bank - Account"
TEMPLATE = "_Test RIGPL O'Rod Template"
BASE_LIST = "_Test RIGPL O'Base Holidays"
FROM, TO = "2026-04-01", "2027-03-31"


def insert_bank_account(name, **values):
    values.setdefault("party_type", "Supplier")
    values.setdefault("party", PARTY)
    return raw("Bank Account", name=name, account_name=name, **values)


def insert_rod(name, diameter, length, tool_type="Round Tool Bits"):
    raw("Item", name=name, item_code=name, item_name=name, variant_of=TEMPLATE, is_stock_item=1)
    for idx, (att, value) in enumerate((("Tool Type", tool_type), ("d1_mm", diameter), ("l1_mm", length))):
        raw("Item Variant Attribute", parent=name, parenttype="Item", parentfield="attributes", idx=idx + 1,
            attribute=att, attribute_value=value)


class TestPaymentEntryBankAccount(ReportTestCase):
    def pay_doc(self, **values):
        values.setdefault("party_bank_account", None)
        return frappe._dict(name="_Test PE", payment_type="Pay", party_type="Supplier", party=PARTY,
            paid_from=ACCOUNT, paid_to=None, **values)

    def test_party_account_is_the_verified_one(self):
        insert_bank_account("_Test RIGPL O'Party Unverified", verified=0)
        insert_bank_account("_Test RIGPL O'Party Verified", verified=1)
        doc = self.pay_doc()
        payment_entry.update_party_bank_account(doc)
        self.assertEqual(doc.party_bank_account, "_Test RIGPL O'Party Verified")

        doc = self.pay_doc(party_bank_account="_Test RIGPL O'Party Unverified")
        with self.assertRaisesRegex(frappe.ValidationError, "O'Party Unverified Selected is Not a Verified"):
            payment_entry.update_party_bank_account(doc)

    def test_company_account_by_ledger(self):
        insert_bank_account("_Test RIGPL O'Company Bank", verified=1, is_company_account=1, account=ACCOUNT,
            party_type=None, party=None)
        doc = self.pay_doc()
        payment_entry.update_comp_bank_account(doc)
        self.assertEqual(doc.bank_account, "_Test RIGPL O'Company Bank")
        doc.paid_from = "_Test RIGPL O'Other - Account"
        payment_entry.update_comp_bank_account(doc)
        self.assertEqual(doc.bank_account, "")


class TestBankAccount(ReportTestCase):
    def new_doc(self, name):
        return frappe._dict(name=name, is_company_account=0, party_type="Supplier", party=PARTY,
            bank_account_no="1'2", bank=None)

    def test_one_account_per_party(self):
        insert_bank_account("_Test RIGPL O'First Account", allow_multiple=0)
        with self.assertRaisesRegex(frappe.ValidationError, "Already Exists"):
            bank_account.validate(self.new_doc("_Test RIGPL O'Second Account"), None)
        bank_account.validate(self.new_doc("_Test RIGPL O'First Account"), None)

    def test_allow_multiple(self):
        insert_bank_account("_Test RIGPL O'First Account", allow_multiple=1)
        bank_account.validate(self.new_doc("_Test RIGPL O'Second Account"), None)


class TestHolidayList(ReportTestCase):
    def test_base_list_of_another_cannot_be_non_base(self):
        raw("Holiday List", name="_Test RIGPL O'Child", holiday_list_name="_Test RIGPL O'Child", is_base_list=0,
            base_holiday_list=BASE_LIST, from_date=FROM, to_date=TO)
        doc = frappe._dict(name=BASE_LIST, is_base_list=0, base_holiday_list="", from_date=FROM, to_date=TO,
            holidays=[])
        with self.assertRaisesRegex(frappe.ValidationError, "O'Child and hence Cannot"):
            holiday_list.validate(doc, None)

    def test_pull_holidays_from_linked_list(self):
        frappe.get_doc(doctype="Holiday List", holiday_list_name=BASE_LIST, is_base_list=1, from_date=FROM,
            to_date=TO).insert()
        frappe.get_doc(doctype="Holiday List", holiday_list_name="_Test RIGPL O'Child", is_base_list=0,
            base_holiday_list=BASE_LIST, from_date=FROM, to_date=TO,
            holidays=[{"holiday_date": "2026-08-15", "description": "O'Independence Day"}]).insert()
        holiday_list.pull_holidays(BASE_LIST, FROM, TO)
        rows = frappe.get_all("Holiday", filters={"parent": BASE_LIST}, pluck="description")
        self.assertEqual(rows, ["O'Independence Day"])

        with self.assertRaisesRegex(frappe.ValidationError, "No Holiday List Linked"):
            holiday_list.pull_holidays(BASE_LIST, FROM, "2027-03-30")


class TestImportantDocumentFiles(ReportTestCase):
    def test_get_files(self):
        name = "_Test RIGPL O'DWG"
        raw("File", file_name=name + "-2D.pdf", attached_to_doctype="Important Documents",
            attached_to_name=name, is_private=1)
        doc = frappe.new_doc("Important Documents")
        doc.name = name
        files = doc.get_files()
        self.assertEqual([(f.file_name, f.is_private) for f in files], [(name + "-2D.pdf", 1)])


class TestPurchaseInvoiceValuation(ReportTestCase):
    def test_cut_pieces_by_length(self):
        raw("Item", name=TEMPLATE, item_code=TEMPLATE, item_name=TEMPLATE, has_variants=1)
        insert_rod("_Test RIGPL O'Rod 100", "6", "100")
        insert_rod("_Test RIGPL O'Rod 80", " 6.0", "80")
        insert_rod("_Test RIGPL O'Rod 40", "6", "40")
        insert_rod("_Test RIGPL O'Rod 8mm", "8", "50")
        po = raw("Purchase Order", is_subcontracting=0)
        doc = SimpleNamespace(posting_date="2026-10-01", items=[
            frappe._dict(purchase_order=po, item_code="_Test RIGPL O'Rod 100", base_net_rate=1000)])

        # 1 PO, 1 Item, 1 attribute map, 1 variants, 1 lengths, 3 writes (lock + update each)
        self.assert_queries(11, lambda: create_valuation_rate(doc))
        rates = dict(frappe.get_all("Item", filters={"variant_of": TEMPLATE},
            fields=["name", "valuation_rate"], as_list=1))
        # ratio 1, 0.8 (factor 0.9), 0.4 (factor 0.8); round down to 10
        self.assertEqual(rates["_Test RIGPL O'Rod 100"], 1000)
        self.assertEqual(rates["_Test RIGPL O'Rod 80"], 720)
        self.assertEqual(rates["_Test RIGPL O'Rod 40"], 320)
        self.assertFalse(rates["_Test RIGPL O'Rod 8mm"])
        self.assertEqual(str(frappe.db.get_value("Item", "_Test RIGPL O'Rod 40", "valuation_rate_date")),
            "2026-10-01")
