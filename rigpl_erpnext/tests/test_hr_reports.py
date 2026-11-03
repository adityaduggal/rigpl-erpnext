"""
HR reports after the move from '%s' SQL to frappe.qb (#187). Each filter value has a quote: the
old reports put it into the SQL text and failed.
"""
import frappe
from frappe.utils import getdate

from rigpl_erpnext.hr_rigpl.utils.attendance_report_utils import get_holidays_by_day, get_leaves_by_day, get_month
from rigpl_erpnext.hr_rigpl.utils.hr_utils import get_base_list_holiday_counts
from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw

EMP = "_Test RIGPL O'Brien Employee"
EMP_2 = "_Test RIGPL O'Brien Employee 2"
BRANCH = "_Test RIGPL O'Branch"
BASE_LIST = "_Test RIGPL O'Base List"
HOLIDAY_LIST = "_Test RIGPL O'Holiday List 2026"
SHIFT = "_Test RIGPL O'Shift"
SEPT = {"month": "Sep", "year": "2026", "branch": BRANCH}


def insert_employee(name, holiday_list=HOLIDAY_LIST, **values):
    values.setdefault("date_of_joining", "2020-01-01")
    raw("Employee", name=name, employee_name=name, first_name=name, branch=BRANCH, status="Active",
        holiday_list=holiday_list, **values)


def insert_holiday_list(dates, weekly_off="Sunday"):
    """A holiday list made from BASE_LIST with the given (date, description)."""
    raw("Holiday List", name=HOLIDAY_LIST, holiday_list_name=HOLIDAY_LIST, from_date="2026-01-01",
        to_date="2026-12-31", base_holiday_list=BASE_LIST, is_base_list=0, weekly_off=weekly_off)
    for idx, (date, description) in enumerate(dates, start=1):
        raw("Holiday", parent=HOLIDAY_LIST, parenttype="Holiday List", parentfield="holidays", idx=idx,
            holiday_date=date, description=description)


def insert_attendance(employee, date, status="Present", overtime=0, punches=()):
    """punches: [(time_type, "HH:MM")]"""
    name = raw("Attendance", employee=employee, attendance_date=date, status=status, docstatus=1, overtime=overtime)
    for idx, (time_type, time) in enumerate(punches, start=1):
        raw("Attendance Time Table", parent=name, parenttype="Attendance", parentfield="attendance_time", idx=idx,
            time_type=time_type, date_time=f"{date} {time}:00")
    return name


def insert_leave(employee, from_date, to_date, days, status="Approved", docstatus=1):
    return raw("Leave Application", employee=employee, from_date=from_date, to_date=to_date, status=status,
        docstatus=docstatus, leave_type="_Test RIGPL O'Leave", total_leave_days=days, posting_date=from_date)


class TestAttendanceReportUtils(ReportTestCase):
    def test_month_needs_valid_month_and_year(self):
        self.assertEqual(get_month(frappe._dict(month="Feb", year="2028")).days, 29)
        self.assertRaises(frappe.ValidationError, get_month, frappe._dict(month="Sept", year="2026"))
        self.assertRaises(frappe.ValidationError, get_month, frappe._dict(month="Sep", year="O'2026"))

    def test_leaves_cross_the_month_end(self):
        insert_leave(EMP, "2026-08-30", "2026-09-02", 4)
        insert_leave(EMP, "2026-09-10", "2026-09-10", 1, status="Open")

        leaves = self.assert_queries(1, lambda: get_leaves_by_day([EMP], "2026-09-01", "2026-09-30"))

        self.assertEqual(leaves, {EMP: {1: "_Test RIGPL O'Leave", 2: "_Test RIGPL O'Leave"}})

    def test_holidays_and_base_list_counts(self):
        insert_holiday_list([("2026-09-06", "Sunday"), ("2026-10-02", "O'Gandhi Jayanti")])
        employees = {EMP: frappe._dict(name=EMP, holiday_list=HOLIDAY_LIST)}

        self.assertEqual(get_holidays_by_day(employees, "2026-09-01", "2026-09-30"), {EMP: {6: "Sunday"}})
        self.assertEqual(get_base_list_holiday_counts([BASE_LIST], "2026-09-01", "2026-10-31"), {BASE_LIST: 2})
