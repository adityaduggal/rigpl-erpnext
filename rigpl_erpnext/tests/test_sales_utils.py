from types import SimpleNamespace

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.tests.test_check_update_bin_values import insert_bin, insert_doc, insert_stock_item
from rigpl_erpnext.utils.sales_utils import (
    check_get_pl_rates,
    check_strict_po_rules,
    copy_address_and_check,
    dead_stock_order_booking,
    get_completed_qty_of_jc_for_operation,
    get_contacts,
    get_email_from_contact,
    get_item_price,
    get_linked_so_data,
    get_pending_so_qty_from_soitem,
    get_phone_from_contact,
    get_sales_comm_for_cust,
    get_sales_comm_for_lead,
    get_sales_comms_for_customers,
    get_total_invoices_and_amount,
    get_total_sales_orders,
    validate_made_to_order_items,
)

# The quotes would break the old '%s' queries
CUSTOMER = "_Test RIGPL O'Brien Customer"
OTHER_CUSTOMER = "_Test RIGPL O'Brien Customer 2"
CONTACT = "_Test RIGPL O'Brien Contact"
OTHER_CONTACT = "_Test RIGPL O'Brien Contact 2"
LEAD = "_Test RIGPL O'Brien Lead"
ITEM = "_Test RIGPL O'Brien Item"
OPERATION = "_Test RIGPL O'Brien Operation"
SO_DETAIL = "_Test RIGPL O'Brien SOI"
PRICE_LIST = "_Test RIGPL O'Brien Price List"
FINISHED_WH = "_Test RIGPL O'Brien FS WH"
DEAD_WH = "_Test RIGPL O'Brien Dead WH"
SO_1 = "_Test RIGPL O'Brien SO 1"
SO_2 = "_Test RIGPL O'Brien SO 2"
ADDRESS = "_Test RIGPL O'Brien Address"


def insert_customer(name):
    frappe.get_doc(doctype="Customer", name=name, customer_name=name).db_insert()


def insert_contact(name, link_doctype=None, link_name=None, emails=(), phones=()):
    frappe.get_doc(doctype="Contact", name=name, first_name=name).db_insert()
    rows = [("Dynamic Link", "links", {"link_doctype": link_doctype, "link_name": link_name})] if link_name else []
    rows += [("Contact Email", "email_ids", {"email_id": email}) for email in emails]
    rows += [("Contact Phone", "phone_nos", {"phone": phone}) for phone in phones]
    for idx, (doctype, parentfield, values) in enumerate(rows, start=1):
        frappe.get_doc(doctype=doctype, name=frappe.generate_hash(length=10), parent=name,
            parenttype="Contact", parentfield=parentfield, idx=idx, **values).db_insert()


def insert_comm(ref_doctype, ref_name, date, subtype="Sales Related"):
    name = frappe.generate_hash(length=10)
    frappe.get_doc(doctype="Communication", name=name, communication_type="Communication",
        communication_medium="Phone", communication_subtype=subtype, reference_doctype=ref_doctype,
        reference_name=ref_name, communication_date=date, content=name).db_insert()
    return name


def insert_warehouse(name, warehouse_type):
    frappe.get_doc(doctype="Warehouse", name=name, warehouse_name=name, short_code=name[-4:],
        warehouse_type=warehouse_type, disabled=0).db_insert()


def insert_job_card(item_code, operation, so_detail, completed_qty, docstatus=1):
    frappe.get_doc(doctype="Process Job Card RIGPL", name=frappe.generate_hash(length=10),
        production_item=item_code, operation=operation, sales_order_item=so_detail,
        total_completed_qty=completed_qty, docstatus=docstatus).db_insert()


def row(**values):
    return frappe._dict(dict(idx=1, qty=1), **values)


