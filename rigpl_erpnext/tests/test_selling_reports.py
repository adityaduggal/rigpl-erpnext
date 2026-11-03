"""
Selling and CRM reports after the move from '%s' SQL to frappe.qb (#187). Each name has a quote:
the old reports put it into the SQL text and failed.
"""
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.report.brc_tracking import brc_tracking
from rigpl_erpnext.rigpl_erpnext.report.cforms_analysis import cforms_analysis
from rigpl_erpnext.rigpl_erpnext.report.compare_pricing import compare_pricing
from rigpl_erpnext.rigpl_erpnext.report.customer_rating import customer_rating
from rigpl_erpnext.rigpl_erpnext.report.customers_with_so import customers_with_so
from rigpl_erpnext.rigpl_erpnext.report.follow_up_customer import follow_up_customer
from rigpl_erpnext.rigpl_erpnext.report.follow_up_lead import follow_up_lead
from rigpl_erpnext.rigpl_erpnext.report.forex_transactions import forex_transactions
from rigpl_erpnext.rigpl_erpnext.report.rigpl_price_list import rigpl_price_list
from rigpl_erpnext.rigpl_erpnext.report.tod_sales_invoice import tod_sales_invoice
from rigpl_erpnext.rigpl_erpnext.report.todo_report import todo_report
from rigpl_erpnext.rigpl_erpnext.report.trial_tracking import trial_tracking
from rigpl_erpnext.rigpl_erpnext.report.va_sales_invoice import va_sales_invoice
from rigpl_erpnext.tests.test_sales_utils import insert_customer
from rigpl_erpnext.tests.test_variant_table import insert_item, insert_item_price
from rigpl_erpnext.utils.item_utils import get_pricing_rules_for_items
from rigpl_erpnext.utils.report_utils import tree_and_descendants

CUSTOMER = "_Test RIGPL O'Brien Report Customer"
OTHER_CUSTOMER = "_Test RIGPL O'Brien Report Customer 2"
TERRITORY = "_Test RIGPL O'Brien Report Territory"
CHILD_TERRITORY = "_Test RIGPL O'Brien Report Territory Child"
ITEM = "_Test RIGPL O'Brien Report Item"
ITEM_2 = "_Test RIGPL O'Brien Report Item 2"
TEMPLATE = "_Test RIGPL O'Brien Report Template"
BM = "_Test RIGPL O'Metal"
PL = ("_Test RIGPL O'PL 1", "_Test RIGPL O'PL 2", "_Test RIGPL O'PL 3")
LEAD = "_Test RIGPL O'Brien Report Lead"
DATE = "2026-01-15"


def raw(doctype, **values):
    """Insert a row without hooks. Returns its name."""
    values.setdefault("name", frappe.generate_hash(length=10))
    doc = frappe.get_doc(dict(doctype=doctype, **values))
    doc.db_insert()
    return doc.name


def set_columns(doctype, name, **values):
    """Set columns that are not in the v13 meta (v12 data, for example Contact.customer)."""
    tab = frappe.qb.DocType(doctype)
    query = frappe.qb.update(tab).where(tab.name == name)
    for field, value in values.items():
        query = query.set(field, value)
    query.run()


def insert_invoice(customer, items, posting_date=DATE, **values):
    """items: [(item_code, base_net_amount)]"""
    name = raw("Sales Invoice", customer=customer, posting_date=posting_date, docstatus=1, **values)
    for idx, (item_code, amount) in enumerate(items, start=1):
        raw("Sales Invoice Item", parent=name, parenttype="Sales Invoice", parentfield="items", idx=idx,
            docstatus=1, item_code=item_code, description=item_code, qty=1, base_net_amount=amount,
            base_amount=amount, base_rate=amount, base_net_rate=amount)
    return name


def insert_territories():
    raw("Territory", name=TERRITORY, territory_name=TERRITORY, is_group=1, lft=990001, rgt=990004)
    raw("Territory", name=CHILD_TERRITORY, territory_name=CHILD_TERRITORY, parent_territory=TERRITORY,
        lft=990002, rgt=990003)


