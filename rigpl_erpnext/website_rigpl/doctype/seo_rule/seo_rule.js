// Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("SEO Rule", {
    refresh(frm) {
        frm.add_custom_button(__("Help"), () => rigpl_erpnext.show_user_guide(
            "website_seo_rules", __("SEO Rules")));
    }
});
