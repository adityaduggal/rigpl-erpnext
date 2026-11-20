# -*- coding: utf-8 -*-
# Copyright (c) 2017, Rohit Industries Ltd. and Contributors
# See license.txt
"""Employee loans (#199): bulk entry, GL and the Salary Slip deduction"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.hr_rigpl.doctype.employee_advance_tool.employee_advance_tool import EmployeeAdvanceTool
from rigpl_erpnext.patches.v13 import convert_employee_advance_rigpl, rename_employee_advance_rigpl
from rigpl_erpnext.rigpl_erpnext.validations import employee_advance, expense_claim, salary_slip
from rigpl_erpnext.rigpl_erpnext.validations.salary_slip_gl import SalarySlipGL, update_employee_advances
from rigpl_erpnext.tests.test_salary_slip import EMP, insert_employee, new_slip

DT = "Employee Advance RIGPL"
EMP2 = "_Test RIGPL Emp Loan 2"
EMP3 = "_Test RIGPL Emp Loan 3"
DEBIT, CREDIT = "Advances to Employees - RIGPL", "Cash BGH MGMT - RIGPL"


def insert_employee_named(name, status="Active", relieving_date=None):
    frappe.get_doc(dict(doctype="Employee", name=name, employee_name=name, first_name=name, status=status,
        relieving_date=relieving_date, gender="Male", date_of_birth="1990-01-01",
        date_of_joining="2020-01-01")).db_insert()


def insert_second_employee(status="Active", relieving_date=None):
    insert_employee_named(EMP2, status, relieving_date)


def loan_doc(rows, posting_date="2026-10-05"):
    return frappe.get_doc(dict(doctype=DT, posting_date=posting_date, debit_account=DEBIT, credit_account=CREDIT,
        deduction_type="Loan Deduction", employee_loan_detail=rows))


def insert_loan(name, loan_amount, emi, posting_date="2026-09-05", employee=EMP, loan=1):
    """A submitted loan on the ERPNext Employee Advance (#229); loan=0 makes a normal advance"""
    frappe.get_doc(dict(doctype="Employee Advance", name=name, employee=employee, posting_date=posting_date,
        purpose="Test", advance_amount=loan_amount, paid_amount=loan_amount, advance_account=DEBIT,
        company="RIGPL", currency="INR", exchange_rate=1, docstatus=1, status="Paid",
        repay_unclaimed_amount_from_salary=loan, deduction_type="Loan Deduction" if loan else None, emi=emi,
        repayment_period=loan_amount / emi if emi else 0)).db_insert()


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

    def test_zero_emi_loan_gets_a_row_with_zero_amount(self):
        insert_loan("_T-EA1", 1000, 0)
        self.assertEqual(self.deduct(new_slip("2026-10-01")), [("_T-EA1", 0, 1000)])

    def test_typed_amount_up_to_the_balance_stays(self):
        insert_loan("_T-EA1", 1000, 300)
        slip = new_slip("2026-10-01", deductions=[dict(salary_component="Loan Deduction", employee_loan="_T-EA1",
            amount=1000, default_amount=1000)])
        self.assertEqual(self.deduct(slip), [("_T-EA1", 1000, 1000)])

    def test_normal_advance_gives_no_row(self):
        insert_loan("_T-EA1", 1000, 300, loan=0)
        self.assertEqual(self.deduct(new_slip("2026-10-01")), [])

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


def advance(advance_amount=20000, emi=0, loan=1, deduction_type=None, advance_account=DEBIT):
    return frappe._dict(advance_amount=advance_amount, emi=emi, repay_unclaimed_amount_from_salary=loan,
        deduction_type=deduction_type, repayment_period=0, company="RIGPL", advance_account=advance_account)


def insert_advance(name, loan=0):
    frappe.get_doc(dict(doctype="Employee Advance", name=name, employee=EMP, posting_date="2026-10-05",
        purpose="Test", advance_amount=1000, paid_amount=1000, advance_account=DEBIT, company="RIGPL",
        currency="INR", exchange_rate=1, docstatus=1, status="Paid", repay_unclaimed_amount_from_salary=loan,
        deduction_type="Loan Deduction" if loan else None, emi=100 if loan else 0)).db_insert()


def validated(doc):
    employee_advance.validate(doc, "validate")
    return doc


class TestEmployeeAdvanceLoanFields(LoanCase):
    """#228, #236: loans on the ERPNext Employee Advance"""

    def test_emi_is_rounded_up_to_100_and_months_are_whole(self):
        for amount, emi, expected in ((20000, 3500, (3500, 6)), (20000, 1999, (2000, 10)),
                (20000, 20000, (20000, 1)), (150, 150, (150, 1))):
            doc = validated(advance(advance_amount=amount, emi=emi))
            self.assertEqual((doc.emi, doc.repayment_period), expected, (amount, emi))

    def test_loan_emi_must_be_a_whole_number_above_zero(self):
        for emi in (0, 1999.5):
            with self.assertRaisesRegex(frappe.ValidationError, "whole number greater than ZERO"):
                validated(advance(emi=emi))

    def test_loan_gets_the_default_deduction_type_and_advance_account(self):
        # The rollback in tearDown does not clear the cached single values
        self.addCleanup(frappe.db.value_cache.pop, "RIGPL Settings", None)
        frappe.db.set_single_value("RIGPL Settings", "loan_deduction_component", "")
        doc = validated(advance(emi=2000, advance_account=None))
        self.assertEqual((doc.deduction_type, doc.advance_account), ("Loan Deduction", DEBIT))
        frappe.db.set_single_value("RIGPL Settings", "loan_deduction_component", "_Test RIGPL Loan Comp")
        self.assertEqual(validated(advance(emi=2000)).deduction_type, "_Test RIGPL Loan Comp")
        self.assertEqual(validated(advance(emi=2000, deduction_type="Other")).deduction_type, "Other")

    def test_emi_without_loan_throws(self):
        with self.assertRaisesRegex(frappe.ValidationError, "only for a loan"):
            validated(advance(emi=100, loan=0))

    def test_normal_advance_clears_the_loan_fields(self):
        doc = validated(advance(advance_amount=1234.5, loan=0, deduction_type="Loan Deduction"))
        self.assertEqual((doc.advance_amount, doc.deduction_type, doc.emi, doc.repayment_period),
            (1234.5, None, 0, 0))

    def test_additional_salary_for_a_loan_throws(self):
        insert_advance("_T-EADV-LOAN", loan=1)
        insert_advance("_T-EADV-CASH")
        employee_advance.validate_additional_salary(
            frappe._dict(ref_doctype="Employee Advance", ref_docname="_T-EADV-CASH"), "validate")
        with self.assertRaisesRegex(frappe.ValidationError, "is a loan"):
            employee_advance.validate_additional_salary(
                frappe._dict(ref_doctype="Employee Advance", ref_docname="_T-EADV-LOAN"), "validate")

    def test_expense_claim_drops_loan_rows_and_stops_an_allocated_loan(self):
        insert_advance("_T-EADV-LOAN", loan=1)
        insert_advance("_T-EADV-CASH")
        claim = frappe.new_doc("Expense Claim")
        for name in ("_T-EADV-LOAN", "_T-EADV-CASH"):
            claim.append("advances", dict(employee_advance=name, advance_paid=1000, allocated_amount=0))
        expense_claim.remove_loan_advances(claim)
        self.assertEqual([(row.employee_advance, row.idx) for row in claim.advances], [("_T-EADV-CASH", 1)])

        claim.append("advances", dict(employee_advance="_T-EADV-LOAN", advance_paid=1000, allocated_amount=500))
        with self.assertRaisesRegex(frappe.ValidationError, "is a loan"):
            expense_claim.remove_loan_advances(claim)


class TestRenamePatch(FrappeTestCase):
    def test_second_run_does_nothing(self):
        """No rigpl column total_loan in Employee Advance: no DDL and no update (#237)"""
        with patch.object(frappe.db, "has_column", return_value=False), \
                patch.object(frappe.db, "sql_ddl") as ddl, assert_max_queries(3, test_case=self):
            rename_employee_advance_rigpl.execute()
        ddl.assert_not_called()

    def check(self, names, parents, is_rigpl_module, tables, new_rows=0):
        with patch.object(frappe.db, "sql_list", side_effect=[names, parents]), \
                patch.object(frappe.db, "count", return_value=new_rows):
            return rename_employee_advance_rigpl.check_before_rename(tables, is_rigpl_module)

    def test_check_returns_names_when_they_match_the_loan_details(self):
        self.assertEqual(self.check(["EA1", "EA2"], ["EA2", "EA1"], False, []), {"EA1", "EA2"})

    def test_check_throws_when_names_and_loan_details_differ(self):
        with self.assertRaisesRegex(frappe.ValidationError, "differ from Employee Loan Detail"):
            self.check(["EA1", "EA3"], ["EA1", "EA2"], False, [])

    def test_check_throws_when_the_rigpl_table_exists_on_prod(self):
        with self.assertRaisesRegex(frappe.ValidationError, "exists already"):
            self.check(["EA1"], ["EA1"], True, ["tabEmployee Advance RIGPL"])

    def test_check_throws_when_the_rigpl_table_has_rows_on_dev(self):
        with self.assertRaisesRegex(frappe.ValidationError, "is not empty"):
            self.check(["EA1"], ["EA1"], False, ["tabEmployee Advance RIGPL"], new_rows=3)

    def test_check_passes_with_an_empty_rigpl_table_on_dev(self):
        self.assertEqual(self.check(["EA1"], ["EA1"], False, ["tabEmployee Advance RIGPL"]), {"EA1"})


def submitted_loan(rows):
    doc = loan_doc(rows)
    doc.insert()
    doc.submit()
    return doc


def insert_slip_gl(slip, loan, credit, employee=EMP, to_advance=False):
    """A Salary Slip GL credit row of a loan. to_advance=True links it to the Employee Advance (#229)"""
    link = dict(against_voucher_type="Employee Advance", against_voucher=loan) if to_advance else {}
    return frappe.get_doc(dict(doctype="GL Entry", name=frappe.generate_hash(length=10), voucher_type="Salary Slip",
        voucher_no=slip, account=DEBIT, party_type="Employee", party=employee, credit=credit,
        credit_in_account_currency=credit, against=loan, docstatus=1, is_cancelled=0, company="RIGPL",
        posting_date="2026-10-31", **link)).db_insert()


def insert_loan_gl(loan, debit, employee=EMP):
    """The Journal Entry GL debit that pays the loan: ERPNext sums it into paid_amount"""
    frappe.get_doc(dict(doctype="GL Entry", name=frappe.generate_hash(length=10), voucher_type="Journal Entry",
        voucher_no="_T-JV-" + loan, account=DEBIT, party_type="Employee", party=employee, debit=debit,
        debit_in_account_currency=debit, against_voucher_type="Employee Advance", against_voucher=loan,
        docstatus=1, is_cancelled=0, company="RIGPL", posting_date="2026-09-05")).db_insert()


class TestConvertPatch(LoanCase):
    """Conversion of the old loans to Employee Advance and Journal Entry (#230)"""

    def old_pointers(self, name):
        gl = frappe.db.count("GL Entry", {"voucher_type": DT, "voucher_no": name})
        gl += frappe.db.count("GL Entry", {"voucher_type": "Salary Slip", "against": name})
        return gl + frappe.db.count("Salary Detail", {"employee_loan": name})

    def test_loan_slip_and_detail_point_to_the_new_advances(self):
        insert_second_employee()
        doc = submitted_loan([dict(employee=EMP, loan_amount=1000, emi=500, repayment_period=2),
            dict(employee=EMP2, loan_amount=3000, emi=1000, repayment_period=3)])
        insert_paid_slip("_T-SLIP-CONVERT", "2026-10-01", [(doc.name, 400)])
        insert_slip_gl("_T-SLIP-CONVERT", doc.name, 400)

        convert_employee_advance_rigpl.convert([doc.name])

        first, second = f"{doc.name}-Row-1", f"{doc.name}-Row-2"
        advances = {row.name: row for row in frappe.get_all("Employee Advance", filters={"name": ["in", [first, second]]},
            fields=["name", "employee", "advance_amount", "paid_amount", "return_amount", "status", "docstatus",
                "advance_account", "company", "repay_unclaimed_amount_from_salary"])}
        self.assertEqual((advances[first].employee, advances[first].advance_amount, advances[first].paid_amount),
            (EMP, 1000, 1000))
        self.assertEqual((advances[first].return_amount, advances[first].status), (400, "Paid"))
        self.assertEqual((advances[second].paid_amount, advances[second].return_amount, advances[second].status),
            (3000, 0, "Paid"))
        self.assertEqual((advances[first].advance_account, advances[first].repay_unclaimed_amount_from_salary), (DEBIT, 1))

        journal = frappe.get_doc("Journal Entry", doc.name)
        self.assertEqual((journal.voucher_type, journal.total_debit, journal.docstatus), ("Cash Entry", 4000, 1))
        self.assertEqual([(row.account, row.party, row.debit, row.credit, row.reference_name) for row in journal.accounts],
            [(DEBIT, EMP, 1000, 0, first), (DEBIT, EMP2, 3000, 0, second), (CREDIT, None, 0, 4000, None)])
        self.assertEqual([row.is_advance for row in journal.accounts], ["Yes", "Yes", "No"])

        gl = frappe.get_all("GL Entry", filters={"voucher_no": doc.name},
            fields=["voucher_type", "against_voucher_type", "against_voucher", "party"])
        self.assertEqual({row.voucher_type for row in gl}, {"Journal Entry"})
        self.assertEqual({row.party: row.against_voucher for row in gl if row.party}, {EMP: first, EMP2: second})
        slip_gl = frappe.get_all("GL Entry", filters={"voucher_no": "_T-SLIP-CONVERT"},
            fields=["against", "against_voucher_type", "against_voucher"])
        self.assertEqual([(r.against, r.against_voucher_type, r.against_voucher) for r in slip_gl],
            [(first, "Employee Advance", first)])
        self.assertEqual(frappe.db.get_value("Salary Detail", {"parent": "_T-SLIP-CONVERT"}, "employee_loan"), first)
        self.assertEqual(self.old_pointers(doc.name), 0)

    def test_second_run_finds_nothing_to_convert(self):
        doc = submitted_loan([dict(employee=EMP, loan_amount=1000, emi=500, repayment_period=2)])
        convert_employee_advance_rigpl.convert([doc.name])
        self.assertTrue(frappe.db.exists("Journal Entry", doc.name))
        names = frappe.db.sql_list("""SELECT name FROM `tabEmployee Advance RIGPL` p WHERE name = %(name)s
            AND docstatus IN (1, 2) AND NOT EXISTS (SELECT 1 FROM `tabJournal Entry` j WHERE j.name = p.name)""",
            {"name": doc.name})
        self.assertEqual(names, [])

    def test_cancelled_loan_is_converted_as_cancelled(self):
        doc = submitted_loan([dict(employee=EMP, loan_amount=1000, emi=500, repayment_period=2)])
        doc.cancel()
        convert_employee_advance_rigpl.convert([doc.name])
        advance = frappe.db.get_value("Employee Advance", f"{doc.name}-Row-1", ["docstatus", "status", "paid_amount"],
            as_dict=True)
        self.assertEqual((advance.docstatus, advance.status, advance.paid_amount), (2, "Cancelled", 0))
        self.assertEqual(frappe.db.get_value("Journal Entry", doc.name, "docstatus"), 2)

    def test_balance_difference_throws(self):
        doc = submitted_loan([dict(employee=EMP, loan_amount=1000, emi=500, repayment_period=2)])
        frappe.db.sql("UPDATE `tabGL Entry` SET debit = 900 WHERE voucher_no = %(name)s AND party = %(emp)s",
            {"name": doc.name, "emp": EMP})
        with self.assertRaisesRegex(frappe.ValidationError, "old balance"):
            convert_employee_advance_rigpl.convert([doc.name])

    def test_query_count_does_not_depend_on_loans(self):
        insert_second_employee()
        rows = [dict(employee=EMP, loan_amount=1000, emi=500, repayment_period=2)]
        warm = submitted_loan(rows)
        convert_employee_advance_rigpl.convert([warm.name])
        one = submitted_loan(rows)
        many = [submitted_loan(rows).name for _ in range(3)]
        with assert_max_queries(1000) as single:
            convert_employee_advance_rigpl.convert([one.name])
        with assert_max_queries(1000) as several:
            convert_employee_advance_rigpl.convert(many)
        self.assertEqual(single.count, several.count)

    def insert_file(self, loan, file_name):
        frappe.get_doc(dict(doctype="File", name=frappe.generate_hash(length=10), file_name=file_name,
            file_url=f"/private/files/{file_name}", attached_to_doctype=DT, attached_to_name=loan, is_private=1,
            folder="Home/Attachments")).db_insert()

    def attached_to(self, file_name):
        return frappe.db.get_value("File", {"file_name": file_name}, ["attached_to_doctype", "attached_to_name"])

    def comments(self, advance):
        return frappe.get_all("Comment", filters={"reference_doctype": "Employee Advance", "reference_name": advance,
            "comment_type": "Comment"}, pluck="content")

    def test_file_moves_to_row_1_and_other_rows_get_a_comment(self):
        insert_second_employee()
        doc = submitted_loan([dict(employee=EMP, loan_amount=1000, emi=500, repayment_period=2),
            dict(employee=EMP2, loan_amount=3000, emi=1000, repayment_period=3)])
        self.insert_file(doc.name, "_t-loan-sheet.pdf")
        convert_employee_advance_rigpl.convert([doc.name])

        convert_employee_advance_rigpl.link_attachments([doc.name])

        first, second = f"{doc.name}-Row-1", f"{doc.name}-Row-2"
        self.assertEqual(self.attached_to("_t-loan-sheet.pdf"), ("Employee Advance", first))
        self.assertEqual(self.comments(first), [])
        comment = self.comments(second)
        self.assertEqual(len(comment), 1)
        self.assertIn(f"on {first}", comment[0])
        self.assertIn("_t-loan-sheet.pdf", comment[0])

        convert_employee_advance_rigpl.link_attachments([doc.name])
        self.assertEqual(len(self.comments(second)), 1)

    def test_file_of_a_single_row_loan_moves_without_a_comment(self):
        doc = submitted_loan([dict(employee=EMP, loan_amount=1000, emi=500, repayment_period=2)])
        self.insert_file(doc.name, "_t-single.pdf")
        convert_employee_advance_rigpl.convert([doc.name])
        convert_employee_advance_rigpl.link_attachments([doc.name])
        self.assertEqual(self.attached_to("_t-single.pdf"), ("Employee Advance", f"{doc.name}-Row-1"))
        self.assertEqual(frappe.db.count("Comment", {"reference_name": ["like", f"{doc.name}-Row-%"],
            "comment_type": "Comment"}), 0)

    def test_file_of_a_cancelled_loan_follows_row_1(self):
        doc = submitted_loan([dict(employee=EMP, loan_amount=1000, emi=500, repayment_period=2)])
        doc.cancel()
        self.insert_file(doc.name, "_t-cancelled.pdf")
        convert_employee_advance_rigpl.convert([doc.name])
        convert_employee_advance_rigpl.link_attachments([doc.name])
        self.assertEqual(self.attached_to("_t-cancelled.pdf"), ("Employee Advance", f"{doc.name}-Row-1"))

    def test_file_of_a_loan_that_is_not_converted_stays(self):
        doc = submitted_loan([dict(employee=EMP, loan_amount=1000, emi=500, repayment_period=2)])
        self.insert_file(doc.name, "_t-stays.pdf")
        convert_employee_advance_rigpl.link_attachments([doc.name])
        self.assertEqual(self.attached_to("_t-stays.pdf"), (DT, doc.name))


class TestLoanSlipPosting(LoanCase):
    """The Salary Slip GL and the Employee Advance after submit and cancel (#229)"""

    def slip(self, *loans):
        return frappe._dict(name="_T-SS-GL", employee=EMP, company="RIGPL", posting_date="2026-10-31",
            deductions=[frappe._dict(salary_component="Loan Deduction", employee_loan=loan, amount=amount)
                for loan, amount in loans])

    def advance(self, name="_T-EA1"):
        return frappe.db.get_value("Employee Advance", name, ["paid_amount", "return_amount", "status"], as_dict=True)

    def test_loan_credit_row_links_to_the_employee_advance(self):
        doc = self.slip(("_T-EA1", 400))
        gl = SalarySlipGL.__new__(SalarySlipGL)
        gl.doc, gl.fiscal_year = doc, "2026-2027"
        gl.company = frappe._dict(default_payroll_payable_account="Expenses Payable - RIGPL")
        gl.components = {"Loan Deduction": frappe._dict(account=DEBIT)}
        row, = gl.deduction_entries()
        self.assertEqual((row.credit, row.party_type, row.party), (400, "Employee", EMP))
        self.assertEqual((row.against_voucher_type, row.against_voucher), ("Employee Advance", "_T-EA1"))

    def test_return_amount_and_status_follow_the_slips(self):
        insert_loan("_T-EA1", 1000, 300)
        insert_loan_gl("_T-EA1", 1000)
        insert_slip_gl("_T-SS-1", "_T-EA1", 400, to_advance=True)
        update_employee_advances(self.slip(("_T-EA1", 400)))
        self.assertEqual(tuple(self.advance().values()), (1000, 400, "Paid"))

        insert_slip_gl("_T-SS-2", "_T-EA1", 600, to_advance=True)
        update_employee_advances(self.slip(("_T-EA1", 600)))
        self.assertEqual(tuple(self.advance().values()), (1000, 1000, "Returned"))

    def test_cancelled_slip_gl_is_not_counted(self):
        insert_loan("_T-EA1", 1000, 300)
        insert_loan_gl("_T-EA1", 1000)
        insert_slip_gl("_T-SS-1", "_T-EA1", 1000, to_advance=True)
        update_employee_advances(self.slip(("_T-EA1", 1000)))
        self.assertEqual(self.advance().status, "Returned")
        frappe.db.sql("UPDATE `tabGL Entry` SET is_cancelled = 1 WHERE voucher_no = '_T-SS-1'")
        update_employee_advances(self.slip(("_T-EA1", 1000)))
        self.assertEqual(tuple(self.advance().values()), (1000, 0, "Paid"))

    def test_zero_amount_rows_do_not_touch_the_advance(self):
        with patch.object(frappe, "get_doc") as get_doc:
            update_employee_advances(self.slip(("_T-EA1", 0)))
        get_doc.assert_not_called()

    def test_submit_and_cancel_update_the_advances_after_the_gl(self):
        calls = []
        doc = frappe._dict(name="_T-SS-GL", net_pay=100, earnings=[], deductions=[])
        with patch.object(salary_slip, "post_gl_entry", side_effect=lambda d: calls.append("post")), \
                patch.object(salary_slip, "cancel_gl_entry", side_effect=lambda d: calls.append("cancel")), \
                patch.object(salary_slip, "update_employee_advances", side_effect=lambda d: calls.append("update")):
            salary_slip.on_submit(doc, "on_submit")
            salary_slip.on_cancel(doc, "on_cancel")
        self.assertEqual(calls, ["post", "update", "cancel", "update"])


class TestEmployeeAdvanceTool(LoanCase):
    """The Single that gives loans to many employees in one transaction (#231)"""
    PURPOSE = "_Test Loan Tool"

    def setUp(self):
        super().setUp()
        # A Journal Entry takes the party Employee only on a Payable account. Rolled back in tearDown.
        frappe.db.set_value("Account", DEBIT, "account_type", "Payable")

    def tool(self, rows, **fields):
        tool = frappe.get_doc("Employee Advance Tool")
        tool.update(dict(posting_date="2026-10-05", company="RIGPL", advance_account=DEBIT, payment_account=CREDIT,
            purpose=self.PURPOSE, **fields))
        tool.set("employee_loan_detail", [dict(employee=emp, loan_amount=amount, emi=emi, repayment_period=0)
            for emp, amount, emi in rows])
        return tool

    def advances(self):
        return frappe.get_all("Employee Advance", filters={"purpose": self.PURPOSE}, order_by="employee",
            fields=["name", "employee", "advance_amount", "paid_amount", "status", "docstatus", "emi",
                "repayment_period", "repay_unclaimed_amount_from_salary", "deduction_type"])

    def three_rows(self):
        insert_second_employee()
        insert_employee_named(EMP3)
        return [(EMP, 1000, 333), (EMP2, 2000, 1000), (EMP3, 500, 500)]

    def test_three_rows_make_three_paid_advances_and_one_journal_entry(self):
        tool = self.tool(self.three_rows())
        journal_name = tool.create_advances()

        advances = self.advances()
        self.assertEqual([(a.employee, a.advance_amount, a.paid_amount, a.status, a.docstatus) for a in advances],
            [(EMP, 1000, 1000, "Paid", 1), (EMP2, 2000, 2000, "Paid", 1), (EMP3, 500, 500, "Paid", 1)])
        self.assertEqual([(a.emi, a.repayment_period, a.repay_unclaimed_amount_from_salary, a.deduction_type)
            for a in advances], [(400, 3, 1, "Loan Deduction"), (1000, 2, 1, "Loan Deduction"),
            (500, 1, 1, "Loan Deduction")])

        journal = frappe.get_doc("Journal Entry", journal_name)
        self.assertEqual((journal.docstatus, journal.voucher_type, journal.total_debit), (1, "Cash Entry", 3500))
        self.assertEqual(frappe.db.count("Journal Entry", {"user_remark": ["like", f"%{self.PURPOSE}%"]}), 1)
        by_name = {a.name: a for a in advances}
        self.assertEqual(sorted((r.party, r.debit, by_name[r.reference_name].employee, r.is_advance)
            for r in journal.accounts if r.account == DEBIT),
            [(EMP, 1000, EMP, "Yes"), (EMP2, 2000, EMP2, "Yes"), (EMP3, 500, EMP3, "Yes")])
        self.assertEqual([(r.account, r.credit) for r in journal.accounts if r.credit], [(CREDIT, 3500)])
        self.assertEqual(tool.employee_loan_detail, [])

    def test_duplicate_employee_makes_nothing(self):
        insert_second_employee()
        tool = self.tool([(EMP, 1000, 500), (EMP2, 1000, 500), (EMP, 2000, 500)])
        with self.assertRaisesRegex(frappe.ValidationError, "multiple times"):
            tool.create_advances()
        self.assertEqual(self.advances(), [])

    def test_employee_who_left_before_posting_makes_nothing(self):
        insert_second_employee(status="Left", relieving_date="2026-09-30")
        tool = self.tool([(EMP, 1000, 500), (EMP2, 1000, 500)])
        with self.assertRaisesRegex(frappe.ValidationError, "left on"):
            tool.create_advances()
        self.assertEqual(self.advances(), [])

    def test_empty_sheet_and_bad_amounts_throw(self):
        with self.assertRaisesRegex(frappe.ValidationError, "at least one"):
            self.tool([]).create_advances()
        with self.assertRaisesRegex(frappe.ValidationError, "multiples of 1"):
            self.tool([(EMP, 1000.5, 500)]).create_advances()
        with self.assertRaisesRegex(frappe.ValidationError, "greater than ZERO"):
            self.tool([(EMP, 1000, 0)]).create_advances()

    def test_error_after_the_advances_undoes_them(self):
        tool = self.tool(self.three_rows())
        with patch.object(EmployeeAdvanceTool, "make_journal_entry", side_effect=frappe.ValidationError("stop")):
            with self.assertRaisesRegex(frappe.ValidationError, "stop"):
                tool.create_advances()
        self.assertEqual(self.advances(), [])
        self.assertEqual(len(tool.employee_loan_detail), 3)

    def test_cancel_of_the_journal_entry_sets_the_advances_back_to_unpaid(self):
        journal_name = self.tool(self.three_rows()).create_advances()
        frappe.get_doc("Journal Entry", journal_name).cancel()
        self.assertEqual([(a.status, a.paid_amount) for a in self.advances()], [("Unpaid", 0)] * 3)
