import frappe
from frappe.utils import getdate

from rigpl_erpnext.rigpl_erpnext.validations import shift_assignment
from rigpl_erpnext.tests.test_attendance_payroll import DAY_SHIFT, NIGHT_SHIFT, HRCase, insert, insert_shift


class TestShiftMerge(HRCase):
    def setUp(self):
        super().setUp()
        for name in (DAY_SHIFT, NIGHT_SHIFT):
            insert("Shift Type", name=name, start_time="09:00:00", end_time="17:30:00")

    def rows(self, days, shift_type=DAY_SHIFT, month="2026-11"):
        return [frappe._dict(name="SA {0}-{1:02d}".format(month, d), start_date="{0}-{1:02d}".format(month, d),
            end_date="{0}-{1:02d}".format(month, d), shift_type=shift_type) for d in days]

    def test_month_of_one_day_rows_is_one_run(self):
        runs = shift_assignment.plan_month_runs(self.rows(range(1, 31)))
        self.assertEqual(len(runs), 1)
        self.assertEqual((runs[0]["keep"], runs[0]["end_date"], len(runs[0]["cancel"])),
            ("SA 2026-11-01", getdate("2026-11-30"), 29))

    def test_month_end_shift_change_and_gap_start_new_runs(self):
        rows = self.rows([30, 31], month="2026-10") + self.rows([1, 2]) + self.rows([3], NIGHT_SHIFT) \
            + self.rows([5, 6])
        runs = shift_assignment.plan_month_runs(rows)
        self.assertEqual([(r["keep"], len(r["cancel"])) for r in runs],
            [("SA 2026-10-30", 1), ("SA 2026-11-01", 1), ("SA 2026-11-05", 1)])

    def test_second_run_changes_nothing(self):
        merged = [frappe._dict(name="SA 1", start_date="2026-11-01", end_date="2026-11-30", shift_type=DAY_SHIFT),
            frappe._dict(name="SA 2", start_date="2026-12-01", end_date="2026-12-31", shift_type=DAY_SHIFT)]
        self.assertEqual(shift_assignment.plan_month_runs(merged), [])

    def submit(self, name, start, end, shift_type=DAY_SHIFT):
        shift_assignment.on_submit(insert_shift(name, shift_type, start, end), None)
        return frappe.db.get_value("Shift Assignment", name, ["start_date", "end_date", "docstatus"])

    def test_submit_joins_both_sides_in_the_month(self):
        insert_shift("_Test RIGPL SA 1", DAY_SHIFT, "2026-11-02", "2026-11-04")
        insert_shift("_Test RIGPL SA 3", DAY_SHIFT, "2026-11-06", "2026-11-06")
        self.assertEqual(self.submit("_Test RIGPL SA 2", "2026-11-05", "2026-11-05"),
            (getdate("2026-11-02"), getdate("2026-11-06"), 1))
        self.assertEqual(frappe.db.get_value("Shift Assignment", "_Test RIGPL SA 1", "docstatus"), 2)
        self.assertEqual(frappe.db.get_value("Shift Assignment", "_Test RIGPL SA 3", "docstatus"), 2)
        self.assertTrue(frappe.db.exists("Comment", {"reference_name": "_Test RIGPL SA 1",
            "content": "Cancelled: merged into _Test RIGPL SA 2"}))

    def test_submit_does_not_join_other_month_or_shift(self):
        insert_shift("_Test RIGPL SA 1", DAY_SHIFT, "2026-10-31", "2026-10-31")
        insert_shift("_Test RIGPL SA 3", NIGHT_SHIFT, "2026-11-02", "2026-11-02")
        self.assertEqual(self.submit("_Test RIGPL SA 2", "2026-11-01", "2026-11-01"),
            (getdate("2026-11-01"), getdate("2026-11-01"), 1))
        self.assertEqual(frappe.db.get_value("Shift Assignment", "_Test RIGPL SA 1", "docstatus"), 1)
