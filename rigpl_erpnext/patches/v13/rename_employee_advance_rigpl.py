import frappe

OLD, NEW = "Employee Advance", "Employee Advance RIGPL"

# (table, column, extra condition). Only rows that point to the rigpl loans. ERPNext links to its own
# Employee Advance (Expense Claim Advance, Employee Advance Summary, HR workspace) are not changed.
REFERENCES = (
    ("GL Entry", "voucher_type", ""),
    ("GL Entry", "against_voucher_type", ""),
    ("Comment", "reference_doctype", ""),
    ("Communication", "reference_doctype", ""),
    ("Communication Link", "link_doctype", ""),
    ("Activity Log", "reference_doctype", ""),
    ("Version", "ref_doctype", ""),
    ("File", "attached_to_doctype", ""),
    ("ToDo", "reference_type", ""),
    ("DocShare", "share_doctype", ""),
    ("Tag Link", "document_type", ""),
    ("Document Follow", "ref_doctype", ""),
    ("Deleted Document", "deleted_doctype", ""),
    ("Employee Loan Detail", "parenttype", ""),
    ("Custom DocPerm", "parent", ""),
    ("Property Setter", "doc_type", ""),
    ("Custom Field", "options", "and dt = 'Salary Detail' and fieldname = 'employee_loan'"),
    ("Report", "ref_doctype", "and name = 'Employee Loan Analysis'"),
)
META_TABLES = ("DocField", "DocPerm", "DocType Link", "DocType Action", "DocType State")


def execute():
    """
    Runs before migrate (#199). The rigpl loan DocType had the same name as the ERPNext Employee Advance,
    so each migrate imported one JSON over the other. Renames the table and the references to
    Employee Advance RIGPL, and deletes the old DocType rows. The schema sync then makes both DocTypes:
    rigpl's on the renamed table, and ERPNext's on a new empty table.
    frappe.rename_doc is not used: it would also change the ERPNext links to its own Employee Advance.
    """
    if frappe.db.get_value("DocType", OLD, "module") != "HR-RIGPL":
        return
    tables = frappe.db.get_tables(cached=False)
    if f"tab{NEW}" in tables:
        frappe.throw(f"Table tab{NEW} exists already", title="Cannot Rename Employee Advance")

    frappe.db.sql_ddl(f"RENAME TABLE `tab{OLD}` TO `tab{NEW}`")
    for doctype, column, condition in REFERENCES:
        if f"tab{doctype}" not in tables or not frappe.db.has_column(doctype, column):
            continue
        frappe.db.sql(f"UPDATE `tab{doctype}` SET `{column}` = %(new)s WHERE `{column}` = %(old)s {condition}",
            {"new": NEW, "old": OLD})
        print(f"{doctype}.{column}: {frappe.db._cursor.rowcount} rows")
    frappe.db.sql("UPDATE `__UserSettings` SET doctype = %(new)s WHERE doctype = %(old)s", {"new": NEW, "old": OLD})

    for doctype in META_TABLES:
        if f"tab{doctype}" in tables:
            frappe.db.sql(f"DELETE FROM `tab{doctype}` WHERE parent = %(old)s", {"old": OLD})
    frappe.db.sql("DELETE FROM `tabDocType` WHERE name = %(old)s", {"old": OLD})
    frappe.db.commit()
    frappe.cache().delete_value("db_tables")
    frappe.clear_cache()
    print(f"Renamed {OLD} to {NEW}")
