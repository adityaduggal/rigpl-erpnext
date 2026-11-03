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
from rigpl_erpnext.rigpl_erpnext.report.customer_rating import customer_rating
from rigpl_erpnext.rigpl_erpnext.report.customers_with_so import customers_with_so
from rigpl_erpnext.rigpl_erpnext.report.forex_transactions import forex_transactions
from rigpl_erpnext.rigpl_erpnext.report.tod_sales_invoice import tod_sales_invoice
from rigpl_erpnext.rigpl_erpnext.report.todo_report import todo_report
from rigpl_erpnext.rigpl_erpnext.report.trial_tracking import trial_tracking
from rigpl_erpnext.tests.test_sales_utils import insert_customer
from rigpl_erpnext.tests.test_variant_table import insert_item, insert_item_price
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