class ReportTestCase(FrappeTestCase):
    def assert_queries(self, limit, run):
        """Run once to load the meta into the cache, then count the queries of the report itself."""
        run()
        with assert_max_queries(limit, test_case=self):
            return run()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()


class TestReportUtils(ReportTestCase):
    def test_tree_and_descendants(self):
        insert_territories()
        self.assertEqual(sorted(tree_and_descendants("Territory", TERRITORY)), sorted([TERRITORY, CHILD_TERRITORY]))
        self.assertEqual(tree_and_descendants("Territory", CHILD_TERRITORY), [CHILD_TERRITORY])
        self.assertRaises(frappe.ValidationError, tree_and_descendants, "Territory", "_Test RIGPL No Territory")


class TestTodoReport(ReportTestCase):
    def test_user_sees_own_todos_with_desk_link(self):
        mine = raw("ToDo", status="Open", description="O'Brien call", owner="Guest", creation=DATE,
            reference_type="Lead", reference_name=LEAD)
        raw("ToDo", status="Open", description="other", owner="Administrator", creation=DATE)
        frappe.set_user("Guest")

        data = todo_report.execute(frappe._dict(status="Open"))[1]

        self.assertEqual([row[0] for row in data], [mine])
        self.assertIn("/app/Form/Lead/", data[0][5])


class TestTodSalesInvoice(ReportTestCase):
    def test_summary_and_detail(self):
        insert_item(ITEM, variant_of=TEMPLATE)
        insert_item(ITEM_2, variant_of=TEMPLATE)
        frappe.db.set_value("Item", ITEM, "stock_maintained", 1, update_modified=False)
        insert_invoice(CUSTOMER, [(ITEM, 100), (ITEM_2, 50)])
        filters = dict(customer=CUSTOMER, from_date="2026-01-01", to_date="2026-01-31")

        split = self.assert_queries(3, lambda: tod_sales_invoice.execute(
            frappe._dict(filters, summary=1, separated_tod=1))[1])

        self.assertEqual(split, [[CUSTOMER, 50, "No"], [CUSTOMER, 100, "Yes"]])
        self.assertEqual(tod_sales_invoice.execute(frappe._dict(filters, summary=1))[1], [[CUSTOMER, 150]])
        detail = tod_sales_invoice.execute(frappe._dict(filters))[1]
        self.assertEqual([(row[3], row[10]) for row in detail], [(ITEM, "Yes"), (ITEM_2, "No")])


class TestTrialTracking(ReportTestCase):
    def test_days_since_order(self):
        so_date = add_days(nowdate(), -40)
        so = raw("Sales Order", customer=CUSTOMER, transaction_date=so_date, docstatus=1)
        raw("Trial Tracking", against_sales_order=so, status="Passed", customer=CUSTOMER, item_code=ITEM,
            trial_owner="O'Brien", docstatus=1)

        data = trial_tracking.execute(frappe._dict(trial_status="Passed", customer=CUSTOMER, trial_owner="O'Brien"))[1]

        self.assertEqual([(row[4], row[11], row[12]) for row in data], [(CUSTOMER, "Not Invoiced", 40)])


class TestForexTransactions(ReportTestCase):
    def test_only_invoice_doctypes(self):
        bad = frappe._dict(doctype="Sales Invoice` WHERE 1=1 --", company="_Test RIGPL O'Company")
        self.assertRaises(frappe.ValidationError, forex_transactions.execute, bad)

    def test_foreign_currency_invoices(self):
        name = insert_invoice(CUSTOMER, [], currency="_Test RIGPL O'USD", grand_total=10, base_grand_total=800)
        company = frappe.defaults.get_global_default("company")
        filters = frappe._dict(doctype="Sales Invoice", company=company, from_date=DATE, to_date=DATE)

        data = forex_transactions.execute(filters)[1]

        self.assertIn([name, getdate(DATE), CUSTOMER], [list(row[:3]) for row in data])


