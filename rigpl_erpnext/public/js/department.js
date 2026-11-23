// Keeps the approver tables the same while the user edits them (#238).
// __onload.approver_tables (validations/department.py onload) lists the tables of
// RIGPL Settings > Department Approvers that must be the same.
const RIGPL_APPROVER_TABLES = ["leave_approvers", "expense_approvers", "shift_request_approver"];

function rigpl_sync_approvers(frm, source) {
    const tables = (frm.doc.__onload || {}).approver_tables || [];
    if (frm.doctype !== "Department" || !tables.includes(source)) return;
    const approvers = (frm.doc[source] || []).map((row) => row.approver);
    tables.filter((table) => table !== source).forEach((table) => {
        frm.clear_table(table);
        approvers.forEach((approver) => frm.add_child(table, { approver: approver }));
        frm.refresh_field(table);
    });
}

const rigpl_approver_events = {
    approver: function(frm, cdt, cdn) {
        rigpl_sync_approvers(frm, locals[cdt][cdn].parentfield);
    },
};
RIGPL_APPROVER_TABLES.forEach((table) => {
    rigpl_approver_events[table + "_add"] = (frm) => rigpl_sync_approvers(frm, table);
    rigpl_approver_events[table + "_remove"] = (frm) => rigpl_sync_approvers(frm, table);
});

frappe.ui.form.on("Department Approver", rigpl_approver_events);
