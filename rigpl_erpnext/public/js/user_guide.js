// Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt

frappe.provide("rigpl_erpnext");

// Shows a guide of docs/user/ in a dialog (utils/guide_utils.py)
rigpl_erpnext.show_user_guide = function(guide, title) {
    frappe.call({method: "rigpl_erpnext.utils.guide_utils.get_user_guide", args: {guide: guide}}).then(r => {
        const dialog = new frappe.ui.Dialog({title: title, size: "large"});
        dialog.$body.html(r.message);
        dialog.$body.find("table").addClass("table table-bordered");
        dialog.$body.find("summary").css({cursor: "pointer", padding: "6px 0"});
        dialog.show();
    });
};