class TestBrcTracking(ReportTestCase):
    def test_quoted_status_filter(self):
        si = insert_invoice(CUSTOMER, [], base_net_total=500)
        brc = raw("BRC MEIS Tracking", reference_doctype="Sales Invoice", reference_name=si, docstatus=1,
            brc_status="BRC Issued", shipping_bill_date=DATE, meis_status="MEIS Pending")

        data = brc_tracking.execute(frappe._dict(docstatus="Submitted", from_date=DATE, brc_status="BRC Issued"))[1]
        self.assertIn(brc, [row[0] for row in data])
        self.assertFalse(brc_tracking.execute(frappe._dict(brc_status="O'Brien"))[1])
        meis = brc_tracking.execute(frappe._dict(docstatus="Submitted", meis_status="MEIS Pending", to_date=DATE))[1]
        self.assertIn(brc, [row[0] for row in meis])


class TestCformsAnalysis(ReportTestCase):
    def test_detail_quarter_and_summary(self):
        insert_customer(CUSTOMER)
        fy = frappe.db.get_value("Fiscal Year", {"year_start_date": ("<=", DATE), "year_end_date": (">=", DATE)})
        insert_invoice(CUSTOMER, [], c_form_applicable="Yes", net_total=100, grand_total=118, letter_head="O'Head")
        insert_invoice(CUSTOMER, [], posting_date="2026-02-15", c_form_applicable="Yes", net_total=50,
            grand_total=59, letter_head="O'Head")
        filters = dict(status="Not Received", customer=CUSTOMER, letter_head="O'Head")

        detail = cforms_analysis.execute(frappe._dict(filters))[1]
        summary = cforms_analysis.execute(frappe._dict(filters, summary=1))[1]

        self.assertEqual([(row[2], row[7], row[8]) for row in detail], [(CUSTOMER, fy, "Q4"), (CUSTOMER, fy, "Q4")])
        self.assertEqual([row[:4] for row in summary], [[CUSTOMER, 150, 177, fy]])
        if fy:
            q1 = cforms_analysis.execute(frappe._dict(filters, fiscal_year=fy, quarter="Q1"))[1]
            self.assertEqual(q1, [])


class TestCustomerRating(ReportTestCase):
    def test_territory_tree_and_group_filter(self):
        insert_territories()
        for name, territory in ((CUSTOMER, CHILD_TERRITORY), (OTHER_CUSTOMER, "_Test RIGPL Other Territory")):
            insert_customer(name)
            frappe.db.set_value("Customer", name, {"territory": territory, "customer_group": "All Customer Groups"},
                update_modified=False)

        customers = customer_rating.get_customers(frappe._dict(territory=TERRITORY, group="All Customer Groups"))

        self.assertEqual([cu.name for cu in customers], [CUSTOMER])


class TestCustomersWithSo(ReportTestCase):
    def test_totals_closed_order_and_last_order(self):
        insert_customer(CUSTOMER)
        raw("Sales Order", customer=CUSTOMER, transaction_date=DATE, docstatus=1, status="To Bill", base_net_total=100)
        raw("Sales Order", customer=CUSTOMER, transaction_date="2026-01-20", docstatus=1, status="Closed",
            base_net_total=200, per_delivered=50)

        data = customers_with_so.execute(frappe._dict(customer=CUSTOMER, from_date="2026-01-01",
            to_date="2026-01-31"))[1]

        self.assertEqual([row[:8] for row in data], [[CUSTOMER, None, 300, 200, 2, 100, getdate("2026-01-20"), 11]])


