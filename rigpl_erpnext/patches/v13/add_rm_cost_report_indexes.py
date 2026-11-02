import frappe


def execute():
    """
    The RM Wastage Analysis and RM Cost of Items Made reports read the submitted Job Cards by
    `posting_date`, and their Stock Entries by `process_job_card`. `add_index` skips an index that
    exists.
    """
    frappe.db.add_index("Process Job Card RIGPL", ["docstatus", "posting_date"], "idx_pjc_docstatus_posting_date")
    frappe.db.add_index("Stock Entry", ["process_job_card"], "idx_ste_process_job_card")
    print("Job Card posting date and Stock Entry Job Card indexes are in place.")
