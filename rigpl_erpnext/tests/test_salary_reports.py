import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.report.salary_register_rigpl import salary_register_rigpl as register
from rigpl_erpnext.rigpl_erpnext.report.salary_structure import salary_structure as structure

BRANCH = "_Test RIGPL Payroll Branch"
WAGE, BOOK_WAGE, ESI, ESI_ER = ("_Test RIGPL Reg Wage", "_Test RIGPL Reg Book Wage", "_Test RIGPL Reg ESI",
    "_Test RIGPL Reg ESI Employer")
COMPONENTS = ((WAGE, dict(is_earning=1, books=0)), (BOOK_WAGE, dict(is_earning=1, books=1)),
    (ESI, dict(is_deduction=1, books=1)), (ESI_ER, dict(is_contribution=1)))


def insert_employee(name, status="Active", relieving_date=None):
    frappe.get_doc(dict(doctype="Employee", name=name, employee_name=name, first_name=name, status=status,
        gender="Male", date_of_birth="1990-01-01", date_of_joining="2020-01-01", relieving_date=relieving_date,
        branch=BRANCH, bank_name="_Test Bank", bank_ac_no="123")).db_insert()


def insert_slip(name, employee):
    doc = frappe.get_doc(dict(doctype="Salary Slip", name=name, employee=employee, employee_name=employee,
        posting_date="2026-10-31", start_date="2026-10-01", end_date="2026-10-31", docstatus=1, gross_pay=10000,
        total_deduction=75, net_pay=9925, rounded_total=9925, actual_bank_salary=8000,
        earnings=[dict(salary_component=WAGE, amount=10000), dict(salary_component=BOOK_WAGE, amount=8000)],
        deductions=[dict(salary_component=ESI, amount=75)], contributions=[dict(salary_component=ESI_ER, amount=325)]))
    doc.db_insert()
    for row in doc.get_all_children():
        row.db_insert()


def insert_ssa(name, employee, from_date, to_date=None):
    frappe.get_doc(dict(doctype="Salary Structure Assignment", name=name, employee=employee, docstatus=1,
        salary_structure="_Test RIGPL Structure", from_date=from_date, to_date=to_date, base=2000)).db_insert()


def labels(columns):
    return [c.split(":")[0] for c in columns]


class TestSalaryRegister(FrappeTestCase):
    def setUp(self):
        for name, flags in COMPONENTS:
            frappe.get_doc(dict(doctype="Salary Component", name=name, salary_component=name,
                salary_component_abbr=name[-6:], **flags)).db_insert()

    def tearDown(self):
        frappe.db.rollback()

    def run_report(self, report_type):
        return register.execute(dict(report_type=report_type, docstatus="Submitted", from_date="2026-10-01",
            to_date="2026-10-31", branch=BRANCH))

    def add_employees(self, count, start=0):
        for i in range(start, start + count):
            insert_employee("_Test RIGPL Reg Emp %s" % i)
            insert_slip("_Test RIGPL Reg Slip %s" % i, "_Test RIGPL Reg Emp %s" % i)

    def test_detailed_shows_non_books_earnings_and_all_deductions(self):
        self.add_employees(1)
        columns, data = self.run_report("Detailed")
        row = dict(zip(labels(columns), data[0]))
        self.assertNotIn(BOOK_WAGE, row)
        self.assertEqual((row[WAGE], row[ESI], row[ESI_ER], row["Rounded Pay"]), (10000, 75, 325, 9925))

    def test_bank_shows_books_pay_and_bank_details(self):
        self.add_employees(1)
        columns, data = self.run_report("Bank")
        row = dict(zip(labels(columns), data[0]))
        self.assertNotIn(WAGE, row)
        self.assertEqual((row["Gross Pay"], row["Net Pay"], row["Bank Name"]), (8000, 7925, "_Test Bank"))
        self.assertIsNone(row["Arrear Amt"])

    def test_summary_shows_cash_balance(self):
        self.add_employees(1)
        columns, data = self.run_report("Summary")
        row = dict(zip(labels(columns), data[0]))
        self.assertEqual((row["Actual Payment"], row["Bank Payment"], row["Books Payment"], row["Balance Cash"]),
            (9925, 8000, 7925, 1925))

    def test_employees_without_salary_slip(self):
        self.add_employees(1)
        insert_employee("_Test RIGPL Reg No Slip")
        _, data = self.run_report("Employees without Salary Slip")
        self.assertEqual([row[0] for row in data], ["_Test RIGPL Reg No Slip"])

    def test_query_count_does_not_depend_on_employees(self):
        counts = []
        for count in (1, 5):
            self.add_employees(count, start=len(counts) * 100)
            with assert_max_queries(10, test_case=self) as guard:
                self.run_report("Detailed")
            counts.append(guard.count)
        self.assertEqual(counts[0], counts[1])


class TestSalaryStructureReport(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def run_report(self, show="Assignments", employee_status="Active", latest_salary="All"):
        return structure.execute(dict(show=show, employee_status=employee_status, latest_salary=latest_salary,
            from_date="2025-11-01", to_date="2026-10-31", branch=BRANCH))

    def test_blank_status_shows_active_and_left(self):
        insert_employee("_Test RIGPL SSR Active")
        insert_employee("_Test RIGPL SSR Left", status="Left", relieving_date="2026-06-30")
        insert_ssa("_Test RIGPL SSR SSA 1", "_Test RIGPL SSR Active", "2026-04-01")
        insert_ssa("_Test RIGPL SSR SSA 2", "_Test RIGPL SSR Left", "2026-04-01")
        employees = lambda status: sorted(row[3] for row in self.run_report(employee_status=status)[1])
        self.assertEqual(employees("Active"), ["_Test RIGPL SSR Active"])
        self.assertEqual(employees("Left"), ["_Test RIGPL SSR Left"])
        self.assertEqual(employees(""), ["_Test RIGPL SSR Active", "_Test RIGPL SSR Left"])

    def test_latest_and_earliest_pick_one_per_employee(self):
        insert_employee("_Test RIGPL SSR Active")
        insert_ssa("_Test RIGPL SSR SSA 1", "_Test RIGPL SSR Active", "2025-04-01", "2026-03-31")
        insert_ssa("_Test RIGPL SSR SSA 2", "_Test RIGPL SSR Active", "2026-04-01")
        self.assertEqual([r[0] for r in self.run_report(latest_salary="Latest")[1]], ["_Test RIGPL SSR SSA 2"])
        self.assertEqual([r[0] for r in self.run_report(latest_salary="Earliest")[1]], ["_Test RIGPL SSR SSA 1"])
        self.assertEqual(len(self.run_report()[1]), 2)

    def test_employees_without_ssa(self):
        insert_employee("_Test RIGPL SSR Active")
        insert_employee("_Test RIGPL SSR No SSA")
        insert_ssa("_Test RIGPL SSR SSA 1", "_Test RIGPL SSR Active", "2026-04-01")
        columns, data = self.run_report(show="Employees without SSA")
        self.assertEqual(labels(columns)[0], "Employee ID")
        self.assertEqual([row[0] for row in data], ["_Test RIGPL SSR No SSA"])

    def test_query_count_does_not_depend_on_employees(self):
        counts = []
        for count in (1, 5):
            for i in range(count):
                name = "_Test RIGPL SSR Emp %s-%s" % (count, i)
                insert_employee(name)
                insert_ssa("_Test RIGPL SSR SSA %s-%s" % (count, i), name, "2026-04-01")
            with assert_max_queries(6, test_case=self) as guard:
                self.run_report()
            counts.append(guard.count)
        self.assertEqual(counts[0], counts[1])
