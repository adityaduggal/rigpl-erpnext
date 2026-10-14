import frappe
from frappe.query_builder import DocType

RENAMED_DOCTYPES = [
    # Renamed by erpnext.patches.v12_0.rename_account_type_doctype
    ("Account Type", "Bank Account Type"),
    ("Account Subtype", "Bank Account Subtype"),
    # Renamed by erpnext.patches.v12_0.rename_pos_closing_doctype
    ("POS Closing Voucher", "POS Closing Entry"),
    ("POS Closing Voucher Taxes", "POS Closing Entry Taxes"),
    ("POS Closing Voucher Details", "POS Closing Entry Detail"),
]


def execute():
    """
    Runs before migrate. A partial earlier migrate can leave both the old and the
    new table of a renamed DocType. The ERPNext rename patch then fails with
    "Table ... already exists". Drop the stale table, but only when all its rows
    are also in the other table.
    """
    tables = frappe.db.get_tables(cached=False)
    for old, new in RENAMED_DOCTYPES:
        if f"tab{old}" not in tables or f"tab{new}" not in tables:
            continue

        if frappe.db.exists("DocType", old):
            stale, source = new, old
        elif frappe.db.exists("DocType", new):
            stale, source = old, new
        else:
            frappe.throw(
                f"Tables tab{old} and tab{new} both exist, but neither DocType exists",
                title="Cannot Fix Duplicate Renamed DocType Tables",
            )

        missing = get_names(stale) - get_names(source)
        if missing:
            frappe.throw(
                f"Table tab{stale} has rows not in tab{source}: {', '.join(sorted(missing))}",
                title="Cannot Fix Duplicate Renamed DocType Tables",
            )

        frappe.db.sql_ddl(f"DROP TABLE `tab{stale}`")
        frappe.cache().delete_value("db_tables")
        print(f"Dropped stale table tab{stale}. tab{source} has all its rows.")


def get_names(doctype):
    table = DocType(doctype)
    return {row[0] for row in frappe.qb.from_(table).select(table.name).run(as_list=True)}
