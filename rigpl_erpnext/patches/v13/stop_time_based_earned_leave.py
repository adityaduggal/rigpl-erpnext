import frappe

JOB = "erpnext.hr.utils.allocate_earned_leaves"


def execute():
    """
    #202: earned leave types get their credit from attendance (hr_rigpl/utils/leave_credit.py). Stops the
    ERPNext job that credits annual / 12 each month, so the two do not both credit. sync_jobs only inserts
    missing jobs, so a migrate does not start it again.
    """
    frappe.db.set_value("Scheduled Job Type", {"method": JOB}, "stopped", 1, update_modified=False)
