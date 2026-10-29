from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, get_datetime, now_datetime
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.scheduled_tasks import communication as task
from rigpl_erpnext.rigpl_erpnext.validations.todo import close_follow_up

USER = "_test_rigpl_follow_up@example.com"
OTHER = "_test_rigpl_follow_up_other@example.com"
DISABLED = "_test_rigpl_follow_up_disabled@example.com"


def make_user(email, first_name, mobile_no, enabled=1):
    if not frappe.db.exists("User", email):
        # mobile_no is mandatory on this site (Property Setter) and unique. The first name names
        # the Contact that User.on_update makes, so it must be unique too.
        frappe.get_doc({"doctype": "User", "email": email, "first_name": first_name, "enabled": enabled,
            "mobile_no": mobile_no, "send_welcome_email": 0}).insert(ignore_permissions=True)


def make_follow_up(user=USER, ref=USER, due=True):
    comm = frappe.get_doc({
        "doctype": "Communication",
        "communication_type": "Communication",
        "communication_medium": "Phone",
        "communication_subtype": "Sales Related",
        "subject": "_Test RIGPL follow up",
        "content": "Call back",
        "reference_doctype": "User",
        "reference_name": ref,
        "user": user,
        "follow_up": 1,
        "next_action_date": add_to_date(now_datetime(), days=2),
    }).insert(ignore_permissions=True)
    if due:
        set_due(comm.name)
    return comm.name


def set_due(name):
    frappe.db.set_value("Communication", name, "next_action_date", add_to_date(now_datetime(), hours=-2),
        update_modified=False)


def run(*names):
    task.process_follow_ups(task.get_due_follow_ups(names=list(names)))


def todos(name, status="Open"):
    return frappe.get_all("ToDo", filters={"reference_type": "Communication", "reference_name": name,
        "status": status}, pluck="name")


def follow_up(name):
    return frappe.db.get_value("Communication", name, "follow_up")


class TestCommunicationFollowUp(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_user(USER, "_Test RIGPL Follow Up", "+91-0000000150")
        make_user(OTHER, "_Test RIGPL Follow Up Other", "+91-0000000151")
        make_user(DISABLED, "_Test RIGPL Follow Up Disabled", "+91-0000000152", enabled=0)

    def setUp(self):
        mail = patch.object(task, "send_follow_up_email")
        self.mail = mail.start()
        self.addCleanup(mail.stop)

    def tearDown(self):
        frappe.db.rollback()

    def test_makes_one_todo_and_one_email_then_nothing(self):
        name = make_follow_up()
        run(name)
        run(name)
        self.assertEqual(len(todos(name)), 1)
        self.mail.assert_called_once()

    def test_follow_up_not_due_gets_no_todo(self):
        name = make_follow_up(due=False)
        run(name)
        self.assertEqual(todos(name), [])

    def test_closed_todo_is_not_reopened(self):
        name = make_follow_up()
        run(name)
        todo = frappe.get_doc("ToDo", todos(name)[0])
        todo.status = "Closed"
        todo.save(ignore_permissions=True)
        run(name)
        self.assertEqual(todos(name), [])
        self.assertEqual(todos(name, "Closed"), [todo.name])
        self.assertEqual(follow_up(name), 0)

    def test_disabled_or_empty_user_ends_follow_up(self):
        disabled = make_follow_up(user=DISABLED)
        empty = make_follow_up()
        frappe.db.set_value("Communication", empty, "user", None, update_modified=False)
        old_todo = frappe.get_doc({"doctype": "ToDo", "owner": DISABLED, "status": "Open",
            "description": "_Test RIGPL follow up", "reference_type": "Communication",
            "reference_name": disabled}).insert(ignore_permissions=True)
        run(disabled, empty)
        self.assertEqual((follow_up(disabled), follow_up(empty)), (0, 0))
        self.assertEqual(todos(disabled) + todos(empty), [])
        self.assertEqual(frappe.db.get_value("ToDo", old_todo.name, "status"), "Closed")
        self.mail.assert_not_called()

    def test_ending_follow_ups_runs_a_fixed_number_of_queries(self):
        names = [make_follow_up(user=DISABLED, ref=ref) for ref in (USER, OTHER, DISABLED)]
        frappe.get_meta("Communication")  # loads the meta into the cache
        with assert_max_queries(5, test_case=self):
            run(*names)
        self.assertEqual([follow_up(name) for name in names], [0, 0, 0])

    def test_close_follow_up_done_ends_follow_up(self):
        name = make_follow_up()
        run(name)
        close_follow_up(todos(name)[0])
        self.assertEqual(follow_up(name), 0)
        self.assertEqual(todos(name), [])

    def test_close_follow_up_with_date_reminds_again(self):
        name = make_follow_up()
        run(name)
        first = todos(name)[0]
        next_date = add_to_date(now_datetime(), days=1).replace(microsecond=0)
        close_follow_up(first, next_action_date=str(next_date))
        self.assertEqual(follow_up(name), 1)
        self.assertEqual(get_datetime(frappe.db.get_value("Communication", name, "next_action_date")), next_date)
        self.assertEqual(frappe.db.get_value("ToDo", first, "status"), "Closed")
        run(name)
        self.assertEqual(todos(name), [])
        set_due(name)
        run(name)
        self.assertEqual(len(todos(name)), 1)
        self.assertNotIn(first, todos(name))

    def test_close_follow_up_date_less_than_one_hour_ahead_throws(self):
        name = make_follow_up()
        run(name)
        with self.assertRaises(frappe.ValidationError):
            close_follow_up(todos(name)[0], next_action_date=str(add_to_date(now_datetime(), minutes=10)))

    def test_cancelled_todo_ends_follow_up(self):
        name = make_follow_up()
        run(name)
        todo = frappe.get_doc("ToDo", todos(name)[0])
        todo.status = "Cancelled"
        todo.save(ignore_permissions=True)
        self.assertEqual(follow_up(name), 0)

    def test_new_call_ends_older_follow_up_of_same_user(self):
        older = make_follow_up()
        run(older)
        other_user = make_follow_up(user=OTHER)
        newer = make_follow_up()
        self.assertEqual(follow_up(older), 0)
        self.assertEqual(todos(older), [])
        self.assertEqual((follow_up(newer), follow_up(other_user)), (1, 1))
