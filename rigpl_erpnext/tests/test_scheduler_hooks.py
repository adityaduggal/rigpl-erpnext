import inspect
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext import hooks
from rigpl_erpnext.rigpl_erpnext.scheduled_tasks import customer_rating, manufacturing_pipeline as mp

TASKS = "rigpl_erpnext.rigpl_erpnext.scheduled_tasks."
REMOVED = [
    TASKS + "update_job_card_status.update_rm_status_unmodified",
    TASKS + "create_new_job_cards.execute",
    TASKS + "update_job_card_status.enqueue_jc_status_update",
    TASKS + "process_sheet_update.enqueue_process_sheet_update",
]


def hook_methods():
    """Return [(frequency, method)] from scheduler_events, with cron entries as ("cron", method)."""
    methods = []
    for frequency, events in hooks.scheduler_events.items():
        if isinstance(events, dict):
            methods += [("cron", method) for cron_events in events.values() for method in cron_events]
        else:
            methods += [(frequency, method) for method in events]
    return methods


class TestSchedulerHooks(FrappeTestCase):
    def test_each_method_resolves(self):
        for _frequency, method in hook_methods():
            self.assertTrue(callable(frappe.get_attr(method)), method)

    def test_no_job_on_every_tick(self):
        self.assertNotIn("all", hooks.scheduler_events)

    def test_old_manufacturing_jobs_are_in_the_pipeline_only(self):
        methods = [method for _frequency, method in hook_methods()]
        for method in REMOVED:
            self.assertNotIn(method, methods)
        self.assertEqual(
            hooks.scheduler_events["cron"]["*/30 * * * *"], [TASKS + "manufacturing_pipeline.enqueue_pipeline"]
        )

    def test_long_jobs_do_not_enqueue_again(self):
        """A *_long job runs in the long queue already. A wrapper that enqueues again loses the dedupe."""
        for frequency, method in hook_methods():
            if frequency.endswith("_long"):
                source = inspect.getsource(frappe.get_attr(method))
                self.assertNotIn("enqueue(", source, method)

    def test_cron_wrappers_use_enqueue_once(self):
        for _frequency, method in hook_methods():
            if method.rsplit(".", 1)[-1].startswith("enqueue"):
                self.assertIn("enqueue_once(", inspect.getsource(frappe.get_attr(method)), method)

    def test_wrappers_pass_path_and_timeout(self):
        with patch.object(mp, "enqueue_once") as enqueue_once:
            mp.enqueue_pipeline()
        enqueue_once.assert_called_once_with(mp.PIPELINE, queue="long", timeout=mp.TIMEOUT)
        self.assertTrue(callable(frappe.get_attr(mp.PIPELINE)))
        with patch.object(customer_rating, "enqueue_once") as enqueue_once:
            customer_rating.enqueue_job()
        enqueue_once.assert_called_once_with(TASKS + "customer_rating.execute", queue="long", timeout=7200)


class TestManufacturingPipeline(FrappeTestCase):
    def test_steps_run_in_order(self):
        titles = [title for title, _step in mp.get_steps()]
        self.assertEqual(titles, [
            "Create Process Sheets",
            "Consolidate Transfer Operations",
            "Clean up Job Cards",
            "Update Job Card Status",
            "Update Process Sheet Priority",
        ])

    def test_failed_step_is_rolled_back_and_next_steps_run(self):
        calls = []
        steps = [
            ("One", lambda: calls.append("One")),
            ("Two", MagicMock(side_effect=frappe.ValidationError("boom"))),
            ("Three", lambda: calls.append("Three")),
        ]
        with patch.object(mp, "get_steps", return_value=steps), \
                patch.object(mp.frappe.db, "commit") as commit, \
                patch.object(mp.frappe.db, "rollback") as rollback, \
                patch.object(mp.frappe, "log_error") as log_error:
            mp.execute()
        self.assertEqual(calls, ["One", "Three"])
        self.assertEqual(commit.call_count, 2)
        rollback.assert_called_once_with()
        log_error.assert_called_once_with(title="Manufacturing Pipeline: Two failed")