class TestFollowUpCustomer(ReportTestCase):
    def setUp(self):
        insert_customer(CUSTOMER)
        contact = raw("Contact", first_name="O'Brien")
        set_columns("Contact", contact, customer=CUSTOMER, mobile_no="98")
        raw("Sales Team", parent=CUSTOMER, parenttype="Customer", parentfield="sales_team", idx=1,
            sales_person="_Test RIGPL O'Person")
        self.old = raw("Communication", communication_type="Communication", reference_doctype="Customer",
            reference_name=CUSTOMER, communication_date="2026-01-10 10:00:00", content="old")
        self.timeline = raw("Communication", communication_type="Communication", communication_date="2026-01-20 10:00:00",
            content="timeline")
        set_columns("Communication", self.timeline, timeline_doctype="Customer", timeline_name=CUSTOMER)

    def test_summary_takes_the_later_timeline_communication(self):
        data = self.assert_queries(10, lambda: follow_up_customer.execute(
            frappe._dict(customer=CUSTOMER, from_date="2025-01-01"))[1])

        self.assertEqual(len(data), 1)
        row = data[0]
        self.assertIn("O&apos;Brien", row[1])
        self.assertEqual((row[2], getdate(row[9]), row[11]), ("98", getdate("2026-01-20"), "_Test RIGPL O'Person"))

    def test_hides_disabled_frozen_and_changed_business(self):
        for values in ({"disabled": 1}, {"is_frozen": 1}, {"customer_group": "Changed Business"}):
            frappe.db.set_value("Customer", CUSTOMER, values, update_modified=False)
            self.assertRaises(frappe.ValidationError, follow_up_customer.execute, frappe._dict(customer=CUSTOMER))
            frappe.db.set_value("Customer", CUSTOMER, {"disabled": 0, "is_frozen": 0, "customer_group": None},
                update_modified=False)

    def test_min_rating(self):
        frappe.db.set_value("Customer", CUSTOMER, "customer_rating", 40, update_modified=False)
        self.assertEqual(len(follow_up_customer.execute(frappe._dict(customer=CUSTOMER, min_rating=40))[1]), 1)
        self.assertRaises(frappe.ValidationError, follow_up_customer.execute,
            frappe._dict(customer=CUSTOMER, min_rating=41))

    def test_details(self):
        data = follow_up_customer.execute(frappe._dict(customer=CUSTOMER, details=1, from_date="2026-01-01"))[1]

        self.assertEqual([row[10] for row in data], [self.timeline, self.old])


class TestFollowUpLead(ReportTestCase):
    def test_latest_communication_and_days(self):
        raw("Lead", name=LEAD, lead_name=LEAD, company_name=LEAD, status="Open", lead_owner="O'Brien")
        for date in ("2026-01-10 10:00:00", "2026-01-20 10:00:00"):
            last = raw("Communication", communication_type="Communication", reference_doctype="Lead",
                reference_name=LEAD, communication_date=date, content=date)

        data = self.assert_queries(4, lambda: follow_up_lead.execute(frappe._dict(lead=LEAD, owner="O'Brien"))[1])

        days = (getdate(nowdate()) - getdate("2026-01-20")).days
        self.assertEqual([(row[0], row[5], row[8], row[12]) for row in data], [(LEAD, "Open", days, last)])

    def test_closed_lead_only_with_status_filter(self):
        raw("Lead", name=LEAD, lead_name=LEAD, company_name=LEAD, status="Lead Lost")

        self.assertEqual(follow_up_lead.execute(frappe._dict(lead=LEAD))[1], [])
        data = follow_up_lead.execute(frappe._dict(lead=LEAD, status="Lead Lost"))[1]
        self.assertEqual([row[0] for row in data], [LEAD])


def insert_priced_items():
    """2 Items of BM with d1_mm 6 and 3, and prices in the 3 price lists of PL."""
    for name, d1 in ((ITEM, "6"), (ITEM_2, "3")):
        insert_item(name, variant_of=TEMPLATE, attributes=[("Base Material", BM), ("Tool Type", "O'Drill"),
            ("d1_mm", d1)])
        frappe.db.set_value("Item", name, "pl_item", 1, update_modified=False)
    insert_item_price(ITEM, 100, PL[0])
    insert_item_price(ITEM, 110, PL[1])
    insert_item_price(ITEM_2, 50, PL[0])


