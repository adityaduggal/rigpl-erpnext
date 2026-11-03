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

    def test_employee_loan_analysis(self):
        for emp in (EMP, HIDDEN):
            loan = raw("Employee Advance RIGPL", docstatus=1, posting_date="2026-09-05", total_loan=1000)
            raw("Employee Loan Detail", parent=loan, parenttype="Employee Advance RIGPL",
                parentfield="employee_loan_detail", employee=emp, loan_amount=1000, emi=100)
        run = lambda: employee_loan_analysis.execute(frappe._dict(PERIOD))
        self.assertEqual(self.employees(run), {EMP})

        frappe.set_user(USER)
        with self.assertRaises(frappe.PermissionError):
            employee_loan_analysis.execute(frappe._dict(PERIOD, details=1, employee=HIDDEN))

    def test_salary_structure(self):
        for emp, dept in ((EMP, DEPT), (HIDDEN, OTHER_DEPT)):
            raw("Salary Structure Assignment", employee=emp, department=dept, docstatus=1, from_date="2026-04-01",
                base=2000, salary_structure="_Test RIGPL Structure")
        filters = frappe._dict(PERIOD, show="Assignments", employee_status="Active", latest_salary="All")
        self.assertEqual(self.employees(lambda: salary_structure.execute(filters), column=3), {EMP})
