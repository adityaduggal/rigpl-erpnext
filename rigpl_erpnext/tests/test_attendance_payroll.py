import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.patches.v13.cancel_duplicate_leave_attendance import get_rows_to_cancel
from rigpl_erpnext.rigpl_erpnext.validations import attendance, salary_slip

EMP = "_Test RIGPL Emp Attendance"
HL = "_Test RIGPL Holiday List"
SUNDAYS = ("2026-11-01", "2026-11-08", "2026-11-15", "2026-11-22", "2026-11-29")
NOV_START, NOV_END = getdate("2026-11-01"), getdate("2026-11-30")
LWP, PAID, PAID_HOL, PPL = ("_Test RIGPL LWP", "_Test RIGPL Paid", "_Test RIGPL Paid Hol", "_Test RIGPL PPL")
BASIC, OT_RATE, OT_WAGE = "_Test RIGPL Att Basic", "_Test RIGPL OT Rate", "_Test RIGPL OT Wage"
DAY_SHIFT, NIGHT_SHIFT = "_Test RIGPL Day Shift", "_Test RIGPL Night Shift"
WORKING_DAYS = [d for d in range(1, 31) if "2026-11-{:02d}".format(d) not in SUNDAYS]


def nov(day):
    return getdate("2026-11-{:02d}".format(day))


def insert(doctype, **fields):
    doc = frappe.get_doc(dict(doctype=doctype, **fields))
    doc.db_insert()
    for row in doc.get_all_children():
        row.db_insert()
    return doc


def insert_leave(name, leave_type, from_date, to_date, half_day=0, half_day_date=None):
    insert("Leave Application", name=name, employee=EMP, leave_type=leave_type, from_date=from_date,
        to_date=to_date, half_day=half_day, half_day_date=half_day_date, status="Approved", docstatus=1)


def insert_attendance(days, status="Present", overtime=0):
    for day in days:
        insert("Attendance", name="_Test RIGPL AT {0} {1}".format(status, day), employee=EMP,
            attendance_date=nov(day), status=status, overtime=overtime, docstatus=1)


def insert_shift(name, shift_type, start_date, end_date):
    return insert("Shift Assignment", name=name, employee=EMP, shift_type=shift_type, start_date=start_date,
        end_date=end_date, status="Active", docstatus=1)


class HRCase(FrappeTestCase):
    def setUp(self):
        insert("Holiday List", name=HL, holiday_list_name=HL, from_date="2026-01-01", to_date="2026-12-31",
            holidays=[dict(holiday_date=day, description="Sunday") for day in SUNDAYS])
        insert("Employee", name=EMP, employee_name=EMP, first_name=EMP, status="Active", gender="Male",
            date_of_birth="1990-01-01", date_of_joining="2020-01-01", holiday_list=HL)
        for name, is_lwp, is_ppl, include_holiday in ((LWP, 1, 0, 1), (PAID, 0, 0, 0), (PAID_HOL, 0, 0, 1),
                (PPL, 0, 1, 0)):
            insert("Leave Type", name=name, leave_type_name=name, is_lwp=is_lwp, is_ppl=is_ppl,
                include_holiday=include_holiday)

    def tearDown(self):
        frappe.db.rollback()
        self.assertFalse(frappe.db.exists("Employee", EMP), "a test committed its rows")

    def leaves(self, start=NOV_START, end=NOV_END):
        emp = frappe.get_doc("Employee", EMP)
        doc = frappe._dict(employee=EMP)
        return salary_slip.get_leaves(doc, start, end, salary_slip.get_holiday_dates(doc, start, end, emp), 0.5)


class TestLeaves(HRCase):
    def test_lwp_week_skips_the_sunday(self):
        insert_leave("_Test RIGPL LA 1", LWP, "2026-11-02", "2026-11-08")
        self.assertEqual(self.leaves(), (6, 0))

    def test_paid_leave_counts_holiday_only_if_leave_type_includes_it(self):
        insert_leave("_Test RIGPL LA 1", PAID, "2026-11-02", "2026-11-08")
        self.assertEqual(self.leaves(), (0, 6))
        frappe.db.set_value("Leave Application", "_Test RIGPL LA 1", "leave_type", PAID_HOL)
        self.assertEqual(self.leaves(), (0, 7))

    def test_half_day_leaves(self):
        insert_leave("_Test RIGPL LA 1", LWP, "2026-11-10", "2026-11-10", half_day=1)
        insert_leave("_Test RIGPL LA 2", PAID, "2026-11-11", "2026-11-13", half_day=1, half_day_date="2026-11-12")
        self.assertEqual(self.leaves(), (0.5, 2.5))

    def test_leave_outside_the_period_is_not_counted(self):
        insert_leave("_Test RIGPL LA 1", LWP, "2026-10-28", "2026-11-03")
        self.assertEqual(self.leaves(), (2, 0))

    def test_partially_paid_leave_throws(self):
        insert_leave("_Test RIGPL LA 1", PPL, "2026-11-02", "2026-11-02")
        with self.assertRaisesRegex(frappe.ValidationError, "Partially paid leave"):
            self.leaves()


