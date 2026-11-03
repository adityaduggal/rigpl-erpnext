# -*- coding: utf-8 -*-
"""GL of a Salary Slip: rigpl posts it on submit (ERPNext v13 posts payroll GL only from Payroll Entry)."""
from typing import Dict, List

import frappe
from frappe import _
from frappe.utils import flt, formatdate
from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries
from erpnext.accounts.utils import get_fiscal_years

COMPANY_FIELDS = ["cost_center", "default_payroll_payable_account", "round_off_account", "round_off_cost_center"]


def post_gl_entry(doc):
    SalarySlipGL(doc).post()


def cancel_gl_entry(doc):
    make_reverse_gl_entries(voucher_type="Salary Slip", voucher_no=doc.name)


def set_expense_claims_paid(doc, paid):
    for row in doc.earnings:
        if row.expense_claim:
            frappe.db.set_value("Expense Claim", row.expense_claim, {
                "total_amount_reimbursed": row.amount if paid else 0, "status": "Paid" if paid else "Unpaid"})


def validate_ec_posting(doc):
    """An Expense Claim paid with salary must credit the payroll payable account"""
    claims = [row.expense_claim for row in doc.earnings if row.expense_claim]
    if not claims:
        return
    payable = frappe.get_cached_value("Company", doc.company, "default_payroll_payable_account")
    for row in get_ec_gl_rows(claims):
        if flt(row.credit) > 0 and row.account != payable:
            frappe.throw("Expense Claim {0} in Salary Slip {1} is not posted correctly".format(
                row.voucher_no, doc.name))


class SalarySlipGL:
    def __init__(self, doc):
        self.doc = doc
        self.company = frappe.get_cached_value("Company", doc.company, COMPANY_FIELDS, as_dict=True)
        self.components = get_component_accounts(
            [row.salary_component for row in doc.earnings + doc.deductions + doc.get("contributions", [])])

    def post(self):
        self.post_unposted_expense_claims()
        make_gl_entries(self.build(), cancel=0, adv_adj=0)

    def build(self) -> List[frappe._dict]:
        """The GL map of the slip. It reads data but writes nothing."""
        self.fiscal_year = get_fy(self.doc)
        gl_map = self.earning_entries() + self.deduction_entries()
        if gl_map:
            gl_map += self.payable_entries()
        return gl_map + self.contribution_entries()

    def earning_entries(self):
        entries = []
        for row in self.doc.earnings:
            comp = self.components[row.salary_component]
            if row.amount != 0 and not row.expense_claim and comp.only_for_deductions != 1:
                entries.append(self.entry(row.salary_component, comp.account, debit=row.amount,
                    cost_center=self.company.cost_center, against=self.company.default_payroll_payable_account))
        return entries

    def deduction_entries(self):
        entries = []
        for row in self.doc.deductions:
            if flt(row.amount) <= 0:
                continue
            account = self.components[row.salary_component].account
            if row.employee_loan:
                entries.append(self.entry(row.salary_component, account, credit=row.amount,
                    party_type="Employee", party=self.doc.employee, against=row.employee_loan))
            else:
                entries.append(self.entry(row.salary_component, account, credit=row.amount,
                    against=self.company.default_payroll_payable_account))
        return entries

    def payable_entries(self):
        doc, payable = self.doc, self.company.default_payroll_payable_account
        ec_paid = sum(flt(row.amount) for row in doc.earnings if row.expense_claim and row.amount > 0)
        return [
            self.entry(None, payable, credit=doc.rounded_total - ec_paid, party_type="Employee",
                party=doc.employee, against=payable),
            self.entry(None, self.company.round_off_account, debit=doc.rounded_total - doc.net_pay,
                cost_center=self.company.round_off_cost_center, against=payable),
        ]

    def contribution_entries(self):
        entries = []
        for row in self.doc.get("contributions", []):
            if row.amount > 0:
                comp = self.components[row.salary_component]
                if not comp.liability_account:
                    frappe.throw(_("Set the Liability Account in Salary Component {0}").format(row.salary_component))
                entries.append(self.entry(row.salary_component, comp.account, debit=row.amount,
                    cost_center=self.company.cost_center, against=comp.liability_account))
                entries.append(self.entry(row.salary_component, comp.liability_account, credit=row.amount,
                    against=comp.account))
        return entries

    def entry(self, component, account, debit=0, credit=0, **fields):
        if not account:
            frappe.throw(_("Set the Account in Salary Component {0}").format(component))
        return frappe._dict(company=self.doc.company, posting_date=self.doc.posting_date,
            fiscal_year=self.fiscal_year, voucher_type="Salary Slip", voucher_no=self.doc.name, account=account,
            debit=flt(debit), debit_in_account_currency=flt(debit), credit=flt(credit),
            credit_in_account_currency=flt(credit), **fields)

    def post_unposted_expense_claims(self):
        claims = [row.expense_claim for row in self.doc.earnings if row.expense_claim and row.amount > 0]
        posted = {row.voucher_no for row in get_ec_gl_rows(claims)}
        for claim in claims:
            if claim not in posted:
                make_gl_entries(self.expense_claim_entries(frappe.get_doc("Expense Claim", claim)),
                    cancel=0, adv_adj=0)
                frappe.msgprint("Posted Expense Claim # {0}".format(claim))

    def expense_claim_entries(self, ec_doc):
        common = dict(company=ec_doc.company, posting_date=ec_doc.posting_date, fiscal_year=get_fy(ec_doc),
            voucher_type="Expense Claim", voucher_no=ec_doc.name)
        entries = [frappe._dict(common, account=exp.default_account, cost_center=self.company.cost_center,
            debit=flt(exp.sanctioned_amount), debit_in_account_currency=flt(exp.sanctioned_amount),
            against=ec_doc.employee) for exp in ec_doc.expenses]
        entries.append(frappe._dict(common, account=ec_doc.payable_account
            or self.company.default_payroll_payable_account, cost_center=ec_doc.cost_center
            or self.company.cost_center, party_type="Employee", party=ec_doc.employee,
            credit=flt(ec_doc.total_sanctioned_amount),
            credit_in_account_currency=flt(ec_doc.total_sanctioned_amount)))
        return entries


def get_fy(document):
    fiscal_years = get_fiscal_years(document.posting_date, company=document.company)
    if len(fiscal_years) > 1:
        frappe.throw(_("Multiple fiscal years exist for the date {0}. Please set company "
            "in Fiscal Year").format(formatdate(document.posting_date)))
    return fiscal_years[0][0]


def get_component_accounts(components) -> Dict[str, frappe._dict]:
    rows = frappe.get_all("Salary Component", filters={"name": ("in", list(set(components)) or [""])},
        fields=["name", "account", "liability_account", "only_for_deductions"])
    accounts = {row.name: row for row in rows}
    missing = set(components) - set(accounts)
    if missing:
        frappe.throw("Salary Component {0} does not exist".format(", ".join(sorted(missing))))
    return accounts


def get_ec_gl_rows(claims):
    """GL rows (not cancelled) of the given Expense Claims"""
    if not claims:
        return []
    return frappe.get_all("GL Entry", filters={"voucher_type": "Expense Claim", "voucher_no": ("in", claims),
        "docstatus": 1, "is_cancelled": 0}, fields=["voucher_no", "account", "credit"])
