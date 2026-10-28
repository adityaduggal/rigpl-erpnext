import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count

PULL_LEADS = "IndiaMart Pull Leads"
JOB_TYPE = "indiamart.execute"
# Fields removed from RIGPL Settings. Frappe keeps the values of removed fields of a
# Single, and indiamart_api_key is a secret.
SETTINGS_FIELDS = ["indiamart_api_key", "indiamart_primary_mobile", "max_leads", "max_days"]


def execute():
    """
    IndiaMART retired the v1 lead API and the integration is no longer used (#157).
    Removes its DocType and the values, logs and secrets it left. Leads stay.
    """
    frappe.delete_doc("DocType", PULL_LEADS, ignore_missing=True, force=True)

    singles = DocType("Singles")
    # The collation is case-insensitive, so this also matches "Indiamart Pull Leads".
    delete_rows("Single values", singles, singles.doctype == PULL_LEADS)
    delete_rows(
        "RIGPL Settings values",
        singles,
        (singles.doctype == "RIGPL Settings") & singles.field.isin(SETTINGS_FIELDS),
    )

    job_log = DocType("Scheduled Job Log")
    delete_rows("Scheduled Job Logs", job_log, job_log.scheduled_job_type == JOB_TYPE)

    error_log = DocType("Error Log")
    delete_rows(
        "Error Logs",
        error_log,
        error_log.method.like("%indiamart%") | error_log.error.like("%indiamart%"),
    )


def delete_rows(label, table, condition):
    count = frappe.qb.from_(table).select(Count("*")).where(condition).run()[0][0]
    if count:
        frappe.qb.from_(table).delete().where(condition).run()
        print(f"Deleted {count} IndiaMART {label}.")
