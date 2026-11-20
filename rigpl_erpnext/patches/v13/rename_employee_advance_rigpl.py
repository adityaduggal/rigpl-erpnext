import frappe

OLD, NEW = "Employee Advance", "Employee Advance RIGPL"

# (table, doctype column, name column). Only rows that point to the rigpl loans are changed: the name must be
# in the rigpl table. ERPNext links to its own Employee Advance stay as they are.
REFERENCES = (
    ("GL Entry", "voucher_type", "voucher_no"),
    ("GL Entry", "against_voucher_type", "against_voucher"),
    ("Comment", "reference_doctype", "reference_name"),
    ("Communication", "reference_doctype", "reference_name"),
    ("Communication Link", "link_doctype", "link_name"),
    ("Activity Log", "reference_doctype", "reference_name"),
    ("Version", "ref_doctype", "docname"),
    ("File", "attached_to_doctype", "attached_to_name"),
    ("ToDo", "reference_type", "reference_name"),
    ("DocShare", "share_doctype", "share_name"),
    ("Tag Link", "document_type", "document_name"),
    ("Document Follow", "ref_doctype", "ref_docname"),
    ("Deleted Document", "deleted_doctype", "deleted_name"),
    ("Employee Loan Detail", "parenttype", "parent"),
)
# Setup data of the DocType. In the module HR state it belongs to the ERPNext Employee Advance: not changed.
META_REFERENCES = (
    ("Custom DocPerm", "parent", ""),
    ("Property Setter", "doc_type", ""),
    ("Custom Field", "options", "and dt = 'Salary Detail' and fieldname = 'employee_loan'"),
    ("Report", "ref_doctype", "and name = 'Employee Loan Analysis'"),
)
META_TABLES = ("DocField", "DocPerm", "DocType Link", "DocType Action", "DocType State")
ERROR_TITLE = "Cannot Rename Employee Advance"


def execute():
    """
    Runs before migrate (#199, #237). The rigpl loan DocType had the same name as the ERPNext Employee Advance,
    so each migrate imported one JSON over the other. The rigpl data is found by its column total_loan,
    not by the module of the DocType row. Moves the rigpl loans to Employee Advance RIGPL.
    - Module HR-RIGPL (prod): renames the table, deletes the old DocType rows. The schema sync then makes
      both DocTypes: rigpl's on the renamed table, and ERPNext's on a new empty table.
    - Module HR (dev): the DocType row is ERPNext's already and stays. The empty RIGPL table is dropped,
      the table is renamed, the ERPNext table is made again and the ERPNext rows are copied back.
    The references change only for the rigpl names. frappe.rename_doc is not used: it would also change the
    ERPNext links to its own Employee Advance.
    All checks run before the first DDL, because DDL commits in MariaDB.
    """
    tables = frappe.db.get_tables(cached=False)
    if f"tab{OLD}" not in tables or not frappe.db.has_column(OLD, "total_loan"):
        return
    is_rigpl_module = frappe.db.get_value("DocType", OLD, "module") == "HR-RIGPL"
    names = check_before_rename(tables, is_rigpl_module)

    if f"tab{NEW}" in tables:
        frappe.db.sql_ddl(f"DROP TABLE `tab{NEW}`")
    frappe.db.sql_ddl(f"RENAME TABLE `tab{OLD}` TO `tab{NEW}`")
    if not is_rigpl_module:
        move_erpnext_rows_back()
    change_references(tables, is_rigpl_module)
    if is_rigpl_module:
        delete_old_doctype(tables)
    frappe.db.commit()
    frappe.cache().delete_value("db_tables")
    frappe.clear_cache()
    print(f"Moved {len(names)} loans from {OLD} to {NEW}")


def check_before_rename(tables, is_rigpl_module):
    """Returns the rigpl loan names. Throws when the data is not as expected, before any DDL."""
    if is_rigpl_module and f"tab{NEW}" in tables:
        frappe.throw(f"Table tab{NEW} exists already", title=ERROR_TITLE)
    if not is_rigpl_module and f"tab{NEW}" in tables and frappe.db.count(NEW):
        frappe.throw(f"Table tab{NEW} is not empty", title=ERROR_TITLE)

    names = set(frappe.db.sql_list("SELECT name FROM `tabEmployee Advance` WHERE IFNULL(employee, '') = ''"))
    detail_parents = set(frappe.db.sql_list(
        "SELECT DISTINCT parent FROM `tabEmployee Loan Detail` WHERE parenttype = %(old)s", {"old": OLD}))
    if names != detail_parents:
        frappe.throw(
            f"Loans without employee ({len(names)}) differ from Employee Loan Detail parents ({len(detail_parents)}). "
            f"Only in Employee Advance: {sorted(names - detail_parents)[:10]}. "
            f"Only in Employee Loan Detail: {sorted(detail_parents - names)[:10]}.", title=ERROR_TITLE)
    erpnext_rows = frappe.db.count(OLD) - len(names)
    print(f"Employee Advance: {len(names)} rigpl loans, {erpnext_rows} ERPNext rows, "
        f"{len(detail_parents)} Employee Loan Detail parents")
    return names


def move_erpnext_rows_back():
    """Makes the ERPNext table again, copies the ERPNext rows (employee set) into it and deletes them here."""
    frappe.clear_cache()
    frappe.db.updatedb(OLD)
    for table in (OLD, NEW):
        frappe.cache().hdel("table_columns", f"tab{table}")
    old_columns = set(frappe.db.get_table_columns(OLD))
    columns = ", ".join(f"`{col}`" for col in frappe.db.get_table_columns(NEW) if col in old_columns)
    frappe.db.sql(f"INSERT INTO `tab{OLD}` ({columns}) SELECT {columns} FROM `tab{NEW}` WHERE IFNULL(employee, '') != ''")
    print(f"Copied {frappe.db._cursor.rowcount} ERPNext rows back to {OLD}")
    frappe.db.sql(f"DELETE FROM `tab{NEW}` WHERE IFNULL(employee, '') != ''")


def change_references(tables, is_rigpl_module):
    """Runs after the rename, so the RIGPL table holds only the rigpl loans."""
    for doctype, column, name_column in REFERENCES:
        if f"tab{doctype}" not in tables or not frappe.db.has_column(doctype, column) \
                or not frappe.db.has_column(doctype, name_column):
            continue
        frappe.db.sql(f"""UPDATE `tab{doctype}` SET `{column}` = %(new)s
            WHERE `{column}` = %(old)s AND `{name_column}` IN (SELECT name FROM `tab{NEW}`)""",
            {"new": NEW, "old": OLD})
        print(f"{doctype}.{column}: {frappe.db._cursor.rowcount} rows")
    if not is_rigpl_module:
        return
    for doctype, column, condition in META_REFERENCES:
        if f"tab{doctype}" not in tables or not frappe.db.has_column(doctype, column):
            continue
        frappe.db.sql(f"UPDATE `tab{doctype}` SET `{column}` = %(new)s WHERE `{column}` = %(old)s {condition}",
            {"new": NEW, "old": OLD})
        print(f"{doctype}.{column}: {frappe.db._cursor.rowcount} rows")
    frappe.db.sql("UPDATE `__UserSettings` SET doctype = %(new)s WHERE doctype = %(old)s", {"new": NEW, "old": OLD})


def delete_old_doctype(tables):
    for doctype in META_TABLES:
        if f"tab{doctype}" in tables:
            frappe.db.sql(f"DELETE FROM `tab{doctype}` WHERE parent = %(old)s", {"old": OLD})
    frappe.db.sql("DELETE FROM `tabDocType` WHERE name = %(old)s", {"old": OLD})
