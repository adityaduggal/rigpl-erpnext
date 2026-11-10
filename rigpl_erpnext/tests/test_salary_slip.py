import json
import os

import frappe
from frappe.model.delete_doc import check_if_doc_is_dynamically_linked
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.rigpl_erpnext.validations import salary_slip, salary_structure_assignment as ssa_hooks
from rigpl_erpnext.rigpl_erpnext.validations.salary_slip_gl import SalarySlipGL, validate_ec_posting

EMP = "_Test RIGPL Emp Payroll"
SS_A = "_Test RIGPL Structure A"
SS_B = "_Test RIGPL Structure B"
BASIC, HRA, MAN1, MAN2 = ("_Test RIGPL Basic", "_Test RIGPL HRA", "_Test RIGPL Manual 1", "_Test RIGPL Manual 2")
COMPONENTS = ((BASIC, "TRBASIC", 0), (HRA, "TRHRA", 0), (MAN1, "TRMAN1", 1), (MAN2, "TRMAN2", 1))
EARNINGS = (
    dict(salary_component=BASIC, abbr="TRBASIC", amount_based_on_formula=1, formula="base * 0.5"),
    dict(salary_component=HRA, abbr="TRHRA", amount_based_on_formula=1, formula="TRBASIC * 0.4",
        condition="base > 1000"),
    dict(salary_component=MAN1, abbr="TRMAN1", amount=0),
    dict(salary_component=MAN2, abbr="TRMAN2", amount=0),
)


def insert_employee(date_of_joining="2020-01-01"):
    frappe.get_doc(dict(doctype="Employee", name=EMP, employee_name=EMP, first_name=EMP, status="Active",
        gender="Male", date_of_birth="1990-01-01", date_of_joining=date_of_joining)).db_insert()


def insert_structure(name, earnings=EARNINGS):
    doc = frappe.get_doc(dict(doctype="Salary Structure", name=name, docstatus=1, is_active="Yes",
        payroll_frequency="Monthly", earnings=[dict(row) for row in earnings]))
    doc.db_insert()
    for row in doc.get_all_children():
        row.db_insert()


def insert_ssa(name, structure, from_date, docstatus=1, base=2000):
    frappe.get_doc(dict(doctype="Salary Structure Assignment", name=name, employee=EMP, salary_structure=structure,
        from_date=from_date, base=base, docstatus=docstatus)).db_insert()


def new_slip(start_date, earnings=(), deductions=()):
    doc = frappe.new_doc("Salary Slip")
    doc.update(dict(employee=EMP, payroll_frequency="Monthly", start_date=start_date))
    for row in earnings:
        doc.append("earnings", row)
    for row in deductions:
        doc.append("deductions", row)
    return doc


def amounts(rows):
    return {row.salary_component: row.amount for row in rows}


class PayrollCase(FrappeTestCase):
    def setUp(self):
        for name, abbr, manual in COMPONENTS:
            frappe.get_doc(dict(doctype="Salary Component", name=name, salary_component=name,
                salary_component_abbr=abbr, type="Earning", manual=manual)).db_insert()
        insert_structure(SS_A)
        insert_structure(SS_B, EARNINGS[:1])

    def tearDown(self):
        frappe.db.rollback()
        self.assertFalse(frappe.db.exists("Salary Component", BASIC), "a test committed its rows")


class TestCustomFieldsSync(FrappeTestCase):
    def test_salary_slip_json_names_its_doctype(self):
        path = os.path.join(frappe.get_app_path("rigpl_erpnext", "rigpl_erpnext"), "custom", "salary_slip.json")
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data["doctype"], "Salary Slip")
        self.assertEqual({row["dt"] for row in data["custom_fields"]}, {"Salary Slip"})