class TestPaymentDays(HRCase):
    def setUp(self):
        super().setUp()
        for name, fields in ((BASIC, dict(depends_on_lwp=1)), (OT_RATE, {}),
                (OT_WAGE, dict(based_on_earning=1, earning=OT_RATE))):
            insert("Salary Component", name=name, salary_component=name, salary_component_abbr=name[-8:],
                type="Earning", **fields)

    def slip(self, ot=False):
        doc = frappe.new_doc("Salary Slip")
        doc.update(dict(employee=EMP, employee_name=EMP, company=frappe.get_all("Company", pluck="name", limit=1)[0],
            change_deductions=0, actual_bank_salary=0))
        doc.append("earnings", dict(salary_component=BASIC, default_amount=3000, amount=3000))
        if ot:
            doc.append("earnings", dict(salary_component=OT_RATE, default_amount=50, amount=50))
            doc.append("earnings", dict(salary_component=OT_WAGE, default_amount=0, amount=0))
        salary_slip.calculate_net_salary(doc, NOV_START, NOV_END)
        return doc

    def basic(self, doc):
        return {row.salary_component: row.amount for row in doc.earnings}[BASIC]

    def test_full_month(self):
        insert_attendance(WORKING_DAYS)
        doc = self.slip()
        self.assertEqual((doc.payment_days, doc.unauthorized_leaves, self.basic(doc)), (30, 0, 3000))

    def test_half_day(self):
        insert_attendance(WORKING_DAYS[:-1])
        insert_attendance(WORKING_DAYS[-1:], status="Half Day")
        doc = self.slip()
        self.assertEqual((doc.payment_days, doc.unauthorized_leaves, self.basic(doc)), (29.5, 0.5, 2950))

    def test_leave_without_pay(self):
        insert_attendance(WORKING_DAYS[:-1])
        insert_leave("_Test RIGPL LA 1", LWP, "2026-11-30", "2026-11-30")
        doc = self.slip()
        self.assertEqual((doc.payment_days, doc.leave_without_pay, doc.unauthorized_leaves, self.basic(doc)),
            (29, 1, 0, 2900))

    def test_paid_leave_is_a_payment_day(self):
        insert_attendance(WORKING_DAYS[:-1])
        insert_leave("_Test RIGPL LA 1", PAID, "2026-11-30", "2026-11-30")
        doc = self.slip()
        self.assertEqual((doc.payment_days, doc.unauthorized_leaves, self.basic(doc)), (30, 0, 3000))

    def test_half_day_lwp_with_half_day_attendance(self):
        insert_attendance(WORKING_DAYS[:-1])
        insert_attendance(WORKING_DAYS[-1:], status="Half Day")
        insert_leave("_Test RIGPL LA 1", LWP, "2026-11-30", "2026-11-30", half_day=1)
        doc = self.slip()
        self.assertEqual((doc.payment_days, doc.leave_without_pay, doc.unauthorized_leaves), (29.5, 0.5, 0))

    def test_overtime_deducted_for_unauthorized_leave(self):
        insert_attendance(WORKING_DAYS[:-1], overtime=1)
        doc = self.slip(ot=True)
        self.assertEqual((doc.total_overtime, doc.unauthorized_leaves, doc.overtime_deducted), (24, 1, 8))
        self.assertEqual({r.salary_component: r.amount for r in doc.earnings}[OT_WAGE], 50 * (24 - 8))
        self.assertEqual(self.basic(doc), 2900)

    def test_query_count_does_not_depend_on_leave_days(self):
        counts = []
        for days in (1, 20):
            insert_leave("_Test RIGPL LA {0}".format(days), LWP, "2026-11-02", nov(1 + days))
            with assert_max_queries(60, test_case=self) as guard:
                self.slip()
            counts.append(guard.count)
            frappe.db.delete("Leave Application", {"name": "_Test RIGPL LA {0}".format(days)})
        self.assertEqual(counts[0], counts[1])


