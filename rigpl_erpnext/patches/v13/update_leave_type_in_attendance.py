import frappe

from rigpl_erpnext.utils.batch_write_utils import bulk_set_fields
from rigpl_erpnext.utils.item_attribute_utils import chunks


def execute():
    """
    Run by hand (not in patches.txt). Sets the leave type of each submitted On Leave
    Attendance that has none, from the approved Leave Application of that day. When more
    than one matches, the last modified one wins, as in the old per-row version.
    """
    attendance = frappe.get_all(
        "Attendance",
        fields=["name", "employee", "attendance_date"],
        filters={"docstatus": 1, "status": "On Leave", "leave_type": ("is", "not set")},
        order_by="attendance_date",
    )
    if not attendance:
        print("No On Leave Attendance without a leave type.")
        return

    leaves = get_leave_applications(
        {row.employee for row in attendance},
        min(row.attendance_date for row in attendance),
        max(row.attendance_date for row in attendance),
    )
    new_values, not_found = {}, []
    for row in attendance:
        leave_type = find_leave_type(leaves.get(row.employee, []), row.attendance_date)
        if leave_type:
            new_values[row.name] = {"leave_type": leave_type}
        else:
            not_found.append(row.name)

    bulk_set_fields("Attendance", new_values, {}, add_versions=False, update_modified=True)
    print(f"Attendance updated with a leave type: {len(new_values)} of {len(attendance)}.")
    if not_found:
        print(f"No Leave Application found for: {', '.join(not_found)}")


def get_leave_applications(employees, from_date, to_date):
    """{employee: [Leave Application]} of the approved ones that overlap the dates, last
    modified first."""
    by_employee = {}
    for chunk in chunks(employees):
        rows = frappe.get_all(
            "Leave Application",
            fields=["employee", "leave_type", "from_date", "to_date"],
            filters={
                "docstatus": 1,
                "status": "Approved",
                "employee": ("in", chunk),
                "from_date": ("<=", to_date),
                "to_date": (">=", from_date),
            },
            order_by="modified desc",
        )
        for row in rows:
            by_employee.setdefault(row.employee, []).append(row)
    return by_employee


def find_leave_type(leaves, date):
    for leave in leaves:
        if leave.from_date <= date <= leave.to_date:
            return leave.leave_type
    return None
