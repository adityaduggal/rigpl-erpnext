"""Merges the one-day Shift Assignments into ranges of at most one calendar month (#196).

The first row of each run gets the last day of the run as end_date, and the other rows are
cancelled. No Version is added: it would be about 430k rows on prod.
"""
import frappe

from rigpl_erpnext.rigpl_erpnext.validations.shift_assignment import plan_month_runs
from rigpl_erpnext.utils.batch_write_utils import bulk_set_fields, bulk_update_rows
from rigpl_erpnext.utils.item_attribute_utils import chunks


def execute():
    employees = frappe.db.sql_list("""SELECT DISTINCT employee FROM `tabShift Assignment`
        WHERE docstatus = 1 AND status = 'Active'""")
    kept = cancelled = 0
    for employee_chunk in chunks(employees, 25):
        rows = frappe.get_all("Shift Assignment", filters={"docstatus": 1, "status": "Active",
            "employee": ("in", employee_chunk)}, fields=["name", "employee", "start_date", "end_date",
            "shift_type"], order_by="employee asc, start_date asc, name asc")
        by_employee = {}
        for row in rows:
            by_employee.setdefault(row.employee, []).append(row)
        runs = [run for emp_rows in by_employee.values() for run in plan_month_runs(emp_rows)]
        cancel = [name for run in runs for name in run["cancel"]]
        bulk_update_rows("Shift Assignment", {run["keep"]: {"end_date": run["end_date"]} for run in runs},
            update_modified=True)
        bulk_set_fields("Shift Assignment", {name: {"docstatus": 2} for name in cancel},
            {name: {"docstatus": 1} for name in cancel}, add_versions=False, update_modified=True)
        kept += len(rows) - len(cancel)
        cancelled += len(cancel)
    print("Shift Assignments: {0} kept, {1} cancelled".format(kept, cancelled))
