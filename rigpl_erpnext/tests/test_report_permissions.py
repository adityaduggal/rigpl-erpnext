"""
HR reports show only the rows the user can read (#206). The user has HR User and a User Permission
on 1 Department. The employee of the other Department must not show in any report.
"""
import frappe

from rigpl_erpnext.rigpl_erpnext.report.attendance_performance_analysis import attendance_performance_analysis
from rigpl_erpnext.rigpl_erpnext.report.employee_attendance import employee_attendance
from rigpl_erpnext.rigpl_erpnext.report.employee_balances_rigpl import employee_balances_rigpl
from rigpl_erpnext.rigpl_erpnext.report.employee_loan_analysis import employee_loan_analysis
from rigpl_erpnext.rigpl_erpnext.report.leave_application_report import leave_application_report
from rigpl_erpnext.rigpl_erpnext.report.monthly_attendance_time_based import monthly_attendance_time_based
from rigpl_erpnext.rigpl_erpnext.report.salary_register_rigpl import salary_register_rigpl
from rigpl_erpnext.rigpl_erpnext.report.salary_structure import salary_structure
from rigpl_erpnext.tests.test_hr_reports import insert_attendance
from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw

USER = "_test_rigpl_report_perm@example.com"
DEPT, OTHER_DEPT = "_Test RIGPL Perm Dept", "_Test RIGPL Perm Other Dept"
EMP, HIDDEN = "_Test RIGPL Perm Employee", "_Test RIGPL Perm Hidden Employee"
BRANCH = "_Test RIGPL Perm Branch"
PERIOD = {"from_date": "2026-09-01", "to_date": "2026-09-30", "branch": BRANCH}


def make_loan(employee, gl_rows, loan=1, cancelled=False):
    """An Employee Advance with GL rows (posting_date, debit, credit, voucher_type), no hooks"""
    advance = raw("Employee Advance", docstatus=1, employee=employee, posting_date="2026-08-01",
        repay_unclaimed_amount_from_salary=loan)
    for posting_date, debit, credit, voucher_type in gl_rows:
        raw("GL Entry", party_type="Employee", party=employee, posting_date=posting_date, debit=debit,
            credit=credit, against_voucher_type="Employee Advance", against_voucher=advance,
            voucher_type=voucher_type, voucher_no=frappe.generate_hash(length=10), is_cancelled=int(cancelled))
    return advance


