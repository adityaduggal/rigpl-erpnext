"""
The All and Guest roles apply to every user or website visitor. Over several ERPNext
versions they collected rights such as create, delete, report and share. This policy
limits them to read, and runs after each migrate and each day so that updates or manual
changes in Role Permission Manager cannot bring the rights back.
"""

import frappe
from frappe.permissions import setup_custom_perms
from frappe.query_builder import DocType
from frappe.query_builder.functions import IfNull

CAPPED_ROLES = ("All", "Guest")

# All rights except read. if_owner is a condition on read, not a right, so it is kept.
EXTRA_PTYPES = (
    "write",
    "create",
    "delete",
    "submit",
    "cancel",
    "amend",
    "report",
    "export",
    "import",
    "share",
    "print",
    "email",
    "set_user_permissions",
)

# Desk users need write and create on these through the All role, for example to attach
# files (frappe.handler.upload_file checks File create for logged-in users).
DESK_DOCTYPES = {
    "File",
    "Event",
    "Note",
    "ToDo",
    "Communication",
    "Notification Settings",
    "Kanban Board",
    "List Filter",
    "Dashboard Chart",
    "Dashboard Settings",
    "Tag",
    "Tag Link",
}
DESK_PTYPES = ("write", "create")


def enforce_role_permission_policy():
    changes = delete_orphan_permissions()
    changes += customise_standard_violations()
    changes += strip_capped_role_rights()
    if not changes:
        return

    frappe.clear_cache()
    message = "\n".join(changes + get_guest_read_doctypes())
    print(message)
    frappe.log_error(message, "Role permission policy applied")


def delete_orphan_permissions():
    """Role Permission Manager fails on rows whose DocType, Page or Report was deleted."""
    changes = []
    doctype = DocType("DocType")
    for perm_doctype in ("Custom DocPerm", "DocPerm"):
        perm = DocType(perm_doctype)
        orphan = perm.parent.notin(frappe.qb.from_(doctype).select(doctype.name))
        rows = frappe.qb.from_(perm).select(perm.parent, perm.role).where(orphan).run()
        if rows:
            frappe.qb.from_(perm).delete().where(orphan).run()
        for parent, role in rows:
            changes.append(f"Deleted {perm_doctype} of deleted DocType {parent} for {role}.")

    custom_role = DocType("Custom Role")
    page = DocType("Page")
    report = DocType("Report")
    orphan = (
        (IfNull(custom_role.page, "") != "")
        & custom_role.page.notin(frappe.qb.from_(page).select(page.name))
    ) | (
        (IfNull(custom_role.report, "") != "")
        & custom_role.report.notin(frappe.qb.from_(report).select(report.name))
    )
    rows = (
        frappe.qb.from_(custom_role).select(custom_role.page, custom_role.report).where(orphan)
    ).run()
    if rows:
        frappe.qb.from_(custom_role).delete().where(orphan).run()
    for page_name, report_name in rows:
        changes.append(f"Deleted Custom Role of deleted Page {page_name} or Report {report_name}.")
    return changes


def customise_standard_violations():
    """
    Standard DocPerm rows are reset on each migrate, so they cannot be changed. Copies
    them to Custom DocPerm, which Frappe then uses instead, so that the next step can
    strip them. These doctypes no longer get permission changes from ERPNext updates.
    """
    doctypes_with_custom_perms = set(
        frappe.get_all("Custom DocPerm", distinct=True, pluck="parent")
    )
    standard_perms = frappe.get_all(
        "DocPerm",
        filters={"role": ("in", CAPPED_ROLES)},
        fields=["parent", "role", *EXTRA_PTYPES],
    )
    doctypes = sorted(
        {
            row.parent
            for row in standard_perms
            if row.parent not in doctypes_with_custom_perms and get_rights_to_remove(row)
        }
    )
    for doctype in doctypes:
        setup_custom_perms(doctype)
    return [f"Copied standard permissions of {doctype} to Custom DocPerm." for doctype in doctypes]


def strip_capped_role_rights():
    """
    Removes all rights except read. An All row at level 0 that has only read changes to
    select, unless the standard DocPerm also gives All read (for example Report), because
    the desk needs those.
    """
    framework_defaults = set(
        frappe.get_all(
            "DocPerm",
            filters={"role": "All", "permlevel": 0, "read": 1},
            pluck="parent",
        )
    )
    custom_perm = DocType("Custom DocPerm")
    rows = (
        frappe.qb.from_(custom_perm)
        .select("name", "parent", "role", "permlevel", "read", *EXTRA_PTYPES)
        .where(custom_perm.role.isin(CAPPED_ROLES))
        .orderby(custom_perm.parent)
        .run(as_dict=True)
    )

    changes = []
    names_by_ptype = {}
    names_to_select = []
    for row in rows:
        removed = get_rights_to_remove(row)
        for ptype in removed:
            names_by_ptype.setdefault(ptype, []).append(row.name)
        if removed:
            label = f"{row.role} on {row.parent} (level {row.permlevel})"
            changes.append(f"{label}: removed {', '.join(removed)}.")

        if (
            row.role == "All"
            and row.read
            and not row.permlevel
            and row.parent not in DESK_DOCTYPES
            and row.parent not in framework_defaults
        ):
            names_to_select.append(row.name)
            changes.append(f"All on {row.parent}: changed read to select.")

    for ptype, names in names_by_ptype.items():
        frappe.qb.update(custom_perm).set(custom_perm[ptype], 0).where(
            custom_perm.name.isin(names)
        ).run()
    if names_to_select:
        (
            frappe.qb.update(custom_perm)
            .set(custom_perm.read, 0)
            .set(custom_perm["select"], 1)
            .where(custom_perm.name.isin(names_to_select))
        ).run()
    return changes


def get_rights_to_remove(row):
    allowed = DESK_PTYPES if row.role == "All" and row.parent in DESK_DOCTYPES else ()
    return [ptype for ptype in EXTRA_PTYPES if row.get(ptype) and ptype not in allowed]


def get_guest_read_doctypes():
    """Guest read is kept because website pages may need it. Listed so an admin can review it."""
    doctypes = frappe.get_all(
        "Custom DocPerm", filters={"role": "Guest", "read": 1}, pluck="parent"
    )
    return [f"Review: Guest can read {doctype}." for doctype in doctypes]
