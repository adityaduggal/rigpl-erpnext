# Permissions in reports and whitelisted methods

Issue #206: HR script reports showed the Salary Slips, attendance and loans of employees in departments that the user could not read. Do not repeat this in any report, page or whitelisted method.

## What skips permissions

| Read | Role permissions | User Permissions | `permission_query_conditions` |
|---|---|---|---|
| `frappe.get_list` | yes | yes | yes |
| `frappe.get_all` | no | no | no |
| `frappe.qb` | no | no | no |
| `frappe.db.sql`, `frappe.db.get_value` | no | no | no |

The `roles` table of a Report controls only who can open the report. It does not filter the rows.

## Rules

1. Read the base DocType of a report with `frappe.get_list`. For HR reports this is Employee, and also the document of each row (Salary Slip, Leave Application, Salary Structure Assignment).
2. When a raw `frappe.qb` or SQL read is necessary (joins, `SUM`, child tables), run it only on the names that `get_list` returned (`.isin(chunk)`), or keep only the rows in `permitted_names(doctype, filters)` from `utils/report_utils.py`.
3. When a filter names 1 document (for example `employee` in a details view), check that the document is in the permitted list. If it is not, raise `frappe.PermissionError`.
4. Use `frappe.get_all` only for config and master data that is not sensitive, or after `frappe.has_permission`.
5. Whitelisted methods follow the same rules. Never pass `ignore_permissions=True` for data that comes back to the user.

## How User Permissions behave (v13)

- A User Permission on a tree DocType (Department) also permits its descendants.
- "Apply Strict User Permissions" is on (System Settings). A document with an empty link field (for example an empty `department`) is hidden from a user with a User Permission on that DocType. With the setting off, it is visible. Test fixtures must set the link fields that ERPNext fetches from the Employee.
- `get_list` also returns documents that are shared with the user.

## Test

Add a test that makes a user with the report role and a User Permission, and runs `execute()` with `frappe.set_user`. Assert that a row of the other value does not show. See `rigpl_erpnext/tests/test_report_permissions.py`.
