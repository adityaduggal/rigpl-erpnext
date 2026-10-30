import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.report.dcr_analysis_rigpl.dcr_analysis_rigpl import execute
from rigpl_erpnext.tests.test_sales_utils import insert_comm, insert_contact, insert_customer

# The quotes would break the old '%s' filters
TERRITORY = "_Test RIGPL O'Brien Territory"
CUSTOMER = "_Test RIGPL O'Brien DCR Customer"
OTHER_CUSTOMER = "_Test RIGPL O'Brien DCR Customer 2"
CONTACT = "_Test RIGPL O'Brien DCR Contact"
LEAD = "_Test RIGPL O'Brien DCR Lead"
DATES = {"from_date": "2026-01-01", "to_date": "2026-01-31"}


def insert_sales_team(customer, email_id):
    frappe.get_doc(doctype="Sales Team", name=frappe.generate_hash(length=10), parent=customer,
        parenttype="Customer", parentfield="sales_team", idx=1, email_id=email_id).db_insert()


def run(**filters):
    return execute(frappe._dict(DATES, **filters))[1]


class TestDcrAnalysis(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def make_customer(self, name, territory, contact=None):
        insert_customer(name)
        frappe.db.set_value("Customer", name, {"territory": territory, "customer_primary_contact": contact},
            update_modified=False)
        insert_sales_team(name, "_test_rigpl@example.com")

    def test_customer_summary_by_territory_in_fixed_queries(self):
        self.make_customer(CUSTOMER, TERRITORY, CONTACT)
        self.make_customer(OTHER_CUSTOMER, "_Test RIGPL Other Territory")
        insert_contact(CONTACT, "Customer", CUSTOMER, emails=["a@x.com"], phones=["98"])
        insert_comm("Contact", CONTACT, "2026-01-20 10:00:00")

        # customers, phones, emails, Sales Order totals, contacts and comms
        with assert_max_queries(6, test_case=self):
            data = run(comm_summary=1, document="Customer", territory=TERRITORY)

        self.assertEqual([(r[0], r[5], r[6], r[9]) for r in data], [(CUSTOMER, "98 ", "a@x.com ", 1)])

    def test_lead_details_by_name(self):
        comm = insert_comm("Lead", LEAD, "2026-01-31 18:00:00")
        frappe.get_doc(doctype="Lead", name=LEAD, lead_name=LEAD, company_name=LEAD).db_insert()

        data = run(comm_details=1, document="Lead", docname=LEAD)

        self.assertEqual([(r[0], r[9]) for r in data], [(LEAD, comm)])

    def test_analysis_summary_takes_the_full_last_day(self):
        dcr = frappe.generate_hash(length=10)
        frappe.get_doc(doctype="Daily Call", name=dcr, docstatus=1, created_by="_test_rigpl@example.com").db_insert()
        frappe.get_doc(doctype="Daily Call Details", name=frappe.generate_hash(length=10), parent=dcr,
            parenttype="Daily Call", parentfield="call_details", idx=1, docstatus=1, document="Lead",
            document_name=LEAD, type_of_communication="Phone", duration=5,
            communication_date="2026-01-31 18:00:00").db_insert()

        data = run(analysis_summary=1, document="Lead", docname=LEAD)

        created_by = frappe.db.get_value("Daily Call", dcr, "created_by")
        self.assertEqual([list(r) for r in data], [[created_by, "Phone", 1, 5]])
