# -*- coding: utf-8 -*-
# Copyright (c) 2017, Rohit Industries Ltd. and Contributors
# See license.txt
"""Employee loans (#199): bulk entry, GL and the Salary Slip deduction"""

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.patches.v13 import rename_employee_advance_rigpl
from rigpl_erpnext.rigpl_erpnext.validations import salary_slip
from rigpl_erpnext.tests.test_salary_slip import EMP, insert_employee, new_slip

DT = "Employee Advance RIGPL"
EMP2 = "_Test RIGPL Emp Loan 2"
DEBIT, CREDIT = "Advances to Employees - RIGPL", "Cash BGH MGMT - RIGPL"


def insert_second_employee(status="Active", relieving_date=None):
    frappe.get_doc(dict(doctype="Employee", name=EMP2, employee_name=EMP2, first_name=EMP2, status=status,
        relieving_date=relieving_date, gender="Male", date_of_birth="1990-01-01",
        date_of_joining="2020-01-01")).db_insert()


def loan_doc(rows, posting_date="2026-10-05"):
    return frappe.get_doc(dict(doctype=DT, posting_date=posting_date, debit_account=DEBIT, credit_account=CREDIT,
        deduction_type="Loan Deduction", employee_loan_detail=rows))


def insert_loan(name, loan_amount, emi, posting_date="2026-09-05", employee=EMP):
    doc = frappe.get_doc(dict(doctype=DT, name=name, docstatus=1, posting_date=posting_date, debit_account=DEBIT,
        credit_account=CREDIT, deduction_type="Loan Deduction", total_loan=loan_amount,
        employee_loan_detail=[dict(employee=employee, loan_amount=loan_amount, emi=emi,
            repayment_period=loan_amount / emi)]))
    doc.db_insert()
    for row in doc.employee_loan_detail:
        row.db_insert()


def insert_paid_slip(name, start_date, deductions):
    doc = frappe.get_doc(dict(doctype="Salary Slip", name=name, employee=EMP, start_date=start_date,
        end_date=frappe.utils.get_last_day(start_date), posting_date=start_date, docstatus=1,
        deductions=[dict(salary_component="Loan Deduction", employee_loan=loan, amount=amount)
            for loan, amount in deductions]))
    doc.db_insert()
    for row in doc.deductions:
        row.db_insert()


def loan_rows(doc):
    return [(row.employee_loan, row.amount, row.default_amount) for row in doc.deductions if row.employee_loan]


class LoanCase(FrappeTestCase):
    def setUp(self):
        insert_employee()

    def tearDown(self):
        frappe.db.rollback()


class TestLoanEntry(LoanCase):
    def test_many_employees_total_and_emi_rounding(self):
        insert_second_employee()
        doc = loan_doc([dict(employee=EMP, loan_amount=1000, emi=333, repayment_period=1),
            dict(employee=EMP2, loan_amount=1000, emi=500, repayment_period=2)])
        doc.validate()
        self.assertEqual(doc.total_loan, 2000)
        first, second = doc.employee_loan_detail
        self.assertEqual((first.emi, round(first.repayment_period, 4)), (340, round(1000 / 340, 4)))
        self.assertEqual((second.emi, second.repayment_period), (500, 2))
        self.assertEqual(first.employee_name, EMP)

    def test_duplicate_employee_throws(self):
        doc = loan_doc([dict(employee=EMP, loan_amount=1000, emi=500, repayment_period=2)] * 2)
        with self.assertRaisesRegex(frappe.ValidationError, "multiple times"):
            doc.validate()

    def test_employee_who_left_before_posting_throws(self):
        insert_second_employee(status="Left", relieving_date="2026-09-30")
        doc = loan_doc([dict(employee=EMP2, loan_amount=1000, emi=500, repayment_period=2)])
        with self.assertRaisesRegex(frappe.ValidationError, "left on"):
            doc.validate()

    def test_zero_emi_throws(self):
        doc = loan_doc([dict(employee=EMP, loan_amount=1000, emi=0, repayment_period=0)])
        with self.assertRaisesRegex(frappe.ValidationError, "greater than ZERO"):
            doc.validate()

    def test_gl_is_balanced_and_cancel_reverses(self):
        insert_second_employee()
        doc = loan_doc([dict(employee=EMP, loan_amount=1000, emi=500, repayment_period=2),
            dict(employee=EMP2, loan_amount=3000, emi=1000, repayment_period=3)])
        doc.insert()
        doc.submit()
        filters = {"voucher_type": DT, "voucher_no": doc.name}
        posted = frappe.get_all("GL Entry", filters=filters, fields=["account", "party", "debit", "credit"])
        self.assertEqual(sum(r.debit for r in posted), 4000)
        self.assertEqual(sum(r.credit for r in posted), 4000)
        self.assertEqual({r.party: r.debit for r in posted if r.account == DEBIT}, {EMP: 1000, EMP2: 3000})

        doc.cancel()
        rows = frappe.get_all("GL Entry", filters=filters, fields=["debit", "credit", "is_cancelled"])
        self.assertTrue(all(r.is_cancelled for r in rows))
        self.assertEqual(sum(r.debit - r.credit for r in rows), 0)


