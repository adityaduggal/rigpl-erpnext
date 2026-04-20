// Copyright (c) 2021, Rohit Industries Group Private Limited and Contributors
// For license information, please see license.txt

frappe.ui.form.on("Payment Entry", {
    setup: function (frm) {
        // Set employment_type from User Permission for new documents.
        // The field is at permlevel 1 (read-only for Accounts User) and mandatory,
        // but the client-side doesn't auto-fill User Permission defaults for
        // permlevel > 0 fields. This ensures the value is set before save.
        set_employment_type_default(frm);
    },
    refresh: function (frm) {
        // Also set on refresh in case setup was too early
        set_employment_type_default(frm);
    },
});

function set_employment_type_default(frm) {
    if (frm.is_new() && !frm.doc.employment_type) {
        let user_perms = frappe.defaults.get_user_permissions();
        if (user_perms && user_perms["Employment Type"]) {
            let et_perms = user_perms["Employment Type"];
            if (et_perms.length > 0) {
                frm.set_value("employment_type", et_perms[0].doc);
            }
        }
    }
}
