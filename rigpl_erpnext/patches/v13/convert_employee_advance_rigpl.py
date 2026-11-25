import json
import os

import frappe
from frappe.modules.utils import sync_customizations_for_doctype
from frappe.utils import escape_html, flt, now

from rigpl_erpnext.utils.batch_write_utils import bulk_insert_rows

OLD, NEW, JOURNAL = "Employee Advance RIGPL", "Employee Advance", "Journal Entry"
ERROR_TITLE = "Cannot Convert Employee Advance RIGPL"

ADVANCE_FIELDS = (
    "name", "creation", "modified", "modified_by", "owner", "docstatus", "idx", "employee", "employee_name",
    "department", "posting_date", "currency", "exchange_rate", "repay_unclaimed_amount_from_salary", "purpose",
    "advance_amount", "deduction_type", "emi", "repayment_period", "status", "company", "advance_account",
)
JOURNAL_FIELDS = (
    "name", "creation", "modified", "modified_by", "owner", "docstatus", "voucher_type", "posting_date", "company",
    "title", "user_remark", "total_debit", "total_credit",
)
ACCOUNT_FIELDS = (
    "name", "creation", "modified", "modified_by", "owner", "docstatus", "parent", "parentfield", "parenttype", "idx",
    "account", "account_type", "account_currency", "cost_center", "party_type", "party", "debit", "credit",
    "debit_in_account_currency", "credit_in_account_currency", "exchange_rate", "reference_type", "reference_name",
    "against_account", "is_advance",
)
COMMENT_FIELDS = (
    "name", "creation", "modified", "modified_by", "owner", "docstatus", "comment_type", "reference_doctype",
    "reference_name", "comment_email", "content",
)
# The new Employee Advance name: the same text as the SQL expression NEW_NAME_SQL.
NEW_NAME_SQL = "CONCAT(d.parent, '-Row-', d.idx)"
# The Employee Loan Detail row of an old doc, joined by the old doc name and the employee.
DETAIL_JOIN = f"""JOIN `tabEmployee Loan Detail` d ON d.parenttype = '{OLD}' AND d.parent = {{parent}}
    AND d.employee = {{employee}} JOIN `tab{OLD}` p ON p.name = d.parent AND p.name IN %(names)s"""


def execute():
    """
    Moves every old loan (Employee Advance RIGPL, #199) to ERPNext (#230):
    - one Employee Advance per loan row, named `<old name>-Row-<idx>`;
    - one Journal Entry per old doc with the old name. ERPNext v13 Employee Advance posts no GL: its paid
      amount is the sum of the GL debits against it, and a Journal Entry posts them;
    - the GL rows, the Salary Slip GL rows and Salary Detail.employee_loan point to the new advances;
    - the files of an old doc move to its first advance (Row 1), the other advances get a Comment about it.
    Submitted and cancelled docs are converted (the cancelled ones with no GL). A draft is not: enter it again.
    Safe to run again: a converted old doc has a Journal Entry with its name, and a moved file is no longer
    attached to the old doc. The files step also runs when there is nothing left to convert.
    """
    if f"tab{OLD}" not in frappe.db.get_tables(cached=False):
        return
    names = frappe.db.sql_list(f"""SELECT name FROM `tab{OLD}` p WHERE docstatus IN (1, 2)
        AND NOT EXISTS (SELECT 1 FROM `tabJournal Entry` j WHERE j.name = p.name) ORDER BY name""")
    if names:
        sync_employee_advance_fields()
    try:
        if names:
            convert(names)
        link_attachments(frappe.db.sql_list(f"SELECT name FROM `tab{OLD}` WHERE docstatus IN (1, 2)"))
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        raise


def sync_employee_advance_fields():
    """
    v13 migrate runs the patches before it syncs the custom fields, so the loan columns do not exist yet.
    The DocType is reloaded first: the custom sync skips a DocType that has no row. The DDL commits.
    """
    frappe.reload_doc("hr", "doctype", "employee_advance")
    folder = frappe.get_app_path("rigpl_erpnext", "rigpl_erpnext", "custom")
    with open(os.path.join(folder, "employee_advance.json")) as f:
        sync_customizations_for_doctype(json.load(f), folder, "employee_advance.json")