class TestComparePricing(ReportTestCase):
    def test_prices_and_sort(self):
        insert_priced_items()
        filters = frappe._dict(bm=BM, tt="O'Drill", pl1=PL[0], pl2=PL[1], pl3=PL[2])

        data = self.assert_queries(5, lambda: compare_pricing.execute(filters)[1])

        self.assertEqual([row[0] for row in data], [ITEM_2, ITEM])
        self.assertEqual(data[1][1:7], [100, "INR", 110, "INR", 10, None])
        self.assertEqual((data[1][10], data[1][14], data[1][15]), (BM, "O'Drill", 6))


class TestVaSalesInvoice(ReportTestCase):
    def test_attributes(self):
        insert_item(ITEM, variant_of=TEMPLATE, attributes=[("Base Material", BM), ("d1_mm", "6")])
        insert_invoice(CUSTOMER, [(ITEM, 100)])

        data = self.assert_queries(2, lambda: va_sales_invoice.execute(frappe._dict(from_date=DATE, to_date=DATE))[1])

        row = next(row for row in data if row[3] == ITEM)
        self.assertEqual(row[9:14] + row[18:], [BM, "-", "-", "-", 6, "-"])


class TestPricingRules(ReportTestCase):
    def test_pricing_rules_for_items(self):
        rule = raw("Pricing Rule", apply_on="Item Code", valid_from="2026-01-01", valid_upto="2026-12-31", rate=5,
            min_qty=2)
        raw("Pricing Rule Item Code", parent=rule, parenttype="Pricing Rule", parentfield="items", item_code=ITEM)

        rules = self.assert_queries(1, lambda: get_pricing_rules_for_items([ITEM, ITEM_2], "2026-02-01", "2026-06-30"))

        self.assertEqual([(r.name, r.rate) for r in rules[ITEM]], [(rule, 5)])
        self.assertNotIn(ITEM_2, rules)
        self.assertEqual(get_pricing_rules_for_items([ITEM], to_dt="2027-01-01"), {})


class TestRigplPriceList(ReportTestCase):
    def setUp(self):
        for attribute, short_name, numeric in (("Base Material", "bm", 0), ("Tool Type", "tt", 0), ("d1_mm", "d1", 1)):
            if not frappe.db.exists("Item Attribute", attribute):
                raw("Item Attribute", name=attribute, attribute_name=attribute, short_name=short_name,
                    numeric_values=numeric)
        insert_item(TEMPLATE, attributes=[("Base Material", ""), ("Tool Type", ""), ("d1_mm", "")])
        insert_priced_items()
        raw("Price List", name=PL[0], price_list_name=PL[0], enabled=1, selling=1)
        self.filters = frappe._dict(pl=PL[0], bm=BM, tt="O'Drill", is_pl="Yes", template=TEMPLATE)

    def test_price_list(self):
        filters = frappe._dict(self.filters, price_list_type="Price List")
        columns, data = self.assert_queries(9, lambda: rigpl_price_list.execute(filters))

        self.assertEqual([row[4] for row in data], [ITEM_2, ITEM])
        self.assertEqual(data[1][2], 100)
        self.assertIn("d1_mm", [col.get("label") for col in columns if isinstance(col, dict)])

    def test_pricing_rule(self):
        rule = raw("Pricing Rule", apply_on="Item Code", valid_from="2026-01-01", valid_upto="2099-12-31", rate=7,
            min_qty=1)
        raw("Pricing Rule Item Code", parent=rule, parenttype="Pricing Rule", parentfield="items", item_code=ITEM)
        filters = frappe._dict(self.filters, price_list_type="Pricing Rule", valid_upto=nowdate(), show_zero=1)

        data = self.assert_queries(9, lambda: rigpl_price_list.execute(filters)[1])

        self.assertEqual([row[:6] for row in data], [[None] * 5 + [ITEM_2], [rule, getdate("2099-12-31"), 1, 7,
            None, ITEM]])
