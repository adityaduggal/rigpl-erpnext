# Copyright (c) 2022, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt

from collections import Counter

import frappe
from frappe import _
from frappe.utils import flt, getdate
from frappe.query_builder.functions import IfNull

from rigpl_erpnext.utils.item_attribute_utils import chunks
from rigpl_erpnext.utils.report_utils import blank_zeros

DETAILED, BANK, SUMMARY, WITHOUT_SLIP = "Detailed", "Bank", "Summary", "Employees without Salary Slip"
EMP_FIELDS = ["name", "employee_name", "company_registered_with", "branch", "department", "designation",
    "bank_name", "bank_ac_no", "bank_ifsc_code", "date_of_joining", "relieving_date"]
EMP_FILTERS = ["branch", "department", "designation", "company_registered_with", "salary_mode"]
SLIP_FIELDS = ["name", "employee", "employee_name", "arrear_amount", "leave_encashment_amount", "gross_pay",
    "total_deduction", "net_pay", "rounded_total", "actual_bank_salary", "posting_date"]
NO_END = getdate("2099-12-31")


def execute(filters=None):
    filters = frappe._dict(filters or {})
    report_type = filters.get("report_type") or DETAILED
    employees = get_employees(filters)
    if report_type == WITHOUT_SLIP:
        return without_slip_columns(), get_employees_without_slip(filters, employees)

    slips = get_salary_slips(filters, employees)
    types, amounts = get_slip_details([ss.name for ss in slips], books=report_type in (BANK, SUMMARY))
    builder = ROW_BUILDERS[report_type]
    data = [blank_zeros(builder(ss, employees[ss.employee], types, amounts)) for ss in slips]
    return get_columns(report_type, types), data


def detailed_row(ss, emp, types, amounts):
    values = amounts.get(ss.name, {})
    total_cont = sum(flt(values.get(c)) for c in types.contribution)
    return (base_row(ss, emp) + [values.get(e) for e in types.earning]
        + [ss.arrear_amount, ss.leave_encashment_amount, ss.gross_pay] + [values.get(d) for d in types.deduction]
        + [ss.total_deduction, ss.net_pay] + [values.get(c) for c in types.contribution]
        + [total_cont, ss.rounded_total])


def bank_row(ss, emp, types, amounts):
    values = amounts.get(ss.name, {})
    book_gross, book_ded = books_totals(values, types)
    total_cont = sum(flt(values.get(c)) for c in types.contribution)
    return (base_row(ss, emp) + [values.get(e) for e in types.earning] + [None, None, book_gross]
        + [values.get(d) for d in types.deduction] + [book_ded, book_gross - book_ded]
        + [values.get(c) for c in types.contribution]
        + [total_cont, emp.bank_name, emp.bank_ac_no, emp.bank_ifsc_code])


def summary_row(ss, emp, types, amounts):
    book_gross, book_ded = books_totals(amounts.get(ss.name, {}), types)
    return base_row(ss, emp) + [ss.rounded_total, ss.actual_bank_salary, book_gross - book_ded,
        flt(ss.rounded_total) - flt(ss.actual_bank_salary)]


ROW_BUILDERS = {DETAILED: detailed_row, BANK: bank_row, SUMMARY: summary_row}


def get_columns(report_type, types):
    columns = [_("Employee") + ":Link/Employee:100", _("Employee Name") + "::140",
        _("Salary Slip") + ":Link/Salary Slip:80", _("Company") + "::50", _("Branch") + "::80",
        _("Department") + "::80", _("Designation") + "::80"]
    if report_type == SUMMARY:
        return columns + [_("Actual Payment") + ":Currency:100", _("Bank Payment") + ":Currency:100",
            _("Books Payment") + ":Currency:100", _("Balance Cash") + ":Currency:100"]

    columns += ([e + ":Currency:90" for e in types.earning]
        + ["Arrear Amt:Currency:90", "Leave Amt:Currency:90", "Gross Pay:Currency:100"]
        + [d + ":Currency:90" for d in types.deduction] + ["Total Deduction:Currency:100", "Net Pay:Currency:100"]
        + [c + ":Currency:90" for c in types.contribution] + ["Total Contribution:Currency:100"])
    if report_type == BANK:
        return columns + ["Bank Name::100", "Bank Account #::100", "Bank IFSC::100"]
    return columns + ["Rounded Pay:Currency:100"]