class TestStructureSelection(PayrollCase):
    def test_latest_submitted_ssa_on_or_before_start(self):
        insert_employee()
        insert_ssa("_Test RIGPL SSA 1", SS_B, "2026-01-01")
        insert_ssa("_Test RIGPL SSA 2", SS_A, "2026-06-01")
        insert_ssa("_Test RIGPL SSA 3", SS_B, "2026-10-01", docstatus=2)
        insert_ssa("_Test RIGPL SSA 4", SS_B, "2026-12-01")
        doc = new_slip("2026-11-01")
        salary_slip.get_edc(doc)
        self.assertEqual(doc.salary_structure, SS_A)

    def test_mid_month_joiner_takes_ssa_from_joining_date(self):
        insert_employee("2026-10-15")
        insert_ssa("_Test RIGPL SSA 1", SS_A, "2026-10-15")
        for start_date in ("2026-10-01", getdate("2026-10-01")):
            doc = new_slip(start_date)
            salary_slip.get_edc(doc)
            self.assertEqual(doc.salary_structure, SS_A)

    def test_no_ssa_throws(self):
        insert_employee()
        with self.assertRaisesRegex(frappe.ValidationError, "No Salary Structure"):
            salary_slip.get_edc(new_slip("2026-11-01"))


class TestRowsFromStructure(PayrollCase):
    def setUp(self):
        super().setUp()
        insert_employee()

    def test_formula_uses_earlier_row_and_condition(self):
        insert_ssa("_Test RIGPL SSA 1", SS_A, "2026-01-01", base=2000)
        doc = new_slip("2026-11-01")
        salary_slip.get_edc(doc)
        self.assertEqual(amounts(doc.earnings)[BASIC], 1000)
        self.assertEqual(amounts(doc.earnings)[HRA], 400)

    def test_false_condition_gives_no_amount(self):
        insert_ssa("_Test RIGPL SSA 1", SS_A, "2026-01-01", base=1000)
        doc = new_slip("2026-11-01")
        salary_slip.get_edc(doc)
        self.assertFalse(amounts(doc.earnings)[HRA])

    def test_each_manual_earning_keeps_its_own_amount(self):
        insert_ssa("_Test RIGPL SSA 1", SS_A, "2026-01-01")
        doc = new_slip("2026-11-01", earnings=[dict(salary_component=MAN1, amount=500),
            dict(salary_component=MAN2, amount=700)])
        salary_slip.get_edc(doc)
        self.assertEqual((amounts(doc.earnings)[MAN1], amounts(doc.earnings)[MAN2]), (500, 700))
        self.assertEqual({r.salary_component: r.default_amount for r in doc.earnings}[MAN1], 500)

    def test_each_loan_row_is_kept(self):
        insert_ssa("_Test RIGPL SSA 1", SS_A, "2026-01-01")
        loans = [dict(salary_component="Loan Deduction", employee_loan="EA-T1", default_amount=1000, amount=100),
            dict(salary_component="Loan Deduction", employee_loan="EA-T2", default_amount=2000, amount=200)]
        doc = new_slip("2026-11-01", deductions=loans)
        salary_slip.get_edc(doc)
        kept = [(r.salary_component, r.employee_loan, r.default_amount, r.amount) for r in doc.deductions]
        self.assertEqual(kept, [("Loan Deduction", "EA-T1", 1000, 100), ("Loan Deduction", "EA-T2", 2000, 200)])

    def test_query_count_does_not_depend_on_rows(self):
        insert_ssa("_Test RIGPL SSA 1", SS_A, "2026-01-01")
        insert_ssa("_Test RIGPL SSA 2", SS_B, "2026-12-01")
        counts = []
        for start_date, earnings in (("2026-11-01", [dict(salary_component=MAN1, amount=5)]),
                ("2026-11-01", [dict(salary_component=c[0], amount=5) for c in COMPONENTS])):
            doc = new_slip(start_date, earnings=earnings)
            with assert_max_queries(40, test_case=self) as guard:
                salary_slip.get_edc(doc)
            counts.append(guard.count)
        self.assertEqual(counts[0], counts[1])


