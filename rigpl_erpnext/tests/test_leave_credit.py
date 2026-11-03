"""Leave credit from attendance (#202)"""

import frappe
from erpnext.hr.doctype.leave_application.leave_application import get_leave_balance_on
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.hr_rigpl.utils import leave_credit
from rigpl_erpnext.tests.test_salary_slip import EMP, insert_employee

LT = "_Test RIGPL Attendance EL"
LWP = "_Test RIGPL LWP"
POLICY, PERIOD, HOLIDAYS = "_Test RIGPL Leave Policy", "_Test RIGPL Leave Period", "_Test RIGPL Holidays"
START, END = "2026-04-01", "2026-04-30"  # 30 days, 5 holidays: 25 working days
HOLIDAY_DATES = ("2026-04-05", "2026-04-12", "2026-04-19", "2026-04-26", "2026-04-14")


def insert(doctype, **fields):
    doc = frappe.get_doc(dict(doctype=doctype, **fields))
    doc.db_insert()
    for row in doc.get_all_children():
        row.db_insert()
    return doc


def insert_setup(annual=10):
    insert_employee()
    insert("Leave Type", name=LT, leave_type_name=LT, is_earned_leave=1, earned_leave_frequency="Monthly",
        rounding="0.5")
    insert("Leave Type", name=LWP, leave_type_name=LWP, is_lwp=1)
    insert("Holiday List", name=HOLIDAYS, holiday_list_name=HOLIDAYS, from_date=START, to_date=END,
        holidays=[dict(holiday_date=day, description="Off") for day in HOLIDAY_DATES])
    frappe.db.set_value("Employee", EMP, {"company": "RIGPL", "holiday_list": HOLIDAYS})
    insert("Leave Period", name=PERIOD, from_date=START, to_date=END, company="RIGPL", is_active=1)
    insert("Leave Policy", name=POLICY, title=POLICY, docstatus=1,
        leave_policy_details=[dict(leave_type=LT, annual_allocation=annual)])
    return insert("Leave Allocation", name="_T-LAL-1", employee=EMP, leave_type=LT, from_date=START, to_date=END,
        company="RIGPL", leave_policy=POLICY, docstatus=1, new_leaves_allocated=0, total_leaves_allocated=0)


def insert_attendance(days, status="Present", leave_type=None, start=2):
    for day in range(start, start + days):
        date = "2026-04-{:02d}".format(day)
        insert("Attendance", name="_T-ATT-{}-{}".format(status, date), employee=EMP, attendance_date=date,
            status=status, leave_type=leave_type, company="RIGPL", docstatus=1)


def run(date="2026-05-01"):
    leave_credit.credit_leaves_from_attendance(date)
    return frappe.db.get_value("Leave Allocation", "_T-LAL-1", "total_leaves_allocated")


class TestEarnedFormula(FrappeTestCase):
    def test_half_the_working_days_earn_half_the_leaves(self):
        self.assertEqual(leave_credit.get_earned_leaves(150, 20, 300, "1.0"), 10)

    def test_rounds_down_to_the_step(self):
        self.assertEqual(leave_credit.get_earned_leaves(156, 20, 318, "0.5"), 9.5)
        self.assertEqual(leave_credit.get_earned_leaves(14, 20, 300, "1.0"), 0)
        self.assertEqual(leave_credit.get_earned_leaves(10, 20, 300, ""), 0.66)

    def test_never_more_than_the_annual_allocation(self):
        self.assertEqual(leave_credit.get_earned_leaves(400, 20, 300, "0.5"), 20)

    def test_no_policy_or_no_working_days_gives_zero(self):
        self.assertEqual(leave_credit.get_earned_leaves(100, 0, 300, "0.5"), 0)
        self.assertEqual(leave_credit.get_earned_leaves(100, 20, 0, "0.5"), 0)


class TestCreditFromAttendance(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_credit_follows_worked_days_and_skips_holidays(self):
        insert_setup()
        insert_attendance(10)  # 10 of 25 working days with annual 10 = 4
        self.assertEqual(run(), 4)
        self.assertEqual(get_leave_balance_on(EMP, LT, END), 4)

    def test_half_day_paid_leave_and_lwp(self):
        insert_setup()
        insert_attendance(4, start=2)                                  # 4
        insert_attendance(2, status="Half Day", start=6)               # 1
        insert_attendance(1, status="Half Day", leave_type=LT, start=8)  # 1
        insert_attendance(2, status="On Leave", leave_type=LT, start=9)  # 2
        insert_attendance(3, status="On Leave", leave_type=LWP, start=11)  # 0
        worked = leave_credit.get_worked_days(frappe.get_all("Leave Allocation", filters={"name": "_T-LAL-1"},
            fields=["name"]), END)
        self.assertEqual(worked["_T-LAL-1"], 8)

    def test_second_run_adds_nothing_and_later_attendance_adds_the_rest(self):
        insert_setup()
        insert_attendance(10)
        self.assertEqual(run(), 4)
        self.assertEqual(run(), 4)
        entries = frappe.db.count("Leave Ledger Entry", {"transaction_name": "_T-LAL-1", "leaves": (">", 0)})
        self.assertEqual(entries, 1)
        insert_attendance(5, start=13)
        self.assertEqual(run(), 6)

    def test_only_attendance_before_the_run_date_counts(self):
        insert_setup()
        insert_attendance(10)
        self.assertEqual(run("2026-04-08"), 2)  # 2-7 April = 6 worked days -> 2.4 -> 2

    def test_max_leaves_allowed_caps_the_total(self):
        insert_setup()
        frappe.db.set_value("Leave Type", LT, "max_leaves_allowed", 3)
        insert_attendance(20)
        self.assertEqual(run(), 3)

    def test_read_queries_do_not_grow_with_allocations(self):
        insert_setup()
        allocations = leave_credit.get_open_allocations(END, [LT])
        with assert_max_queries(8, test_case=self) as small:
            self.read_all(allocations)
        with assert_max_queries(8, test_case=self) as large:
            self.read_all(allocations * 5)
        self.assertEqual(small.count, large.count)

    def read_all(self, allocations):
        leave_credit.get_worked_days(allocations, END)
        leave_credit.get_working_days(allocations)
        leave_credit.get_annual_allocations(allocations)
        leave_credit.get_credited_leaves([row.name for row in allocations])


class TestPolicyAssignmentStartsAtZero(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_earned_type_from_assignment_starts_at_zero(self):
        insert_setup()
        doc = frappe.get_doc(dict(doctype="Leave Allocation", employee=EMP, leave_type=LT, from_date=START,
            to_date=END, new_leaves_allocated=5, leave_policy_assignment="_T-LPA-1"))
        doc.set("__islocal", 1)  # as Document.insert does before before_validate
        leave_credit.zero_time_based_credit(doc)
        self.assertEqual(doc.new_leaves_allocated, 0)

    def test_manual_allocation_keeps_its_leaves(self):
        insert_setup()
        doc = frappe.get_doc(dict(doctype="Leave Allocation", employee=EMP, leave_type=LT, from_date=START,
            to_date=END, new_leaves_allocated=5))
        doc.set("__islocal", 1)
        leave_credit.zero_time_based_credit(doc)
        self.assertEqual(doc.new_leaves_allocated, 5)
