from unittest.mock import patch

import frappe
from erpnext.crm.doctype.lead.lead import Lead
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.utils.lead_share_utils import get_changes, sync_lead_shares

REP = "_test_rigpl_lead_share_rep@example.com"
REP2 = "_test_rigpl_lead_share_rep2@example.com"
SYS = "_test_rigpl_lead_share_sys@example.com"


def share(name, user, dt="Lead", dn="L-1"):
    return frappe._dict(name=name, user=user, share_doctype=dt, share_name=dn)


def make_user(email, first_name, mobile_no, roles):
    if not frappe.db.exists("User", email):
        # mobile_no is mandatory on this site (Property Setter) and unique. The first name names
        # the Contact that User.on_update makes, so it must be unique too. The roles go in the
        # insert: a second save (add_roles) makes the Contact again and fails.
        frappe.get_doc({"doctype": "User", "email": email, "first_name": first_name, "mobile_no": mobile_no,
            "send_welcome_email": 0, "roles": [{"role": role} for role in roles]}).insert(ignore_permissions=True)


def make_lead(lead_owner):
    lead = frappe.get_doc({"doctype": "Lead", "lead_name": "_Test RIGPL Lead Share",
        "company_name": "_Test RIGPL Lead Share Co", "email_id": "_test_rigpl_lead_share_lead@example.com",
        "lead_owner": lead_owner})
    lead.flags.ignore_mandatory = True
    # ERPNext makes a Contact before the Lead exists, and rohit_common rejects a Contact
    # without links. The share tests do not need it.
    with patch.object(Lead, "before_insert", lambda self: None), \
            patch.object(Lead, "after_insert", lambda self: None):
        return lead.insert(ignore_permissions=True)


def shared_users(dn, dt="Lead"):
    return sorted(frappe.get_all("DocShare", filters={"share_doctype": dt, "share_name": dn}, pluck="user"))


class TestGetChanges(FrappeTestCase):
    def test_adds_missing_lead_owner_share(self):
        self.assertEqual(get_changes({("Lead", "L-1"): REP}, []), ([("Lead", "L-1")], []))

    def test_removes_other_shares_on_wanted_document(self):
        to_add, to_remove = get_changes({("Lead", "L-1"): REP},
            [share("DS-1", REP), share("DS-2", REP2), share("DS-3", None)])
        self.assertEqual((to_add, to_remove), ([], ["DS-2", "DS-3"]))

    def test_leaves_documents_that_are_not_wanted(self):
        self.assertEqual(get_changes({}, [share("DS-1", REP2)]), ([], []))

    def test_no_change_when_shares_are_correct(self):
        wanted = {("Lead", "L-1"): REP, ("Quotation", "Q-1"): REP}
        existing = [share("DS-1", REP), share("DS-2", REP, "Quotation", "Q-1")]
        self.assertEqual(get_changes(wanted, existing), ([], []))


class TestSyncLeadShares(FrappeTestCase):
    """Uses the Sales Representative rules in User Share Settings of the site."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_user(REP, "_Test RIGPL Lead Share Rep", "+91-0000000160", ["Sales Representative"])
        make_user(REP2, "_Test RIGPL Lead Share Rep Two", "+91-0000000161", ["Sales Representative"])
        make_user(SYS, "_Test RIGPL Lead Share Sys", "+91-0000000162", ["Sales Representative", "System Manager"])

    def tearDown(self):
        frappe.db.rollback()

    def test_lead_made_for_rep_is_shared_with_rep(self):
        lead = make_lead(REP)
        self.assertEqual(shared_users(lead.name), [REP])

    def test_new_lead_owner_replaces_old_share(self):
        lead = make_lead(REP)
        lead.lead_owner = REP2
        lead.save(ignore_permissions=True)
        self.assertEqual(shared_users(lead.name), [REP2])

    def test_system_manager_lead_owner_gets_no_share(self):
        lead = make_lead(SYS)
        self.assertEqual(shared_users(lead.name), [])

    def test_sync_runs_a_fixed_number_of_queries(self):
        lead = make_lead(REP)
        with assert_max_queries(8, test_case=self):
            to_add, to_remove = sync_lead_shares([lead.name])
        self.assertEqual((to_add, to_remove), ([], []))