class TestSSAValidate(PayrollCase):
    def ssa(self, **fields):
        doc = frappe._dict(name="_Test RIGPL SSA New", employee=EMP, from_date="2026-11-15", to_date=None, base=2000)
        doc.update(fields)
        return doc

    def test_from_date_moves_to_month_start_or_joining(self):
        insert_employee()
        doc = self.ssa()
        ssa_hooks.validate(doc, None)
        self.assertEqual(getdate(doc.from_date), getdate("2026-11-01"))
        frappe.db.set_value("Employee", EMP, "date_of_joining", "2026-11-10", update_modified=False)
        doc = self.ssa(from_date="2026-11-20")
        ssa_hooks.validate(doc, None)
        self.assertEqual(getdate(doc.from_date), getdate("2026-11-10"))

    def test_to_date_as_string_is_accepted(self):
        insert_employee()
        insert_ssa("_Test RIGPL SSA 2", SS_A, "2026-12-01")
        ssa_hooks.validate(self.ssa(to_date="2026-11-30"), None)
        with self.assertRaisesRegex(frappe.ValidationError, "To Date should be 2026-11-30"):
            ssa_hooks.validate(self.ssa(to_date="2026-11-29"), None)

    def test_cancelled_future_ssa_is_ignored(self):
        insert_employee()
        insert_ssa("_Test RIGPL SSA 2", SS_A, "2026-12-01", docstatus=2)
        ssa_hooks.validate(self.ssa(), None)
        with self.assertRaisesRegex(frappe.ValidationError, "To Date should be Blank"):
            ssa_hooks.validate(self.ssa(to_date="2026-11-30"), None)


GL_EARN, GL_ESI, GL_ESI_ER = "_Test RIGPL GL Wage", "_Test RIGPL GL ESI", "_Test RIGPL GL ESI Employer"
GL_COMPONENTS = ((GL_EARN, "TRGLW", dict(account="Wages Account - RIGPL")),
    (GL_ESI, "TRGLESI", dict(account="RIGB ESI Payable - RIGPL")),
    (GL_ESI_ER, "TRGLESIER", dict(account="ESI Employers Share - RIGPL", liability_account="RIGB ESI Payable - RIGPL")))


def gl_slip(earnings=1, **fields):
    rows = lambda comp, amount, n: [frappe._dict(salary_component=comp, amount=amount) for _ in range(n)]
    doc = frappe._dict(name="_Test RIGPL Slip GL", company="RIGPL", posting_date=getdate("2026-10-31"),
        employee=EMP, net_pay=10000 * earnings - 75, rounded_total=10000 * earnings - 75,
        earnings=rows(GL_EARN, 10000, earnings), deductions=rows(GL_ESI, 75, 1), contributions=rows(GL_ESI_ER, 325, 1))
    doc.update(fields)
    return doc