class TestLoanDeduction(LoanCase):
    def deduct(self, slip):
        salary_slip.get_loan_deduction(slip, slip.start_date, frappe.utils.get_last_day(slip.start_date))
        return loan_rows(slip)

    def test_slip_deducts_the_emi(self):
        insert_loan("_T-EA1", 1000, 300)
        self.assertEqual(self.deduct(new_slip("2026-10-01")), [("_T-EA1", 300, 1000)])

    def test_last_slip_deducts_only_the_balance(self):
        insert_loan("_T-EA1", 1000, 300)
        insert_paid_slip("_T-SS-09", "2026-09-01", [("_T-EA1", 900)])
        self.assertEqual(self.deduct(new_slip("2026-10-01")), [("_T-EA1", 100, 100)])

    def test_paid_loan_and_later_loan_give_no_row(self):
        insert_loan("_T-EA1", 1000, 500)
        insert_loan("_T-EA2", 1000, 500, posting_date="2026-11-05")
        insert_paid_slip("_T-SS-09", "2026-09-01", [("_T-EA1", 1000)])
        self.assertEqual(self.deduct(new_slip("2026-10-01")), [])

    def test_typed_amount_above_balance_throws(self):
        insert_loan("_T-EA1", 1000, 300)
        insert_paid_slip("_T-SS-09", "2026-09-01", [("_T-EA1", 900)])
        slip = new_slip("2026-10-01", deductions=[dict(salary_component="Loan Deduction", employee_loan="_T-EA1",
            amount=200)])
        with self.assertRaisesRegex(frappe.ValidationError, "Max deduction allowed 100"):
            self.deduct(slip)

    def test_recompute_of_a_submitted_slip_does_not_count_itself(self):
        insert_loan("_T-EA1", 1000, 300)
        insert_paid_slip("_T-SS-09", "2026-09-01", [("_T-EA1", 900)])
        insert_paid_slip("_T-SS-10", "2026-10-01", [("_T-EA1", 100)])
        slip = new_slip("2026-10-01", deductions=[dict(salary_component="Loan Deduction", employee_loan="_T-EA1",
            amount=100, default_amount=100)])
        slip.name = "_T-SS-10"
        self.assertEqual(self.deduct(slip), [("_T-EA1", 100, 100)])

    def test_query_count_does_not_depend_on_loans(self):
        counts = []
        for names in (["_T-EA1"], ["_T-EA2", "_T-EA3", "_T-EA4"]):
            for name in names:
                insert_loan(name, 1000, 100)
            with assert_max_queries(4, test_case=self) as guard:
                self.deduct(new_slip("2026-10-01"))
            counts.append(guard.count)
            frappe.db.rollback()
            insert_employee()
        self.assertEqual(counts[0], counts[1])


class TestRenamePatch(FrappeTestCase):
    def test_second_run_does_nothing(self):
        with assert_max_queries(1, test_case=self):
            rename_employee_advance_rigpl.execute()