def without_slip_columns():
    return [_("Employee") + ":Link/Employee:100", _("Employee Name") + "::140", _("Company") + "::50",
        _("Branch") + "::100", _("Department") + "::100", _("Designation") + "::100",
        _("Joining Date") + ":Date:80", _("Relieving Date") + ":Date:80"]


def base_row(ss, emp):
    return [ss.employee, ss.employee_name, ss.name, emp.company_registered_with, emp.branch, emp.department,
        emp.designation]


def books_totals(values, types):
    return (sum(flt(values.get(e)) for e in types.earning), sum(flt(values.get(d)) for d in types.deduction))


def get_employees(filters):
    emp_filters = {"docstatus": 0}
    if filters.get("employee"):
        emp_filters["name"] = filters.employee
    emp_filters.update({f: filters[f] for f in EMP_FILTERS if filters.get(f)})
    employees = frappe.get_list("Employee", filters=emp_filters, fields=EMP_FIELDS, order_by="date_of_joining",
        limit_page_length=0)
    if not employees:
        frappe.throw(_("No Employees in the Given Criterion"))
    return {emp.name: emp for emp in employees}


def get_salary_slips(filters, employees):
    slips = []
    for names in chunks(employees):
        slips += frappe.get_list("Salary Slip", fields=SLIP_FIELDS, limit_page_length=0,
            filters=slip_filters(filters) + [["employee", "in", names]])
    if not slips:
        frappe.throw(_("No salary slip found between dates"))
    return sorted(slips, key=lambda ss: (ss.employee, ss.posting_date, ss.name))


def get_employees_without_slip(filters, employees):
    with_slip = set(frappe.get_list("Salary Slip", filters=slip_filters(filters), pluck="employee",
        limit_page_length=0))
    to_date = getdate(filters.to_date)
    data = []
    for emp in employees.values():
        relieving = emp.relieving_date or NO_END
        if emp.name not in with_slip and getdate(emp.date_of_joining) <= to_date and relieving >= to_date:
            data.append([emp.name, emp.employee_name, emp.company_registered_with or "None", emp.branch or "-",
                emp.department or "-", emp.designation or "-", emp.date_of_joining, relieving])
    return data


def slip_filters(filters):
    """get_list filters, so Salary Slip permissions and User Permissions apply (#206)"""
    conditions = [["posting_date", "between", [filters.from_date, filters.to_date]]]
    docstatus = {"Draft": 0, "Submitted": 1, "Cancelled": 2}.get(filters.get("docstatus"))
    if docstatus is not None:
        conditions.append(["docstatus", "=", docstatus])
    if filters.get("report_type") == WITHOUT_SLIP:
        conditions.append(["docstatus", "!=", 2])
    if filters.get("employee"):
        conditions.append(["employee", "=", filters.employee])
    return conditions


def get_slip_details(slip_names, books):
    """Column lists (components with a non-zero amount, in row order) and amounts per slip and component.

    Bank and Summary show only the books earnings and deductions; Detailed shows the non-books earnings
    and all deductions.
    """
    rows = []
    for names in chunks(slip_names):
        sd, sc = frappe.qb.DocType("Salary Detail"), frappe.qb.DocType("Salary Component")
        rows += (
            frappe.qb.from_(sd).inner_join(sc).on(sc.name == sd.salary_component)
            .select(sd.parent, sd.salary_component, sd.amount, sd.idx, IfNull(sc.books, 0).as_("books"),
                sc.is_earning, sc.is_deduction, sc.is_contribution)
            .where((sd.parenttype == "Salary Slip") & sd.parent.isin(names))
        ).run(as_dict=True)

    amounts, idx_counts = {}, {}
    for row in rows:
        values = amounts.setdefault(row.parent, {})
        values[row.salary_component] = flt(values.get(row.salary_component)) + flt(row.amount)
        if row.amount:
            idx_counts.setdefault(row.salary_component, Counter())[row.idx] += 1

    # A component can sit at a different idx in each structure; its most common idx sets the column order
    order = {c: (counts.most_common(1)[0][0], c) for c, counts in idx_counts.items()}
    flags = {row.salary_component: row for row in rows}

    def pick(test):
        return sorted((c for c in order if test(flags[c])), key=order.get)

    types = frappe._dict(
        earning=pick(lambda f: f.is_earning and f.books == int(books)),
        deduction=pick(lambda f: f.is_deduction and (f.books or not books)),
        contribution=pick(lambda f: f.is_contribution))
    return types, amounts
