// Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("SEO Settings", {
    setup(frm) {
        frm.set_query("addresses", () => ({
            filters: {is_your_company_address: 1, disabled: 0}
        }));
    },

    refresh(frm) {
        frm.add_custom_button(__("Help"), () => rigpl_erpnext.show_user_guide(
            "website_seo_rules", __("SEO Rules")));
        frm.add_custom_button(__("Create Missing Records"), () => create_records(frm));
    }
});

function create_records(frm) {
    frappe.call({
        method: "rigpl_erpnext.website_rigpl.doctype.seo_settings.seo_settings.create_records",
        freeze: true
    }).then(r => {
        const names = r.message.map(name => frappe.utils.escape_html(name));
        frappe.msgprint(names.length
            ? `${__("Created")}: ${names.join(", ")}`
            : __("All default records exist."));
        frm.reload_doc();
    });
}