def convert(names):
    """Converts the old docs in one transaction, no commit. Throws when a check fails."""
    names = tuple(names)
    docs, rows = read_old_docs(names)
    expected = expected_balances(names, rows)
    ledger = ledger_balances(docs, rows)

    companies = company_by_doc(names, docs)
    bulk_insert_rows(NEW, ADVANCE_FIELDS, advance_rows(docs, rows, companies))
    journal_rows, account_rows = journal_entry_rows(docs, rows, companies)
    bulk_insert_rows(JOURNAL, JOURNAL_FIELDS, journal_rows)
    bulk_insert_rows("Journal Entry Account", ACCOUNT_FIELDS, account_rows)
    print(f"Inserted {len(rows)} Employee Advance and {len(docs)} Journal Entry")

    point_references_to_new_advances(names)
    set_paid_return_and_status([new_name(row.parent, row.idx) for row in rows])
    check_conversion(names, docs, rows, expected, ledger)
    print(f"Converted {len(docs)} Employee Advance RIGPL docs to {len(rows)} Employee Advance")


def new_name(old_name, idx):
    return f"{old_name}-Row-{idx}"


def read_old_docs(names):
    docs = frappe.db.sql(f"""SELECT name, docstatus, posting_date, debit_account, credit_account, deduction_type,
        company, owner, creation, modified, modified_by, total_loan FROM `tab{OLD}` WHERE name IN %(names)s
        ORDER BY name""", {"names": names}, as_dict=True)
    rows = frappe.db.sql(f"""SELECT d.parent, d.idx, d.employee, d.employee_name, d.loan_amount, d.emi,
        d.repayment_period, e.department FROM `tabEmployee Loan Detail` d
        LEFT JOIN `tabEmployee` e ON e.name = d.employee
        WHERE d.parenttype = '{OLD}' AND d.parent IN %(names)s ORDER BY d.parent, d.idx""",
        {"names": names}, as_dict=True)
    return docs, rows


def company_by_doc(names, docs):
    """The old docs have no company: take it from their GL rows, else the default company."""
    from_gl = dict(frappe.db.sql(f"""SELECT voucher_no, MAX(company) FROM `tabGL Entry`
        WHERE voucher_type = '{OLD}' AND voucher_no IN %(names)s GROUP BY voucher_no""", {"names": names}))
    default = frappe.db.get_single_value("Global Defaults", "default_company")
    return {doc.name: doc.company or from_gl.get(doc.name) or default for doc in docs}


def advance_rows(docs, rows, companies):
    doc_by_name = {doc.name: doc for doc in docs}
    result = []
    for row in rows:
        doc = doc_by_name[row.parent]
        result.append((new_name(row.parent, row.idx), doc.creation, doc.modified, doc.modified_by, doc.owner,
            doc.docstatus, 0, row.employee, row.employee_name, row.department, doc.posting_date, "INR", 1, 1,
            f"Loan {row.parent}", row.loan_amount, doc.deduction_type, row.emi, row.repayment_period,
            "Cancelled" if doc.docstatus == 2 else "Unpaid", companies[doc.name], doc.debit_account))
    return result


def journal_entry_rows(docs, rows, companies):
    """One Journal Entry per old doc: a debit row per loan row, one credit row on the credit account."""
    account_types = {acc.name: acc.account_type for acc in frappe.get_all("Account",
        filters={"name": ["in", list({doc.debit_account for doc in docs} | {doc.credit_account for doc in docs})]},
        fields=["name", "account_type"])}
    rows_by_doc = {}
    for row in rows:
        rows_by_doc.setdefault(row.parent, []).append(row)
    journal_rows, account_rows = [], []
    for doc in docs:
        company = companies[doc.name]
        cost_center = frappe.get_cached_value("Company", company, "cost_center")
        voucher_type = {"Bank": "Bank Entry", "Cash": "Cash Entry"}.get(account_types.get(doc.credit_account),
            "Journal Entry")
        total = sum(flt(row.loan_amount) for row in rows_by_doc[doc.name])
        journal_rows.append((doc.name, doc.creation, doc.modified, doc.modified_by, doc.owner, doc.docstatus,
            voucher_type, doc.posting_date, company, doc.credit_account, f"Converted from {OLD} {doc.name}",
            total, total))
        common = (doc.creation, doc.modified, doc.modified_by, doc.owner, doc.docstatus, doc.name,
            "accounts", JOURNAL)
        for idx, row in enumerate(rows_by_doc[doc.name], 1):
            account_rows.append((frappe.generate_hash(length=10), *common, idx, doc.debit_account,
                account_types.get(doc.debit_account), "INR", cost_center, "Employee", row.employee,
                row.loan_amount, 0, row.loan_amount, 0, 1, NEW, new_name(row.parent, row.idx),
                doc.credit_account, "Yes"))
        account_rows.append((frappe.generate_hash(length=10), *common, len(rows_by_doc[doc.name]) + 1,
            doc.credit_account, account_types.get(doc.credit_account), "INR", cost_center, None, None, 0, total,
            0, total, 1, None, None, doc.debit_account, "No"))
    return journal_rows, account_rows