class TestContactsAndComms(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_contact_emails_phones_and_links(self):
        insert_customer(CUSTOMER)
        insert_contact(CONTACT, "Customer", CUSTOMER, emails=["a@x.com", "b@x.com"], phones=["98", "99"])

        self.assertEqual([r.email_id for r in get_email_from_contact(CONTACT)], ["a@x.com", "b@x.com"])
        self.assertEqual([r.phone for r in get_phone_from_contact(CONTACT)], ["98", "99"])
        self.assertEqual([r.name for r in get_contacts(name=CUSTOMER, type="Customer")], [CONTACT])
        self.assertFalse(get_email_from_contact(None))
        self.assertFalse(get_phone_from_contact(None))

    def test_customer_comms_own_first_then_contacts_latest_first(self):
        insert_customer(CUSTOMER)
        insert_contact(CONTACT, "Customer", CUSTOMER)
        insert_contact(OTHER_CONTACT, "Customer", CUSTOMER)
        own = insert_comm("Customer", CUSTOMER, "2026-01-05 10:00:00")
        older = insert_comm("Contact", CONTACT, "2026-01-02 10:00:00")
        newer = insert_comm("Contact", OTHER_CONTACT, "2026-01-08 10:00:00")
        insert_comm("Customer", CUSTOMER, "2026-01-06 10:00:00", subtype="Other")

        comms = get_sales_comm_for_cust(CUSTOMER)

        self.assertEqual([c.name for c in comms], [own, newer, older])
        self.assertEqual({c.contacts for c in comms}, {3})

    def test_to_date_takes_the_full_last_day(self):
        insert_customer(CUSTOMER)
        before = insert_comm("Customer", CUSTOMER, "2026-01-01 09:00:00")
        last_day = insert_comm("Customer", CUSTOMER, "2026-01-31 18:00:00")
        insert_comm("Customer", CUSTOMER, "2026-02-01 00:00:00")

        comms = get_sales_comm_for_cust(CUSTOMER, frm_date="2026-01-01", to_date="2026-01-31")

        self.assertEqual([c.name for c in comms], [last_day, before])

    def test_lead_comms_count_all_lead_comms(self):
        sales = insert_comm("Lead", LEAD, "2026-01-05 10:00:00")
        insert_comm("Lead", LEAD, "2026-01-06 10:00:00", subtype="Other")

        comms = get_sales_comm_for_lead(LEAD)

        self.assertEqual([c.name for c in comms], [sales])
        self.assertEqual(comms[0].contacts, 2)

    def test_customer_comms_read_in_fixed_queries(self):
        for customer, contact in ((CUSTOMER, CONTACT), (OTHER_CUSTOMER, OTHER_CONTACT)):
            insert_customer(customer)
            insert_contact(contact, "Customer", customer)
            insert_comm("Contact", contact, "2026-01-05 10:00:00")

        with assert_max_queries(2, test_case=self):
            comms = get_sales_comms_for_customers([CUSTOMER, OTHER_CUSTOMER])

        self.assertEqual([len(comms[CUSTOMER]), len(comms[OTHER_CUSTOMER])], [1, 1])


class TestOrderQueries(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_totals_keep_one_row_shape(self):
        insert_doc("Sales Order", "Sales Order Item", "items", {"customer": CUSTOMER,
            "transaction_date": "2026-01-10", "base_net_total": 500, "status": "To Deliver and Bill"}, [])

        self.assertEqual(get_total_sales_orders(CUSTOMER, "2026-01-01", "2026-01-31")[0].total_net_amt, 500)
        self.assertEqual(get_total_sales_orders(CUSTOMER, "2026-02-01", "2026-02-28"),
            [{"total_net_amt": None, "so": 0}])
        self.assertEqual(get_total_invoices_and_amount(CUSTOMER, "2026-01-01", "2026-01-31"),
            [{"total_net_amt": None, "invoices": 0}])

    def test_pending_so_qty(self):
        insert_doc("Sales Order", "Sales Order Item", "items", {"status": "To Deliver and Bill"}, [{
            "item_code": ITEM, "qty": 10, "delivered_qty": 4}])
        so_item = frappe.get_all("Sales Order Item", filters={"item_code": ITEM}, pluck="name")[0]

        self.assertEqual(get_pending_so_qty_from_soitem(so_item), 6)
        self.assertEqual(get_pending_so_qty_from_soitem(SO_DETAIL), 0)

    def test_completed_qty_of_job_cards(self):
        insert_job_card(ITEM, OPERATION, SO_DETAIL, 3)
        insert_job_card(ITEM, OPERATION, SO_DETAIL, 4)
        insert_job_card(ITEM, OPERATION, SO_DETAIL, 50, docstatus=0)

        self.assertEqual(get_completed_qty_of_jc_for_operation(ITEM, OPERATION, SO_DETAIL), 7)
        self.assertEqual(get_completed_qty_of_jc_for_operation(ITEM, OPERATION), 0)


class TestSalesValidations(FrappeTestCase):
    def setUp(self):
        insert_stock_item(ITEM)
        insert_warehouse(FINISHED_WH, "Finished Stock")
        insert_warehouse(DEAD_WH, "Dead Stock")

    def tearDown(self):
        frappe.db.rollback()

    def test_dead_stock_booking_limited_to_free_qty(self):
        insert_bin(ITEM, DEAD_WH, actual_qty=5)
        insert_bin(ITEM, FINISHED_WH, actual_qty=3, reserved_qty=2)
        doc = SimpleNamespace(items=[row(item_code=ITEM, qty=6)])

        with assert_max_queries(1, test_case=self):
            dead_stock_order_booking(doc)
        doc.items[0].qty = 7
        self.assertRaises(frappe.ValidationError, dead_stock_order_booking, doc)

    def made_to_order_doc(self, qty):
        frappe.db.set_value("Item", ITEM, "made_to_order", 1, update_modified=False)
        return SimpleNamespace(doctype="Delivery Note", name="_Test RIGPL DN", bypass_made_to_order_check=0,
            items=[row(item_code=ITEM, so_detail=SO_DETAIL, qty=qty, warehouse=FINISHED_WH)])

    def test_made_to_order_needs_process_sheet(self):
        self.assertRaisesRegex(frappe.ValidationError, "No Processing Done",
            validate_made_to_order_items, self.made_to_order_doc(1))

    def test_made_to_order_qty_limited_to_final_job_cards(self):
        insert_doc("Process Sheet", "BOM Operation", "operations", {"production_item": ITEM,
            "sales_order_item": SO_DETAIL, "status": "Completed"}, [{"operation": OPERATION, "final_operation": 1}])
        insert_job_card(ITEM, OPERATION, SO_DETAIL, 5)

        validate_made_to_order_items(self.made_to_order_doc(5))
        self.assertRaisesRegex(frappe.ValidationError, "Only allowed to Submit Qty= 5",
            validate_made_to_order_items, self.made_to_order_doc(6))

    def test_item_price_and_quotation_rates(self):
        frappe.get_doc(doctype="Price List", name=PRICE_LIST, price_list_name=PRICE_LIST, currency="INR",
            selling=1, enabled=1, disable_so=0).db_insert()
        frappe.get_doc(doctype="Item Price", name=frappe.generate_hash(length=10), item_code=ITEM,
            price_list=PRICE_LIST, price_list_rate=120, currency="INR", selling=1).db_insert()
        doc = SimpleNamespace(doctype="Quotation", name="_Test RIGPL QTN", currency="INR")
        quote_row = row(item_code=ITEM, price_list=PRICE_LIST, price_list_rate=100)

        self.assertEqual(get_item_price(ITEM, PRICE_LIST), 120)
        self.assertFalse(get_item_price(ITEM, "_Test RIGPL No Price List"))
        with assert_max_queries(2, test_case=self):
            check_get_pl_rates(doc, [quote_row])
        self.assertEqual(quote_row.price_list_rate, 120)

        frappe.db.set_value("Price List", PRICE_LIST, "disable_so", 1, update_modified=False)
        self.assertRaisesRegex(frappe.ValidationError, "Sales Order Booking Disabled",
            check_get_pl_rates, doc, [quote_row])


def insert_sales_order(name, strict=0, address=ADDRESS):
    frappe.get_doc(doctype="Sales Order", name=name, customer=CUSTOMER, docstatus=1, follow_strict_po_rules=strict,
        customer_address=address, shipping_address_name=address).db_insert()


class TestDeliveryNoteSoChecks(FrappeTestCase):
    def setUp(self):
        insert_customer(CUSTOMER)
        frappe.clear_document_cache("Customer", CUSTOMER)
        insert_stock_item(ITEM)
        insert_warehouse(FINISHED_WH, "Finished Stock")
        insert_warehouse(DEAD_WH, "Dead Stock")
        insert_sales_order(SO_1)
        insert_sales_order(SO_2)

    def tearDown(self):
        frappe.db.rollback()
        frappe.clear_document_cache("Customer", CUSTOMER)

    def dn(self, sales_orders, warehouse=FINISHED_WH):
        return SimpleNamespace(doctype="Delivery Note", name="_Test RIGPL DN", customer=CUSTOMER,
            customer_address=ADDRESS, shipping_address_name=ADDRESS, bypass_made_to_order_check=0,
            items=[row(idx=idx, item_code=ITEM, warehouse=warehouse, against_sales_order=so)
                for idx, so in enumerate(sales_orders, start=1)])

    def check(self, doc):
        so_data = get_linked_so_data(doc)
        check_strict_po_rules(doc, so_data)
        copy_address_and_check(doc, so_data)

    def test_two_sales_orders_pass_without_strict_rules(self):
        self.check(self.dn([SO_1, SO_2]))

    def test_strict_customer_allows_one_sales_order(self):
        frappe.db.set_value("Customer", CUSTOMER, "follow_strict_po_rules", 1, update_modified=False)
        frappe.clear_document_cache("Customer", CUSTOMER)
        self.check(self.dn([SO_1, SO_1]))
        self.assertRaisesRegex(frappe.ValidationError, "Row 2 is Rejected", self.check, self.dn([SO_1, SO_2]))

    def test_strict_sales_order_on_a_later_row(self):
        frappe.db.set_value("Sales Order", SO_2, "follow_strict_po_rules", 1, update_modified=False)
        self.assertRaisesRegex(frappe.ValidationError, "Row 3 is Rejected", self.check,
            self.dn([SO_1, SO_1, SO_2]))

    def test_strict_rule_when_row_one_has_no_sales_order(self):
        frappe.db.set_value("Sales Order", SO_1, "follow_strict_po_rules", 1, update_modified=False)
        self.check(self.dn([None, SO_1, SO_1]))
        self.assertRaisesRegex(frappe.ValidationError, "Row 3 is Rejected", self.check,
            self.dn([None, SO_1, SO_2]))

    def test_address_must_match_the_sales_order(self):
        doc = self.dn([SO_1, SO_2])
        doc.shipping_address_name = "_Test RIGPL Other Address"
        self.assertRaisesRegex(frappe.ValidationError, "Shipping Address mentioned", self.check, doc)

    def test_other_doctype_is_refused(self):
        doc = self.dn([SO_1])
        doc.doctype = "Quotation"
        self.assertRaisesRegex(frappe.ValidationError, "not for Quotation", self.check, doc)

    def test_warehouse_must_be_finished_stock(self):
        self.assertRaisesRegex(frappe.ValidationError, "Not Finished Stock Warehouse",
            validate_made_to_order_items, self.dn([SO_1], warehouse=DEAD_WH))

    def test_query_count_does_not_depend_on_rows(self):
        # The first calls load the Sales Order, Item and Warehouse meta into the cache
        self.check(self.dn([SO_1]))
        validate_made_to_order_items(self.dn([SO_1]))
        for sales_orders in ([SO_1], [SO_1, SO_2, SO_1, SO_2]):
            doc = self.dn(sales_orders)
            with assert_max_queries(2, test_case=self):
                self.check(doc)
            with assert_max_queries(2, test_case=self):
                validate_made_to_order_items(doc)
