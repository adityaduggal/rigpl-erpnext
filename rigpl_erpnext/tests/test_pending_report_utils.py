import frappe
from frappe.query_builder import Order
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.report.dn_to_be_billed.dn_to_be_billed import get_dn_entries
from rigpl_erpnext.tests.test_check_update_bin_values import insert_stock_item
from rigpl_erpnext.utils.pending_report_utils import get_pending_rows

# The quotes would break the old '%s' queries
CUSTOMER = "_Test RIGPL O'Brien Pending Customer"
SUPPLIER = "_Test RIGPL O'Brien Pending Supplier"
ITEM = "_Test RIGPL O'Brien Pending Item"
OTHER_ITEM = "_Test RIGPL O'Brien Pending Item 2"
TERRITORY = "_Test RIGPL O'Brien Territory"
CHILD_TERRITORY = "_Test RIGPL O'Brien Child Territory"


def insert_parent(doctype, rows, docstatus=1, **values):
    name = frappe.generate_hash(length=10)
    frappe.get_doc(doctype=doctype, name=name, docstatus=docstatus, **values).db_insert()
    for idx, row in enumerate(rows, start=1):
        row = dict({"item_code": ITEM, "description": ITEM}, **row)
        frappe.get_doc(doctype=doctype + " Item", name=frappe.generate_hash(length=10), parent=name,
            parenttype=doctype, parentfield="items", idx=idx, docstatus=docstatus, **row).db_insert()
    return name


def row_names(doctype, parent):
    return frappe.get_all(doctype + " Item", filters={"parent": parent}, pluck="name", order_by="idx")


def insert_sales_order(rows, status="To Deliver and Bill", date="2026-01-10", customer=CUSTOMER):
    return insert_parent("Sales Order", rows, status=status, transaction_date=date, customer=customer)


def insert_delivery_note(qty=10, rate=100, date="2026-01-10"):
    return insert_parent("Delivery Note", [{"qty": qty, "base_rate": rate, "base_amount": qty * rate}],
        status="To Bill", posting_date=date, customer=CUSTOMER)


def insert_invoice(doctype, link_field, detail_field, parent, detail, qty, rate=100, docstatus=1,
        date="2026-01-15"):
    party = {"customer": CUSTOMER} if doctype == "Sales Invoice" else {"supplier": SUPPLIER}
    insert_parent(doctype, [{link_field: parent, detail_field: detail, "qty": qty, "base_amount": qty * rate}],
        docstatus=docstatus, posting_date=date, **party)


def pending(flow, filters, **kwargs):
    return [(row.item_code, row.pending_qty) for row in get_pending_rows(flow, filters, **kwargs)]