def point_references_to_new_advances(names):
    """
    One UPDATE with a join per table, so each row is read before it is changed: a new name can never be
    matched as an old name. Only the docs in `names` are changed.
    """
    gl_join = DETAIL_JOIN.format(parent="g.voucher_no", employee="g.party")
    slip_join = DETAIL_JOIN.format(parent="g.against", employee="g.party")
    detail_join = DETAIL_JOIN.format(parent="sd.employee_loan", employee="ss.employee")
    statements = (
        ("GL Entry (loan debit rows)", f"""UPDATE `tabGL Entry` g {gl_join}
            SET g.voucher_type = '{JOURNAL}', g.against_voucher_type = '{NEW}', g.against_voucher = {NEW_NAME_SQL}
            WHERE g.voucher_type = '{OLD}' AND g.party IS NOT NULL"""),
        ("GL Entry (loan credit rows)", f"""UPDATE `tabGL Entry` SET voucher_type = '{JOURNAL}'
            WHERE voucher_type = '{OLD}' AND voucher_no IN %(names)s"""),
        ("GL Entry (Salary Slip rows)", f"""UPDATE `tabGL Entry` g {slip_join}
            SET g.against_voucher_type = '{NEW}', g.against_voucher = {NEW_NAME_SQL}, g.against = {NEW_NAME_SQL}
            WHERE g.voucher_type = 'Salary Slip'"""),
        ("Salary Detail.employee_loan", f"""UPDATE `tabSalary Detail` sd
            JOIN `tabSalary Slip` ss ON ss.name = sd.parent AND sd.parenttype = 'Salary Slip' {detail_join}
            SET sd.employee_loan = {NEW_NAME_SQL}"""),
    )
    for label, query in statements:
        frappe.db.sql(query, {"names": names})
        print(f"{label}: {frappe.db._cursor.rowcount} rows")


def set_paid_return_and_status(new_names):
    """The same sums as Employee Advance.set_total_advance_paid and set_status, in one query for all."""
    new_names = tuple(new_names)
    frappe.db.sql(f"""UPDATE `tab{NEW}` a JOIN (
            SELECT against_voucher, SUM(debit) paid,
                SUM(CASE WHEN voucher_type != 'Expense Claim' THEN credit ELSE 0 END) returned
            FROM `tabGL Entry` WHERE against_voucher_type = '{NEW}' AND against_voucher IN %(new_names)s
                AND party_type = 'Employee' AND docstatus = 1 AND is_cancelled = 0
            GROUP BY against_voucher) g ON g.against_voucher = a.name
        SET a.paid_amount = g.paid, a.return_amount = g.returned""", {"new_names": new_names})
    frappe.db.sql(f"""UPDATE `tab{NEW}` SET status = CASE
            WHEN docstatus = 2 THEN 'Cancelled'
            WHEN return_amount > 0 AND ROUND(return_amount, 2) = ROUND(paid_amount, 2) THEN 'Returned'
            WHEN paid_amount > 0 AND ROUND(advance_amount, 2) = ROUND(paid_amount, 2) THEN 'Paid'
            ELSE 'Unpaid' END
        WHERE name IN %(new_names)s""", {"new_names": new_names})


def expected_balances(names, rows):
    """Per employee: loans of the submitted old docs less the Salary Slip GL credits against them."""
    submitted = {doc_name for doc_name in frappe.db.sql_list(
        f"SELECT name FROM `tab{OLD}` WHERE docstatus = 1 AND name IN %(names)s", {"names": names})}
    expected = {}
    for row in rows:
        if row.parent in submitted:
            expected[row.employee] = expected.get(row.employee, 0) + flt(row.loan_amount)
    for party, credit in frappe.db.sql("""SELECT party, SUM(credit) FROM `tabGL Entry`
            WHERE voucher_type = 'Salary Slip' AND against IN %(names)s AND party_type = 'Employee'
            AND docstatus = 1 AND is_cancelled = 0 GROUP BY party""", {"names": names}):
        expected[party] = expected.get(party, 0) - flt(credit)
    return expected


def ledger_balances(docs, rows):
    """Per employee: the GL balance of the advance accounts."""
    return dict(frappe.db.sql("""SELECT party, SUM(debit - credit) FROM `tabGL Entry`
        WHERE account IN %(accounts)s AND party_type = 'Employee' AND party IN %(employees)s
        AND docstatus = 1 AND is_cancelled = 0 GROUP BY party""",
        {"accounts": tuple({doc.debit_account for doc in docs}), "employees": tuple({row.employee for row in rows})}))


