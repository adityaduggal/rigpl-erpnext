# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import erpnext
import math
import datetime
from frappe.utils import money_in_words, flt, getdate
from erpnext.payroll.doctype.payroll_entry.payroll_entry import get_start_end_dates
from erpnext.hr.doctype.employee.employee import get_holiday_list_for_employee
from frappe.query_builder.functions import Count, Sum

from rigpl_erpnext.hr_rigpl.utils.hr_utils import get_half_day_fraction
from rigpl_erpnext.rigpl_erpnext.validations.salary_slip_gl import (  # noqa: F401 (patches import post_gl_entry)
    cancel_gl_entry, post_gl_entry, set_expense_claims_paid, validate_ec_posting)


def on_submit(doc, method):
    if doc.net_pay < 0:
        frappe.throw("Negative Net Pay Not Allowed for {0}".format(doc.name))
    # Mark the claims paid so that no new JV can be made for them
    set_expense_claims_paid(doc, paid=True)
    post_gl_entry(doc)


def on_cancel(doc, method):
    set_expense_claims_paid(doc, paid=False)
    cancel_gl_entry(doc)


def validate(doc, method):
    get_edc(doc)
    update_fields(doc)
    msd, med = get_month_dates(doc)
    get_loan_deduction(doc, msd, med)
    get_expense_claim(doc, med)
    calculate_net_salary(doc, msd, med)
    validate_ec_posting(doc)


def update_fields(doc):
    doc.letter_head = frappe.get_cached_value("Salary Structure", doc.salary_structure, "letter_head")
    doc.department = frappe.get_cached_value("Employee", doc.employee, "department")


def calculate_net_salary(doc, msd, med):
    gross_pay = 0
    tot_ded = 0
    tot_cont = 0
    tot_books = 0
    emp = frappe.get_doc("Employee", doc.employee)
    tdim, twd = get_total_days(doc, emp, msd, med)
    holiday_dates = get_holiday_dates(doc, msd, med, emp)
    holidays = flt(len(holiday_dates))
    hd_fraction = get_half_day_fraction()
    lwp, plw = get_leaves(doc, msd, med, holiday_dates, hd_fraction)
    doc.leave_without_pay = lwp
    doc.posting_date = med
    wd = twd - holidays  # total working days
    doc.total_days_in_month = tdim

    att = get_attendance_summary(doc.employee, msd, med)
    t_ot = att.overtime
    doc.total_overtime = t_ot
    worked = att.present + att.half_day * hd_fraction

    ual = twd - worked - lwp - holidays - plw

    if ual < 0:
        frappe.throw("Unauthorized Leave cannot be Negative for Employee {0}".format(
            doc.employee_name))

    # Paid leave is a payment day and earns its share of the holidays, as in ERPNext
    paydays = worked + plw + math.ceil((worked + plw) / wd * holidays)
    doc.payment_days = paydays

    if doc.change_deductions == 0:
        doc.payment_days_for_deductions = doc.payment_days

    if doc.payment_days_for_deductions == doc.payment_days:
        doc.change_deductions = 0

    doc.unauthorized_leaves = ual

    ot_ded = round(8 * ual, 1)
    if ot_ded > t_ot:
        ot_ded = (int(t_ot / 8)) * 8
    doc.overtime_deducted = ot_ded
    d_ual = int(ot_ded / 8)

    comps = get_component_flags([d.salary_component for d in doc.get("earnings") + doc.get("deductions")])

    # Calculate Earnings
    chk_ot = 0  # Check if there is an Overtime Rate
    for d in doc.get("earnings"):
        if d.salary_component == "Overtime Rate":
            chk_ot = 1

    for d in doc.get("earnings"):
        earn = comps[d.salary_component]
        if earn.depends_on_lwp == 1:
            d.depends_on_lwp = 1
        else:
            d.depends_on_lwp = 0

        if earn.based_on_earning:
            for d2 in doc.get("earnings"):
                # Calculate Overtime Value
                if earn.earning == d2.salary_component:
                    d.default_amount = flt(d2.amount) * t_ot
                    d.amount = flt(d2.amount) * (t_ot - ot_ded)
        else:
            if d.depends_on_lwp == 1 and earn.books == 0:
                if chk_ot == 1:
                    d.amount = round(flt(d.default_amount) *
                                     (paydays + d_ual) / tdim, 0)
                else:
                    d.amount = round(flt(d.default_amount)
                                     * (paydays) / tdim, 0)
            elif d.depends_on_lwp == 1 and earn.books == 1:
                d.amount = round(flt(d.default_amount) *
                                 flt(doc.payment_days_for_deductions) / tdim, 0)
            elif earn.manual == 1:
                d.default_amount = d.amount
            else:
                d.amount = d.default_amount
        if earn.books == 1:
            tot_books += flt(d.amount)

        if earn.only_for_deductions != 1:
            gross_pay += flt(d.amount)

    if gross_pay < 0:
        frappe.throw("Gross Pay Cannot be Less than Zero for Employee: {0}".format(
            emp.employee_name))

    # Calculate Deductions
    for d in doc.get("deductions"):
        if d.salary_component != 'Loan Deduction':
            d.amount = deduction_amount(d, comps[d.salary_component], doc.payment_days_for_deductions, tdim)
        tot_ded += flt(d.amount)

    # Calculate Contributions
    for c in doc.get("contributions"):
        c.amount = prorated(c.default_amount, doc.payment_days_for_deductions, tdim)
        tot_cont += c.amount

    doc.gross_pay = gross_pay
    doc.total_deduction = tot_ded
    doc.net_pay = doc.gross_pay - doc.total_deduction
    doc.rounded_cash = myround(flt(doc.net_pay) - flt(doc.actual_bank_salary))
    doc.rounded_total = flt(doc.actual_bank_salary) + flt(doc.rounded_cash)
    doc.net_pay_books = tot_books - doc.total_deduction

    company_currency = erpnext.get_company_currency(doc.company)
    doc.total_in_words = money_in_words(doc.rounded_total, company_currency)
    doc.total_ctc = doc.gross_pay + tot_cont


