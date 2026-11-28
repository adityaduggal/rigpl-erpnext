// Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Schema Template", {
    refresh(frm) {
        frm.add_custom_button(__("Help"), () => rigpl_erpnext.show_user_guide(
            "website_seo_schema", __("Schema Templates")));
        if (frm.is_new()) {
            return;
        }
        frm.add_custom_button(__("Preview"), () => {
            frappe.prompt(
                {fieldname: "route", fieldtype: "Data", label: __("Route"), default: frm.doc.sample_route,
                    description: __("Empty: the home page")},
                values => show_preview(frm, values.route),
                __("Preview")
            );
        });
    }
});

function show_preview(frm, route) {
    frappe.call({
        method: "rigpl_erpnext.website_rigpl.doctype.schema_template.schema_template.preview",
        args: {name: frm.doc.name, route: route},
        freeze: true
    }).then(r => {
        const escape = frappe.utils.escape_html;
        const errors = r.message.errors.map(
            e => `<li>${escape(`${e.template} / ${e.property}: ${e.message}`)}</li>`).join("");
        const json = r.message.json
            ? `<pre>${escape(r.message.json)}</pre>`
            : `<p>${__("No node for this route.")}</p>`;
        const dialog = new frappe.ui.Dialog({title: __("JSON-LD"), size: "large"});
        dialog.$body.html((errors ? `<ul class="text-danger">${errors}</ul>` : "") + json);
        dialog.show();
    });
}