class TestSalarySlipGL(FrappeTestCase):
    def setUp(self):
        insert_employee()
        for name, abbr, accounts in GL_COMPONENTS:
            frappe.get_doc(dict(doctype="Salary Component", name=name, salary_component=name,
                salary_component_abbr=abbr, **accounts)).db_insert()

    def tearDown(self):
        frappe.db.rollback()

    def test_map_is_balanced_with_payable_to_employee(self):
        gl_map = SalarySlipGL(gl_slip(rounded_total=9930)).build()
        self.assertEqual(sum(e.debit for e in gl_map), sum(e.credit for e in gl_map))
        by_account = {e.account: e for e in gl_map}
        payable = by_account["Expenses Payable - RIGPL"]
        self.assertEqual((payable.credit, payable.party_type, payable.party), (9930, "Employee", EMP))
        self.assertEqual(by_account["Short and Excess - RIGPL"].debit, 5)
        self.assertEqual(by_account["ESI Employers Share - RIGPL"].debit, 325)
        self.assertEqual(sum(e.credit for e in gl_map if e.account == "RIGB ESI Payable - RIGPL"), 75 + 325)

    def test_submit_posts_and_cancel_reverses(self):
        doc = gl_slip()
        # GL Entry checks that its voucher exists
        frappe.get_doc(dict(doctype="Salary Slip", name=doc.name, employee=EMP, company=doc.company,
            posting_date=doc.posting_date, start_date="2026-10-01", end_date="2026-10-31", docstatus=1)).db_insert()
        salary_slip.post_gl_entry(doc)
        filters = {"voucher_type": "Salary Slip", "voucher_no": doc.name}
        posted = frappe.get_all("GL Entry", filters=filters, fields=["debit", "credit"])
        self.assertTrue(posted)
        self.assertEqual(sum(r.debit for r in posted), sum(r.credit for r in posted))

        salary_slip.cancel_gl_entry(doc)
        rows = frappe.get_all("GL Entry", filters=filters, fields=["account", "debit", "credit", "is_cancelled"])
        self.assertTrue(all(r.is_cancelled for r in rows))
        for account in {r.account for r in rows}:
            self.assertEqual(sum(r.debit - r.credit for r in rows if r.account == account), 0, account)

    def test_cancel_passes_the_link_check(self):
        doc = gl_slip(doctype="Salary Slip")
        frappe.get_doc(dict(doctype="Salary Slip", name=doc.name, employee=EMP, company=doc.company,
            posting_date=doc.posting_date, start_date="2026-10-01", end_date="2026-10-31", docstatus=1)).db_insert()
        salary_slip.post_gl_entry(doc)
        with self.assertRaises(frappe.LinkExistsError):
            check_if_doc_is_dynamically_linked(doc, method="Cancel")

        salary_slip.on_cancel(doc, "on_cancel")
        check_if_doc_is_dynamically_linked(doc, method="Cancel")

    def test_component_without_account_throws_with_its_name(self):
        frappe.db.set_value("Salary Component", GL_ESI, "account", None)
        with self.assertRaisesRegex(frappe.ValidationError, GL_ESI):
            SalarySlipGL(gl_slip()).build()

    def test_query_count_does_not_depend_on_rows(self):
        def slip_with_claims(earnings):
            doc = gl_slip(earnings=earnings)
            for i, row in enumerate(doc.earnings[1:]):
                row.expense_claim = "_Test RIGPL EC %s" % i
            return doc

        validate_ec_posting(slip_with_claims(2))  # load the Company, fiscal year and GL Entry meta caches
        SalarySlipGL(slip_with_claims(2)).build()
        counts = []
        for earnings in (2, 6):
            doc = slip_with_claims(earnings)
            with assert_max_queries(4, test_case=self) as guard:
                SalarySlipGL(doc).build()
                validate_ec_posting(doc)
            counts.append(guard.count)
        self.assertEqual(counts[0], counts[1])


class TestDeductionProration(FrappeTestCase):
    ESI = frappe._dict(depends_on_lwp=1, round_up=1)
    EPF = frappe._dict(depends_on_lwp=1, round_up=0)

    def amount(self, comp, default_amount, payment_days, days=30):
        row = frappe._dict(default_amount=default_amount, amount=default_amount)
        return salary_slip.deduction_amount(row, comp, payment_days, days)

    def test_esi_rounds_up_and_zero_stays_zero(self):
        self.assertEqual(self.amount(self.ESI, 533, 15), 267)
        self.assertEqual(self.amount(self.ESI, 600, 15), 300)
        self.assertEqual(self.amount(self.ESI, 0, 30), 0)
        self.assertEqual(self.amount(self.ESI, None, 30), 0)

    def test_short_month_prorates_by_deduction_payment_days(self):
        self.assertEqual(self.amount(self.EPF, 1968, 12), 787)
        self.assertEqual(self.amount(self.EPF, 1968, 30), 1968)
        self.assertEqual(salary_slip.prorated(3340, 12, 30), 1336)

    def test_fixed_deduction_is_not_prorated(self):
        self.assertEqual(self.amount(frappe._dict(depends_on_lwp=0), 200, 10), 200)