class TestReportPermissions(ReportTestCase):
    def setUp(self):
        for lft, dept in ((900001, DEPT), (900003, OTHER_DEPT)):
            raw("Department", name=dept, department_name=dept, is_group=0, lft=lft, rgt=lft + 1)
        for emp, dept in ((EMP, DEPT), (HIDDEN, OTHER_DEPT)):
            raw("Employee", name=emp, employee_name=emp, first_name=emp, branch=BRANCH, department=dept,
                status="Active", date_of_joining="2020-01-01")
        # db_insert, no hooks: User.on_update makes a Contact in tests, and the ERPNext Contact hook
        # (call_log.link_existing_conversations) commits.
        raw("User", name=USER, email=USER, first_name="_Test RIGPL Report Perm", user_type="System User",
            enabled=1)
        raw("Has Role", parent=USER, parenttype="User", parentfield="roles", role="HR User")
        frappe.clear_cache(user=USER)
        frappe.get_doc(dict(doctype="User Permission", user=USER, allow="Department", for_value=DEPT,
            apply_to_all_doctypes=1)).insert(ignore_permissions=True)

    def employees(self, run, column=0):
        """Employees in the report as the restricted user."""
        frappe.set_user(USER)
        try:
            return {row[column] for row in run()[1]}
        finally:
            frappe.set_user("Administrator")

    def test_salary_register(self):
        for emp, dept in ((EMP, DEPT), (HIDDEN, OTHER_DEPT)):
            raw("Salary Slip", employee=emp, employee_name=emp, department=dept, posting_date="2026-09-30",
                start_date="2026-09-01", end_date="2026-09-30", docstatus=1)
        filters = dict(PERIOD, report_type="Detailed", docstatus="Submitted")
        self.assertEqual(self.employees(lambda: salary_register_rigpl.execute(filters)), {EMP})

    def test_employee_attendance_and_time_based(self):
        for emp in (EMP, HIDDEN):
            insert_attendance(emp, "2026-09-02", punches=[("In Time", "09:00"), ("Out Time", "17:00")])
        filters = frappe._dict(month="Sep", year="2026", branch=BRANCH)
        self.assertEqual(self.employees(lambda: employee_attendance.execute(filters)), {EMP})
        self.assertEqual(self.employees(lambda: monthly_attendance_time_based.execute(filters)), {EMP})

    def test_attendance_performance(self):
        for emp in (EMP, HIDDEN):
            insert_attendance(emp, "2026-09-02")
        run = lambda: attendance_performance_analysis.execute(frappe._dict(PERIOD))
        self.assertEqual(self.employees(run), {EMP})

    def test_leave_application_report(self):
        # department as ERPNext fetches it from the Employee: strict User Permissions hide an empty one
        for emp, dept in ((EMP, DEPT), (HIDDEN, OTHER_DEPT)):
            raw("Leave Application", employee=emp, department=dept, from_date="2026-09-03", to_date="2026-09-03",
                status="Approved", docstatus=1, leave_type="_Test RIGPL O'Leave", total_leave_days=1,
                posting_date="2026-09-03")
        run = lambda: leave_application_report.execute(frappe._dict(PERIOD))
        self.assertEqual(self.employees(run, column=3), {EMP})

    def test_employee_balances(self):
        for emp in (EMP, HIDDEN):
            raw("GL Entry", party_type="Employee", party=emp, posting_date="2026-09-05", credit=500, debit=0)
        run = lambda: employee_balances_rigpl.execute(frappe._dict(PERIOD, non_zero=1))
        self.assertEqual(self.employees(run), {EMP})

    def test_employee_balances_left_employee_is_visible(self):
        """A restricted user sees the balance of an employee who left, in any Department. A left employee
        without a balance, and an employee who did not leave, stay hidden."""
        left, left_zero = "_Test RIGPL Perm Left Employee", "_Test RIGPL Perm Left Zero Employee"
        for emp in (left, left_zero):
            raw("Employee", name=emp, employee_name=emp, first_name=emp, branch=BRANCH, department=OTHER_DEPT,
                status="Left", date_of_joining="2020-01-01", relieving_date="2026-08-31")
        for emp in (EMP, HIDDEN, left):
            raw("GL Entry", party_type="Employee", party=emp, posting_date="2026-09-05", credit=500, debit=0)
        run = lambda: employee_balances_rigpl.execute(frappe._dict(PERIOD, non_zero=1))
        self.assertEqual(self.employees(run), {EMP, left})

    def test_employee_loan_analysis(self):
        for emp in (EMP, HIDDEN):
            make_loan(emp, [("2026-09-05", 1000, 0, "Journal Entry")])
        run = lambda: employee_loan_analysis.execute(frappe._dict(PERIOD))
        self.assertEqual(self.employees(run), {EMP, "Total"})

        frappe.set_user(USER)
        with self.assertRaises(frappe.PermissionError):
            employee_loan_analysis.execute(frappe._dict(PERIOD, view=employee_loan_analysis.DETAILS, employee=HIDDEN))

    def test_employee_loan_analysis_left_employee_first(self):
        """A restricted user sees the loan of an employee who left, in any Department, and the left employee
        with a balance is listed before the others. A left employee with no balance stays hidden."""
        left, left_zero = "_Test RIGPL Perm Left Employee", "_Test RIGPL Perm Left Zero Employee"
        for emp in (left, left_zero):
            raw("Employee", name=emp, employee_name=emp, first_name=emp, branch=BRANCH, department=OTHER_DEPT,
                status="Left", date_of_joining="2020-01-01", relieving_date="2026-08-31")
        for emp in (EMP, HIDDEN, left):
            make_loan(emp, [("2026-09-05", 1000, 0, "Journal Entry")])
        make_loan(left_zero, [("2026-08-05", 1000, 0, "Journal Entry"), ("2026-08-20", 0, 1000, "Salary Slip")])
        run = lambda: employee_loan_analysis.execute(frappe._dict(PERIOD))
        frappe.set_user(USER)
        try:
            rows = run()[1]
            details = employee_loan_analysis.execute(frappe._dict(PERIOD, view=employee_loan_analysis.DETAILS, employee=left))[1]
        finally:
            frappe.set_user("Administrator")
        self.assertEqual([row[0] for row in rows], [left, EMP, "Total"])
        self.assertTrue(details)

    def test_employee_loan_analysis_balances(self):
        """Opening, given, deducted and closing come from the GL of loans only; cancelled rows and advances
        that are not loans are ignored."""
        loan = make_loan(EMP, [("2026-08-10", 1000, 0, "Journal Entry"), ("2026-09-05", 0, 100, "Salary Slip"),
            ("2026-09-10", 500, 0, "Journal Entry"), ("2026-09-20", 0, 200, "Salary Slip"),
            ("2026-10-05", 0, 50, "Salary Slip")])
        make_loan(EMP, [("2026-09-06", 0, 300, "Salary Slip")], cancelled=True)
        make_loan(EMP, [("2026-09-07", 700, 0, "Journal Entry")], loan=0)
        data = employee_loan_analysis.execute(frappe._dict(PERIOD))[1]
        self.assertEqual(data[0], [EMP, EMP, "Active", "2099-12-31", 1000, 500, 300, 1200, loan])
        self.assertEqual(data[-1], ["Total", "", "", "", 1000, 500, 300, 1200, ""])

        data = employee_loan_analysis.execute(frappe._dict(PERIOD, view=employee_loan_analysis.DETAILS, employee=EMP))[1]
        self.assertEqual([(row[3], row[4], row[5], row[6]) for row in data], [
            ("", "", 1000, ""), (None, 100, 900, "Salary Slip"), (500, None, 1400, "Journal Entry"),
            (None, 200, 1200, "Salary Slip"), (500, 300, 1200, "")])

    def test_employee_loan_analysis_show_options(self):
        """Existing Loans lists the employees with a Closing balance. Transactions in Period lists the employees with
        a loan given or deducted in the period, also when the loan is repaid (Closing 0). The default is Existing Loans."""
        make_loan(EMP, [("2026-08-10", 1000, 0, "Journal Entry")])
        make_loan(HIDDEN, [("2026-09-05", 500, 0, "Journal Entry"), ("2026-09-20", 0, 500, "Salary Slip")])
        names = lambda **f: [row[0] for row in employee_loan_analysis.execute(frappe._dict(PERIOD, **f))[1]
            if row[0] != "Total"]
        self.assertEqual(names(), [EMP])
        self.assertEqual(names(view=employee_loan_analysis.EXISTING), [EMP])
        self.assertEqual(names(view=employee_loan_analysis.TRANSACTIONS), [HIDDEN])

    def test_employee_loan_analysis_pending_advances(self):
        """Deductions repay the oldest loan first, so the Closing balance is allocated to the newest advances.
        A repaid advance, a cancelled one and an advance that is not a loan are not listed."""
        make_loan(EMP, [("2026-06-10", 500, 0, "Journal Entry")])
        old = make_loan(EMP, [("2026-07-10", 1000, 0, "Journal Entry")])
        new = make_loan(EMP, [("2026-08-10", 300, 0, "Journal Entry")])
        make_loan(EMP, [("2026-09-02", 0, 1500, "Salary Slip")])
        make_loan(EMP, [("2026-09-06", 200, 0, "Journal Entry")], cancelled=True)
        make_loan(EMP, [("2026-09-07", 700, 0, "Journal Entry")], loan=0)
        data = employee_loan_analysis.execute(frappe._dict(PERIOD))[1]
        self.assertEqual(data[0][7], 300)
        self.assertEqual(data[0][8], new)
        self.assertEqual(data[-1][8], "")
        make_loan(EMP, [("2026-09-10", 100, 0, "Journal Entry")])
        data = employee_loan_analysis.execute(frappe._dict(PERIOD))[1]
        self.assertEqual(data[0][7], 400)
        self.assertEqual(len(data[0][8].split(", ")), 2)
        self.assertIn(new, data[0][8])
        self.assertNotIn(old, data[0][8])

    def test_employee_loan_analysis_query_count(self):
        """The queries do not grow with the number of employees or GL rows"""
        make_loan(EMP, [("2026-09-05", 1000, 0, "Journal Entry")])
        summary = lambda: employee_loan_analysis.execute(frappe._dict(PERIOD))
        details = lambda: employee_loan_analysis.execute(frappe._dict(PERIOD, view=employee_loan_analysis.DETAILS, employee=EMP))
        self.assert_queries(5, summary)
        self.assert_queries(5, details)
        for idx in range(20):
            name = "_Test RIGPL Perm Extra Employee {0}".format(idx)
            raw("Employee", name=name, employee_name=name, first_name=name, branch=BRANCH, department=DEPT,
                status="Active", date_of_joining="2020-01-01")
            make_loan(name, [("2026-09-05", 100, 0, "Journal Entry")])
        make_loan(EMP, [("2026-09-{0:02d}".format(day), 0, 10, "Salary Slip") for day in range(6, 26)])
        self.assert_queries(5, summary)
        self.assert_queries(5, details)

    def test_salary_structure(self):
        for emp, dept in ((EMP, DEPT), (HIDDEN, OTHER_DEPT)):
            raw("Salary Structure Assignment", employee=emp, department=dept, docstatus=1, from_date="2026-04-01",
                base=2000, salary_structure="_Test RIGPL Structure")
        filters = frappe._dict(PERIOD, show="Assignments", employee_status="Active", latest_salary="All")
        self.assertEqual(self.employees(lambda: salary_structure.execute(filters), column=3), {EMP})