def check_conversion(names, docs, rows, expected, ledger):
    """Throws when the converted data differs from the old data. The caller rolls back."""
    new_names = tuple(new_name(row.parent, row.idx) for row in rows)
    problems = []
    for doctype, count in ((NEW, len(rows)), (JOURNAL, len(docs))):
        found = frappe.db.sql(f"SELECT COUNT(*) FROM `tab{doctype}` WHERE name IN %(names)s",
            {"names": new_names if doctype == NEW else names})[0][0]
        if found != count:
            problems.append(f"{doctype}: {found} found, {count} expected")

    after = frappe.db.sql(f"""SELECT employee, SUM(paid_amount - return_amount) FROM `tab{NEW}`
        WHERE docstatus = 1 AND name IN %(names)s GROUP BY employee""", {"names": new_names})
    after = {employee: flt(balance) for employee, balance in after}
    for employee in set(expected) | set(after):
        if round(expected.get(employee, 0) - after.get(employee, 0), 2):
            problems.append(f"{employee}: old balance {expected.get(employee, 0)}, new {after.get(employee, 0)}")

    ledger_after = ledger_balances(docs, rows)
    for employee in set(ledger) | set(ledger_after):
        if round(flt(ledger.get(employee)) - flt(ledger_after.get(employee)), 2):
            problems.append(f"{employee}: GL balance changed from {ledger.get(employee)} to {ledger_after.get(employee)}")

    old_pointers = frappe.db.sql(f"""SELECT COUNT(*) FROM `tabGL Entry`
        WHERE (voucher_type = '{OLD}' AND voucher_no IN %(names)s)
        OR (voucher_type = 'Salary Slip' AND against IN %(names)s)""", {"names": names})[0][0]
    old_pointers += frappe.db.sql("SELECT COUNT(*) FROM `tabSalary Detail` WHERE employee_loan IN %(names)s",
        {"names": names})[0][0]
    if old_pointers:
        problems.append(f"{old_pointers} GL or Salary Detail rows still point to an old name")
    if problems:
        frappe.throw("<br>".join(problems[:20]), title=ERROR_TITLE)


def link_attachments(names):
    """
    Moves the files of the old docs to their first advance (Row 1): one File record and one physical file.
    The other advances of the doc get a Comment that names the file. No commit, throws when a check fails.
    """
    if not names:
        return
    names = tuple(names)
    # Not filtered by `IN names` in SQL: with the join below MariaDB returns no rows for a long IN list.
    in_scope = set(names)
    files = [file for file in frappe.db.sql(f"""SELECT f.name, f.file_name, f.file_url, f.owner,
        f.attached_to_name old_name, fr.idx first_row FROM `tabFile` f
        JOIN (SELECT parent, MIN(idx) idx FROM `tabEmployee Loan Detail` WHERE parenttype = '{OLD}'
            GROUP BY parent) fr ON fr.parent = f.attached_to_name
        JOIN `tab{NEW}` a ON a.name = CONCAT(fr.parent, '-Row-', fr.idx)
        WHERE f.attached_to_doctype = '{OLD}'""", as_dict=True) if file.old_name in in_scope]
    if not files:
        return
    rows_by_doc = {}
    for old_name, idx in frappe.db.sql(f"""SELECT parent, idx FROM `tabEmployee Loan Detail`
            WHERE parenttype = '{OLD}' AND parent IN %(names)s ORDER BY parent, idx""", {"names": names}):
        rows_by_doc.setdefault(old_name, []).append(idx)

    comments = []
    for file in files:
        first = new_name(file.old_name, file.first_row)
        link = f"<a href='{escape_html(file.file_url)}' target='_blank'>{escape_html(file.file_name)}</a>"
        for idx in rows_by_doc[file.old_name]:
            if idx != file.first_row:
                comments.append((frappe.generate_hash(length=10), now(), now(),
                    file.owner, file.owner, 0, "Comment", NEW, new_name(file.old_name, idx), file.owner,
                    f"Attachment of this loan is on {first}: {link}"))
    frappe.db.sql(f"""UPDATE `tabFile` f
        JOIN (SELECT parent, MIN(idx) idx FROM `tabEmployee Loan Detail` WHERE parenttype = '{OLD}'
            GROUP BY parent) fr ON fr.parent = f.attached_to_name
        SET f.attached_to_doctype = '{NEW}', f.attached_to_name = CONCAT(fr.parent, '-Row-', fr.idx)
        WHERE f.name IN %(files)s""", {"files": tuple(file.name for file in files)})
    moved = frappe.db._cursor.rowcount
    bulk_insert_rows("Comment", COMMENT_FIELDS, comments)
    print(f"Moved {moved} files to the first Employee Advance, {len(comments)} Comments for the other rows")
    if moved != len(files):
        frappe.throw(f"{moved} files moved, {len(files)} expected", title=ERROR_TITLE)