def deduction_amount(row, comp, payment_days, days_in_month):
    """ESI, EPF and LWF prorate by the deduction payment days. ESI (round_up) rounds up"""
    if comp.depends_on_lwp != 1:
        return row.amount
    if comp.round_up == 1:
        # v12 used int(x) + 1, which took 1 from a row with no amount
        return math.ceil(flt(flt(row.default_amount) * flt(payment_days) / days_in_month, 2))
    return prorated(row.default_amount, payment_days, days_in_month)


def prorated(amount, payment_days, days_in_month):
    return round(flt(amount) * flt(payment_days) / days_in_month, 0)


def get_attendance_summary(employee, start_date, end_date):
    """Present and Half Day counts and their total overtime"""
    att = frappe.qb.DocType("Attendance")
    rows = (
        frappe.qb.from_(att)
        .select(att.status, Count(att.name).as_("days"), Sum(att.overtime).as_("overtime"))
        .where((att.employee == employee) & (att.docstatus == 1)
            & att.attendance_date.between(start_date, end_date) & att.status.isin(["Present", "Half Day"]))
        .groupby(att.status)
    ).run(as_dict=True)
    by_status = {row.status: row for row in rows}
    present, half_day = by_status.get("Present", {}), by_status.get("Half Day", {})
    return frappe._dict(present=flt(present.get("days")), half_day=flt(half_day.get("days")),
        overtime=flt(present.get("overtime")) + flt(half_day.get("overtime")))


def get_component_flags(components):
    fields = ["name", "depends_on_lwp", "based_on_earning", "earning", "books", "manual",
        "only_for_deductions", "round_up"]
    rows = frappe.get_all("Salary Component", filters={"name": ("in", list(set(components)) or [""])},
        fields=fields)
    flags = {row.name: row for row in rows}
    missing = set(components) - set(flags)
    if missing:
        frappe.throw("Salary Component {0} does not exist".format(", ".join(sorted(missing))))
    return flags


def get_leaves(doc, start_date, end_date, holiday_dates, hd_fraction):
    """Returns (leave without pay, paid leave) days from the approved Leave Applications.

    LWP is never counted on a holiday (rigpl rule). Paid leave is counted on a holiday only if the
    Leave Type includes holidays (ERPNext rule). A half day counts 1 - hd_fraction.
    """
    leaves = get_approved_leaves(doc.employee, start_date, end_date)
    lwp = 0
    plw = 0
    for day in range((end_date - start_date).days + 1):
        date = start_date + datetime.timedelta(days=day)
        leave = next((la for la in leaves if la.from_date <= date <= la.to_date), None)
        if not leave:
            continue
        if leave.is_ppl:
            frappe.throw("Partially paid leave {0} ({1}) is not supported in the Salary Slip".format(
                leave.name, leave.leave_type))
        if date in holiday_dates and (leave.is_lwp or not leave.include_holiday):
            continue
        days = (1 - hd_fraction) if is_half_day_leave(leave, date) else 1
        if leave.is_lwp:
            lwp += days
        else:
            plw += days
    return flt(lwp), flt(plw)


