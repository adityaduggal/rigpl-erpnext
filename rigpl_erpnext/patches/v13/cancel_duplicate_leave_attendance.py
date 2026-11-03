"""Cancels the second On Leave Attendance of a day (#196).

rigpl made one more On Leave Attendance on Leave Application submit, after the one that ERPNext
makes. For each employee and day with 2 or more submitted rows, the row with a Leave Application
stays (else the oldest), and the others are cancelled. Only On Leave rows are cancelled, so pay
does not change.
"""
import frappe

from rigpl_erpnext.utils.batch_write_utils import bulk_set_fields


def execute():
    rows = frappe.db.sql("""SELECT att.name, att.employee, att.attendance_date, att.status,
            att.leave_application, att.creation
        FROM `tabAttendance` att
        INNER JOIN (SELECT employee, attendance_date FROM `tabAttendance` WHERE docstatus = 1
            GROUP BY employee, attendance_date HAVING COUNT(*) > 1) dup
            ON dup.employee = att.employee AND dup.attendance_date = att.attendance_date
        WHERE att.docstatus = 1""", as_dict=1)
    to_cancel = get_rows_to_cancel(rows)
    bulk_set_fields("Attendance", {name: {"docstatus": 2} for name in to_cancel},
        {name: {"docstatus": 1} for name in to_cancel}, update_modified=True)
    print("Cancelled {0} duplicate On Leave Attendance".format(len(to_cancel)))


def get_rows_to_cancel(rows):
    by_day = {}
    for row in rows:
        by_day.setdefault((row.employee, row.attendance_date), []).append(row)
    to_cancel = []
    for day_rows in by_day.values():
        day_rows.sort(key=lambda row: (not row.leave_application, row.creation, row.name))
        for row in day_rows[1:]:
            assert row.status == "On Leave", "{0} is {1}, not On Leave".format(row.name, row.status)
            to_cancel.append(row.name)
    return to_cancel