class TestShift(HRCase):
    def setUp(self):
        super().setUp()
        insert("Shift Type", name=DAY_SHIFT, start_time="09:00:00", end_time="17:30:00", in_out_required=1,
            hours_required_per_day="08:00:00", time_rounding="00:30:00", time_margin="00:10:00",
            delayed_entry_allowed_time="00:15:00", early_entry_allowed_time="00:30:00", next_day=0)
        insert("Shift Type", name=NIGHT_SHIFT, start_time="21:00:00", end_time="05:30:00", in_out_required=0)

    def shift_on(self, day):
        doc = frappe._dict(employee=EMP, attendance_date=nov(day))
        attendance.get_shift(doc, nov(day))
        return doc.shift

    def test_v13_range_row_without_date(self):
        insert_shift("_Test RIGPL SA 1", DAY_SHIFT, "2026-11-01", "2026-11-30")
        self.assertEqual(self.shift_on(15), DAY_SHIFT)

    def test_holiday_takes_the_day_before(self):
        insert_shift("_Test RIGPL SA 1", NIGHT_SHIFT, "2026-11-07", "2026-11-07")
        self.assertEqual(self.shift_on(8), NIGHT_SHIFT)
        with self.assertRaisesRegex(frappe.ValidationError, "No Shift Assignment defined"):
            self.shift_on(9)

    def test_cancelled_assignment_is_ignored(self):
        insert_shift("_Test RIGPL SA 1", DAY_SHIFT, "2026-11-02", "2026-11-02")
        frappe.db.set_value("Shift Assignment", "_Test RIGPL SA 1", "docstatus", 2)
        with self.assertRaisesRegex(frappe.ValidationError, "No Shift Assignment defined"):
            self.shift_on(2)

    def overtime(self, status, out_time, **fields):
        doc = frappe.new_doc("Attendance")
        doc.update(dict(employee=EMP, attendance_date=nov(2), status=status, shift=DAY_SHIFT, **fields))
        if out_time:
            doc.append("attendance_time", dict(time_type="In Time", date_time="2026-11-02 09:00:00"))
            doc.append("attendance_time", dict(time_type="Out Time", date_time="2026-11-02 " + out_time))
        attendance.calculate_overtime(doc, frappe.get_doc("Shift Type", DAY_SHIFT), nov(2))
        return doc.overtime

    def test_overtime_full_and_half_day(self):
        self.assertEqual(self.overtime("Present", "19:00:00"), 2)
        self.assertEqual(self.overtime("Half Day", "14:00:00"), 1)

    def test_half_day_leave_without_punches(self):
        self.assertEqual(self.overtime("Half Day", None, leave_application="_Test RIGPL LA 1"), 0)
        with self.assertRaisesRegex(frappe.ValidationError, "In and Out Punch are required"):
            self.overtime("Half Day", None)


class TestDuplicateLeaveAttendance(FrappeTestCase):
    def row(self, name, day, leave_application=None, status="On Leave", creation="2026-11-01 10:00:00"):
        return frappe._dict(name=name, employee="E1", attendance_date=day, status=status,
            leave_application=leave_application, creation=creation)

    def test_linked_row_stays(self):
        rows = [self.row("A", "2026-11-02"), self.row("B", "2026-11-02", "LA1", creation="2026-11-01 11:00:00")]
        self.assertEqual(get_rows_to_cancel(rows), ["A"])

    def test_oldest_stays_without_link(self):
        rows = [self.row("B", "2026-11-02", creation="2026-11-01 11:00:00"), self.row("A", "2026-11-02")]
        self.assertEqual(get_rows_to_cancel(rows), ["B"])

    def test_only_on_leave_is_cancelled(self):
        rows = [self.row("A", "2026-11-02", "LA1"), self.row("B", "2026-11-02", status="Present")]
        with self.assertRaises(AssertionError):
            get_rows_to_cancel(rows)

    def test_single_rows_are_kept(self):
        self.assertEqual(get_rows_to_cancel([self.row("A", "2026-11-02"), self.row("B", "2026-11-03")]), [])