def get_approved_leaves(employee, start_date, end_date):
    la = frappe.qb.DocType("Leave Application")
    lt = frappe.qb.DocType("Leave Type")
    return (
        frappe.qb.from_(la)
        .inner_join(lt).on(lt.name == la.leave_type)
        .select(la.name, la.leave_type, la.from_date, la.to_date, la.half_day, la.half_day_date,
            lt.is_lwp, lt.is_ppl, lt.include_holiday)
        .where((la.employee == employee) & (la.status == "Approved") & (la.docstatus == 1)
            & (la.from_date <= end_date) & (la.to_date >= start_date))
        .orderby(la.from_date).orderby(la.name)
    ).run(as_dict=True)


def is_half_day_leave(leave, date):
    # Same rule as ERPNext get_lwp_or_ppl_for_date
    return bool(leave.half_day) and (leave.half_day_date == date or leave.from_date == leave.to_date)


def get_holiday_dates(doc, start_date, end_date, emp):
    """Holiday dates of the employee's Holiday List between joining and relieving"""
    if emp.date_of_joining > start_date:
        start_date = emp.date_of_joining
    if emp.relieving_date and emp.relieving_date < end_date:
        end_date = emp.relieving_date
    if start_date > end_date:
        return set()

    holiday_list = get_holiday_list_for_employee(doc.employee)
    hol = frappe.qb.DocType("Holiday")
    rows = (
        frappe.qb.from_(hol)
        .select(hol.holiday_date)
        .where((hol.parent == holiday_list) & hol.holiday_date.between(start_date, end_date))
    ).run()
    return {row[0] for row in rows}


def get_total_days(doc, emp, msd, med):
    tdim = (med - msd).days + 1  # total days
    if emp.relieving_date is None:
        relieving_date = datetime.date(2099, 12, 31)
    else:
        relieving_date = emp.relieving_date

    if emp.date_of_joining >= msd:
        # Joining DATE IS THE First WORKING DAY
        twd = (med - emp.date_of_joining).days + 1
    elif relieving_date <= med:
        # RELIEVING DATE IS THE LAST WORKING DAY
        twd = (emp.relieving_date - msd).days + 1
    else:
        twd = tdim  # total days in a month
    doc.working_days = twd
    return tdim, twd


def get_expense_claim(doc, med):
    """Adds an earning row for each approved claim paid with salary that is not fully reimbursed"""
    ec = frappe.qb.DocType("Expense Claim")
    claims = (
        frappe.qb.from_(ec)
        .select(ec.name, ec.total_sanctioned_amount, ec.total_amount_reimbursed)
        .where((ec.docstatus == 1) & (ec.approval_status == "Approved") & (ec.pay_with_salary == 1)
            & (ec.total_amount_reimbursed < ec.total_sanctioned_amount) & (ec.posting_date <= med)
            & (ec.employee == doc.employee))
    ).run(as_dict=True)
    existing = {row.expense_claim for row in doc.earnings}
    for claim in claims:
        if claim.name not in existing:
            due = claim.total_sanctioned_amount - claim.total_amount_reimbursed
            doc.append("earnings", {"idx": len(doc.earnings) + 1, "depends_on_lwp": 0, "default_amount": due,
                "expense_claim": claim.name, "salary_component": "Expense Claim", "amount": due})