class TestPendingRows(FrappeTestCase):
    def setUp(self):
        insert_stock_item(ITEM)
        insert_stock_item(OTHER_ITEM)
        frappe.get_doc(doctype="Customer", name=CUSTOMER, customer_name=CUSTOMER).db_insert()

    def tearDown(self):
        frappe.db.rollback()

    def test_sales_order_rows_pending_delivery(self):
        insert_sales_order([{"qty": 10, "delivered_qty": 4}, {"qty": 5, "delivered_qty": 5}])
        insert_sales_order([{"qty": 3}], status="Closed")
        insert_sales_order([{"qty": 2, "item_code": OTHER_ITEM}], date="2026-02-10")

        self.assertEqual(pending("so_delivery", {"customer": CUSTOMER}, order=Order.desc),
            [(OTHER_ITEM, 2), (ITEM, 6)])
        self.assertEqual(pending("so_delivery", {"customer": CUSTOMER, "to_date": "2026-01-31"}), [(ITEM, 6)])
        self.assertEqual(pending("so_delivery", {"customer": CUSTOMER, "item": OTHER_ITEM}), [(OTHER_ITEM, 2)])

    def test_made_to_order_and_base_material_filters(self):
        frappe.db.set_value("Item", OTHER_ITEM, "made_to_order", 1, update_modified=False)
        frappe.get_doc(doctype="Item Variant Attribute", name=frappe.generate_hash(length=10), parent=ITEM,
            parenttype="Item", parentfield="attributes", attribute="Base Material",
            attribute_value="HSS").db_insert()
        insert_sales_order([{"qty": 1}, {"qty": 2, "item_code": OTHER_ITEM}])

        self.assertEqual(pending("so_delivery", {"customer": CUSTOMER, "made_to_order": 1}), [(OTHER_ITEM, 2)])
        self.assertEqual(pending("so_delivery", {"customer": CUSTOMER, "made_to_order": 0}), [(ITEM, 1)])
        self.assertEqual(pending("so_delivery", {"customer": CUSTOMER, "bm": "HSS"}), [(ITEM, 1)])

    def test_territory_includes_child_territories(self):
        for name, parent in ((TERRITORY, "All Territories"), (CHILD_TERRITORY, TERRITORY)):
            frappe.get_doc(doctype="Territory", territory_name=name, parent_territory=parent,
                is_group=1).insert(ignore_permissions=True)
        frappe.db.set_value("Customer", CUSTOMER, "territory", CHILD_TERRITORY, update_modified=False)
        insert_delivery_note()

        self.assertEqual(pending("dn_billing", {"territory": TERRITORY}), [(ITEM, 10)])
        self.assertEqual(pending("dn_billing", {"customer": CUSTOMER, "territory": "_Test RIGPL No Territory"}), [])

    def test_delivery_note_rows_not_billed(self):
        dn = insert_delivery_note()
        detail = row_names("Delivery Note", dn)[0]
        insert_invoice("Sales Invoice", "delivery_note", "dn_detail", dn, detail, 4)
        insert_invoice("Sales Invoice", "delivery_note", "dn_detail", dn, detail, 3, docstatus=0)
        insert_invoice("Sales Invoice", "delivery_note", "dn_detail", dn, detail, 2, date="2026-03-01")

        self.assertEqual(pending("dn_billing", {"customer": CUSTOMER, "to_date": "2026-01-31"}), [(ITEM, 6)])
        self.assertEqual(pending("dn_billing", {"customer": CUSTOMER, "to_date": "2026-01-31", "draft": 1}),
            [(ITEM, 3)])
        self.assertEqual(pending("dn_billing", {"customer": CUSTOMER}), [(ITEM, 4)])

    def test_purchase_receipt_rows_not_billed(self):
        pr = insert_parent("Purchase Receipt", [{"qty": 10, "base_rate": 100, "base_amount": 1000}],
            status="To Bill", posting_date="2026-01-10", supplier=SUPPLIER)
        insert_invoice("Purchase Invoice", "purchase_receipt", "pr_detail", pr, row_names("Purchase Receipt", pr)[0], 4)

        rows = get_pending_rows("pr_billing", {"supplier": SUPPLIER})
        self.assertEqual([(row.pending_qty, row.pending_amount) for row in rows], [(6, 600)])

    def test_dn_summary_groups_by_customer(self):
        insert_delivery_note(qty=2, date="2026-01-12")
        insert_delivery_note(qty=3, date="2026-01-11")

        summary = get_dn_entries(frappe._dict(customer=CUSTOMER, summary=1))
        self.assertEqual([row[0] for row in summary], [CUSTOMER])
        self.assertEqual(summary[0][3:], [2, 2, frappe.utils.getdate("2026-01-11"), 5, 500])

    def test_query_count_does_not_depend_on_rows(self):
        for count in (1, 5):
            frappe.db.rollback()
            self.setUp()
            dns = [insert_delivery_note() for _ in range(count)]
            for dn in dns:
                insert_invoice("Sales Invoice", "delivery_note", "dn_detail", dn, row_names("Delivery Note", dn)[0], 1)
            insert_sales_order([{"qty": 2}] * count)
            with assert_max_queries(1, test_case=self):
                self.assertEqual(len(get_pending_rows("dn_billing", {"customer": CUSTOMER})), count)
            with assert_max_queries(1, test_case=self):
                self.assertEqual(len(get_pending_rows("so_delivery", {"customer": CUSTOMER})), count)
