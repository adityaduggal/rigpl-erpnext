# -*- coding: utf-8 -*-
# Copyright (c) 2018, Rohit Industries Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.tests.test_selling_reports import raw

USER = "_test_rigpl_dcr@example.com"
OTHER = "_test_rigpl_dcr_other@example.com"
LEADS = ["_Test RIGPL DCR Lead {}".format(i) for i in range(6)]
CUSTOMER = "_Test RIGPL DCR Customer"
CONTACT = "_Test RIGPL DCR Contact"


def insert_masters():
	for user in (USER, OTHER):
		raw("User", name=user, email=user, first_name=user, enabled=1)
	for lead in LEADS:
		frappe.get_doc(doctype="Lead", name=lead, lead_name=lead, company_name=lead, status="Open").db_insert()
	raw("Customer", name=CUSTOMER, customer_name=CUSTOMER)
	raw("Contact", name=CONTACT, first_name=CONTACT)
	raw("Dynamic Link", parent=CONTACT, parenttype="Contact", parentfield="links", link_doctype="Customer",
		link_name=CUSTOMER)


def call_row(document, name, next_action=False):
	return {"document": document, "document_name": name, "type_of_communication": "Phone", "duration": 5,
		"communication_date": now_datetime(), "details": "Discussed the quotation for " + name,
		"next_action_date": add_to_date(now_datetime(), days=2) if next_action else None}


def make_dcr(rows, submit=True):
	dcr = frappe.get_doc({"doctype": "Daily Call", "created_by": USER, "next_action_by": USER,
		"call_details": rows})
	dcr.insert()
	if submit:
		dcr.submit()
	return dcr


def make_follow_up(reference_doctype, reference_name, user=OTHER):
	comm = frappe.get_doc({"doctype": "Communication", "communication_type": "Communication",
		"communication_medium": "Phone", "communication_subtype": "Sales Related", "subject": "_Test RIGPL DCR",
		"content": "Call back", "reference_doctype": reference_doctype, "reference_name": reference_name,
		"user": user, "follow_up": 1, "next_action_date": add_to_date(now_datetime(), days=3)})
	comm.insert(ignore_permissions=True)
	todo = raw("ToDo", owner=user, status="Open", description="_Test RIGPL DCR", reference_type="Communication",
		reference_name=comm.name)
	return comm.name, todo


class TestDailyCall(FrappeTestCase):
	def setUp(self):
		insert_masters()

	def tearDown(self):
		frappe.db.rollback()

	def test_calls_point_to_the_party_and_follow_up_only_with_a_date(self):
		dcr = make_dcr([call_row("Lead", LEADS[0], next_action=True), call_row("Lead", LEADS[1]),
			call_row("Customer", CUSTOMER)])

		comms = [frappe.get_doc("Communication", row.communication) for row in dcr.call_details]
		self.assertEqual([(c.reference_doctype, c.reference_name) for c in comms],
			[("Lead", LEADS[0]), ("Lead", LEADS[1]), ("Customer", CUSTOMER)])
		self.assertEqual([c.follow_up for c in comms], [1, 0, 0])
		self.assertEqual([(l.link_doctype, l.link_name) for l in comms[2].timeline_links], [("Contact", CONTACT)])
		self.assertEqual(dcr.call_details[2].contact, CONTACT)
		self.assertEqual(frappe.db.get_value("Daily Call Details", dcr.call_details[0].name, "communication"),
			comms[0].name)

	def test_new_call_ends_older_follow_ups_of_all_users_due_or_not(self):
		lead_comm, lead_todo = make_follow_up("Lead", LEADS[0])
		contact_comm, contact_todo = make_follow_up("Contact", CONTACT)

		dcr = make_dcr([call_row("Lead", LEADS[0], next_action=True), call_row("Customer", CUSTOMER)])

		self.assertEqual([frappe.db.get_value("Communication", c, "follow_up") for c in (lead_comm, contact_comm)],
			[0, 0])
		self.assertEqual([frappe.db.get_value("ToDo", t, "status") for t in (lead_todo, contact_todo)],
			["Closed", "Closed"])
		self.assertEqual(frappe.db.get_value("Communication", dcr.call_details[0].communication, "follow_up"), 1)

	def test_cancel_deletes_the_calls_and_their_todos(self):
		dcr = make_dcr([call_row("Lead", LEADS[0], next_action=True)])
		comm = dcr.call_details[0].communication
		todo = raw("ToDo", owner=USER, status="Open", description="_Test RIGPL DCR", reference_type="Communication",
			reference_name=comm)

		dcr.cancel()

		self.assertFalse(frappe.db.exists("Communication", comm))
		self.assertFalse(frappe.db.exists("ToDo", todo))
		self.assertIsNone(frappe.db.get_value("Daily Call Details", dcr.call_details[0].name, "communication"))

	def test_customer_with_many_contacts_needs_a_contact(self):
		raw("Contact", name=CONTACT + " 2", first_name=CONTACT + " 2")
		raw("Dynamic Link", parent=CONTACT + " 2", parenttype="Contact", parentfield="links",
			link_doctype="Customer", link_name=CUSTOMER)
		with self.assertRaises(frappe.ValidationError):
			make_dcr([call_row("Customer", CUSTOMER)], submit=False)

	def test_validate_runs_the_same_queries_for_more_rows(self):
		counts = []
		for size in (2, 6):
			dcr = frappe.get_doc({"doctype": "Daily Call", "created_by": USER, "next_action_by": USER,
				"call_details": [call_row("Lead", lead) for lead in LEADS[:size - 1]] + [call_row("Customer", CUSTOMER)]})
			with assert_max_queries(10, test_case=self) as guard:
				dcr.validate()
			counts.append(guard.count)
		self.assertEqual(counts[0], counts[1])