def get_loan_deduction(doc, msd, med):
    existing_loan = []
    for d in doc.deductions:
        existing_loan.append(d.employee_loan)
    # get total loan due for employee
    query = """SELECT el.name, eld.name, eld.emi, el.deduction_type, eld.loan_amount
    FROM `tabEmployee Advance` el, `tabEmployee Loan Detail` eld WHERE eld.parent = el.name AND el.docstatus = 1
    AND el.posting_date <= '%s' AND eld.employee = '%s'""" % (med, doc.employee)

    loan_list = frappe.db.sql(query, as_list=1)
    for i in loan_list:
        emi = i[2]
        total_loan = i[4]
        if i[0] not in existing_loan:
            # Check if the loan has already been deducted
            query = """SELECT SUM(ssd.amount) FROM `tabSalary Detail` ssd, `tabSalary Slip` ss
            WHERE ss.docstatus = 1 AND ssd.parent = ss.name AND ssd.employee_loan = '%s'
            AND ss.employee = '%s'""" % (i[0], doc.employee)
            deducted_amount = frappe.db.sql(query, as_list=1)

            if flt(total_loan) > flt(deducted_amount[0][0]):
                # Add deduction for each loan separately
                # Check if EMI is less than balance
                balance = flt(total_loan) - flt(deducted_amount[0][0])
                if balance > emi:
                    doc.append("deductions", {
                        "idx": len(doc.deductions) + 1, "depends_on_lwp": 0, "default_amount": balance,
                        "employee_loan": i[0], "salary_component": i[3], "amount": emi})
                else:
                    doc.append("deductions", {
                        "idx": len(doc.deductions) + 1, "d_depends_on_lwp": 0, "default_amount": balance,
                        "employee_loan": i[0], "salary_component": i[3], "amount": balance
                    })
    for d in doc.deductions:
        if d.employee_loan:
            total_given = frappe.db.sql("""SELECT eld.loan_amount FROM `tabEmployee Advance` el,
            `tabEmployee Loan Detail` eld WHERE eld.parent = el.name AND eld.employee = '%s'
            AND el.name = '%s'""" % (doc.employee, d.employee_loan), as_list=1)

            deducted = frappe.db.sql("""SELECT SUM(ssd.amount) FROM `tabSalary Detail` ssd, `tabSalary Slip` ss
            WHERE ss.docstatus = 1 AND ssd.parent = ss.name  AND ssd.employee_loan = '%s'
            AND ss.employee = '%s'""" % (d.employee_loan, doc.employee), as_list=1)
            balance = flt(total_given[0][0]) - flt(deducted[0][0])
            if balance < d.amount:
                frappe.throw(("Max deduction allowed {0} for Loan Deduction {1} check row # {2} in "
                              "Deduction Table").format(balance, d.employee_loan, d.idx))


def get_month_dates(doc):
    date_details = get_start_end_dates(
        doc.payroll_frequency, doc.start_date or doc.posting_date)
    doc.end_date = date_details.end_date
    med = date_details.end_date
    doc.start_date = date_details.start_date
    msd = date_details.start_date
    return msd, med


def get_edc(doc):
    """Rebuilds earnings, deductions and contributions from the applicable Salary Structure.

    Manual earnings and Loan Deduction rows keep the values the user entered.
    """
    doc.salary_structure = get_applicable_structure(doc)
    manual = get_manual_components([row.salary_component for row in doc.get("earnings")])
    manual_amounts = {row.salary_component: row.amount for row in doc.get("earnings")
        if row.salary_component in manual}
    loan_rows = [dict(salary_component=row.salary_component, default_amount=row.default_amount,
        amount=row.amount, idx=row.idx, employee_loan=row.employee_loan)
        for row in doc.get("deductions") if row.salary_component == "Loan Deduction"]

    doc.set("earnings", [])
    doc.set("deductions", [])
    doc.set("contributions", [])
    sstr = frappe.get_doc("Salary Structure", doc.salary_structure)
    get_from_sal_struct(doc, sstr, ["earnings", "deductions", "contributions"])

    for row in doc.earnings:
        if row.salary_component in manual_amounts:
            row.default_amount = row.amount = manual_amounts[row.salary_component]
    for row in loan_rows:
        doc.append("deductions", row)


def get_applicable_structure(doc):
    """Structure of the latest submitted SSA from on or before the start date, or the joining date if later"""
    doj = frappe.db.get_value("Employee", doc.employee, "date_of_joining")
    date_for_sstra = max(getdate(doj), getdate(doc.start_date))
    structure = frappe.get_all("Salary Structure Assignment", filters={"employee": doc.employee,
        "from_date": ("<=", date_for_sstra), "docstatus": 1}, pluck="salary_structure",
        order_by="from_date desc", limit=1)
    if not structure:
        frappe.throw("No Salary Structure Found for Employee {}".format(doc.employee))
    return structure[0]


def get_manual_components(components):
    if not components:
        return set()
    return set(frappe.get_all("Salary Component", filters={"name": ("in", list(set(components))), "manual": 1},
        pluck="name"))


def get_from_sal_struct(doc, salary_structure_doc, table_list):
    # v13 returns (data, default_data); the formulas need data
    data, _ = doc.get_data_for_eval()

    for table_name in table_list:
        for comp in salary_structure_doc.get(table_name):
            amount = doc.eval_condition_and_formula(comp, data)
            doc.append(table_name, {
                "salary_component": comp.salary_component,
                "default_amount": amount,
                "amount": amount,
                "idx": comp.idx,
                "depends_on_lwp": comp.depends_on_lwp
            })


def myround(x, base=5):
    return int(base * round(float(x) / base))
