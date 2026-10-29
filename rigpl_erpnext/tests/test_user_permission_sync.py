from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.scheduled_tasks import user_permission_sync as ups

USER = "_test_rigpl_ups@example.com"
OTHER = "_test_rigpl_ups_other@example.com"


def d(**kwargs):
    return frappe._dict(kwargs)


def rule(allow, value=None, role=None, all_roles=0, applicable_for=None, all_doctypes=1):
    return d(role=role, apply_to_all_roles=all_roles, allow_doctype=allow, allow_doctype_value=value,
        apply_to_all_values=0 if value else 1, applicable_for_doctype=applicable_for,
        apply_to_all_doctypes=all_doctypes)


def perm(name, user, allow, value, applicable_for=None, all_doctypes=1):
    return d(name=name, user=user, allow=allow, for_value=value, applicable_for=applicable_for,
        apply_to_all_doctypes=all_doctypes)


def ctx(rules=(), perms=(), roles=None, enabled=(USER,), employees=(), approvers=None):
    return d(enabled=set(enabled), roles=roles or {USER: {"Accounts User"}}, rules=list(rules),
        perms=list(perms), employees=list(employees), approvers=approvers or {})


def keys(perms):
    return [p.name for p in perms]


class TestGetChanges(FrappeTestCase):
    def test_role_value_rule_adds_permission(self):
        to_insert, to_delete = ups.get_changes(ctx([
            rule("Employment Type", "Accounts Employee", role="Accounts User"),
            rule("Issue Type", "Quality Issues", role="Production User"),
        ]))
        self.assertEqual(to_insert, [(USER, "Employment Type", "Accounts Employee", "", 1)])
        self.assertEqual(to_delete, [])

    def test_all_roles_rule_adds_permission_for_each_user(self):
        to_insert, _ = ups.get_changes(ctx([rule("Company", "RIGPL", all_roles=1)],
            roles={USER: {"Accounts User"}, OTHER: set()}, enabled=(USER, OTHER)))
        self.assertEqual(sorted(key[0] for key in to_insert), [OTHER, USER])

    def test_rule_permission_without_all_values_rule_is_kept(self):
        # The old daily job deleted it and the hourly job added it again
        to_insert, to_delete = ups.get_changes(ctx(
            [rule("Employment Type", "Accounts Employee", role="Accounts User")],
            [perm("UP-1", USER, "Employment Type", "Accounts Employee")],
        ))
        self.assertEqual((to_insert, to_delete), ([], []))

    def test_permission_without_rule_or_role_is_deleted(self):
        _, to_delete = ups.get_changes(ctx(perms=[perm("UP-1", USER, "Issue Type", "Quality Issues")]))
        self.assertEqual(keys(to_delete), ["UP-1"])

    def test_system_manager_and_disabled_users_lose_all_permissions(self):
        to_insert, to_delete = ups.get_changes(ctx(
            [rule("Company", "RIGPL", all_roles=1)],
            [perm("UP-1", USER, "Company", "RIGPL"), perm("UP-2", OTHER, "Company", "RIGPL")],
            roles={USER: {"System Manager"}, OTHER: set()}, enabled=(USER,),
        ))
        self.assertEqual(to_insert, [])
        self.assertEqual(keys(to_delete), ["UP-1", "UP-2"])

    def test_one_doctype_permission_under_all_doctypes_is_deleted(self):
        to_insert, to_delete = ups.get_changes(ctx(
            [rule("Supplier", "S1", role="Accounts User", all_doctypes=0),
             rule("Supplier", role="Accounts User")],
            [perm("UP-1", USER, "Supplier", "S1"), perm("UP-2", USER, "Supplier", "S1", all_doctypes=0)],
        ))
        self.assertEqual(to_insert, [])
        self.assertEqual(keys(to_delete), ["UP-2"])

    def test_all_doctypes_permission_needs_the_role(self):
        rules = [rule("Customer", role="Sales Representative")]
        perms = [perm("UP-1", USER, "Customer", "C1")]
        _, to_delete = ups.get_changes(ctx(rules, perms))
        self.assertEqual(keys(to_delete), ["UP-1"])
        _, to_delete = ups.get_changes(ctx(rules, perms, roles={USER: {"Sales Representative"}}))
        self.assertEqual(to_delete, [])

    def test_employee_permissions(self):
        employees = [
            d(name="EMP-1", status="Active", user_id=USER, create_user_permission=1),
            d(name="EMP-2", status="Left", user_id=None, create_user_permission=1),
            d(name="EMP-3", status="Active", user_id=USER, create_user_permission=0),
        ]
        to_insert, to_delete = ups.get_changes(ctx(
            [rule("Employee", role="Employee")], [perm("UP-1", USER, "Employee", "EMP-2")],
            roles={USER: {"Employee"}}, employees=employees,
        ))
        self.assertEqual(to_insert, [(USER, "Employee", "EMP-1", "", 1)])
        self.assertEqual(keys(to_delete), ["UP-1"])

    def test_account_permissions(self):
        rules = [rule("Account", role="Accounts User", applicable_for="GL Entry", all_doctypes=0)]
        to_insert, to_delete = ups.get_changes(ctx(
            rules,
            [perm("UP-1", USER, "Account", "Cash", "GL Entry", 0),
             perm("UP-2", USER, "Account", "Bank", "Journal Entry", 0)],
            approvers={"Bank": {USER}, "Sales": {USER}},
        ))
        self.assertEqual(to_insert, [(USER, "Account", "Bank", "GL Entry", 0),
            (USER, "Account", "Sales", "GL Entry", 0)])
        self.assertEqual(keys(to_delete), ["UP-1", "UP-2"])


class TestSyncUserPermissions(FrappeTestCase):
    def setUp(self):
        if not frappe.db.exists("User", USER):
            frappe.get_doc({"doctype": "User", "email": USER, "first_name": "UPS",
                "send_welcome_email": 0}).insert(ignore_permissions=True)

    def tearDown(self):
        frappe.db.rollback()

    def test_load_context_runs_a_fixed_number_of_queries(self):
        ups.load_context()  # loads the metas into the cache
        with assert_max_queries(6, test_case=self):
            ups.load_context()

    def test_inserts_once_and_then_has_no_changes(self):
        def test_ctx():
            perms = frappe.get_all("User Permission", filters={"user": USER}, fields=ups.UP_FIELDS)
            return ctx([rule("Role", "Accounts User", role="Accounts User")], perms)

        with patch.object(ups, "load_context", side_effect=test_ctx):
            to_insert, _ = ups.sync_user_permissions()
            self.assertEqual(to_insert, [(USER, "Role", "Accounts User", "", 1)])
            self.assertTrue(frappe.db.exists("User Permission", {"user": USER, "allow": "Role"}))
            self.assertEqual(ups.sync_user_permissions(dry_run=True), ([], []))
