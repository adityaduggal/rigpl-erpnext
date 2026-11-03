"""
Selling and CRM reports after the move from '%s' SQL to frappe.qb (#187). Each name has a quote:
the old reports put it into the SQL text and failed.
"""
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.report.todo_report import todo_report
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
