import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count

# erpnext.patches.v12_0.rename_pos_closing_doctype deletes these only when the
# DocType "POS Closing Voucher" still exists. After a partial earlier migrate it
# does not, so these DocTypes and their tables are left behind.
ORPHAN_DOCTYPES = [
    "POS Closing Voucher Taxes",
    "POS Closing Voucher Details",
    "POS Closing Voucher Invoices",
]


def execute():
    tables = frappe.db.get_tables(cached=False)
    for doctype in ORPHAN_DOCTYPES:
        frappe.delete_doc("DocType", doctype, ignore_missing=True, force=True)

        # delete_doc does not drop the table. Drop it only when empty, so no data is lost.
        if f"tab{doctype}" not in tables:
            continue
        if count_rows(doctype):
            print(f"Kept table tab{doctype} because it has rows.")
        else:
            frappe.db.sql_ddl(f"DROP TABLE `tab{doctype}`")

    frappe.cache().delete_value("db_tables")


def count_rows(doctype):
    table = DocType(doctype)
    return frappe.qb.from_(table).select(Count("*")).run()[0][0]
