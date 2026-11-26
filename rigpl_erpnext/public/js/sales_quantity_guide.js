// Help button for the Pack Size and Minimum Order Value guide (#256).
// hooks.py loads this file for Sales Order and Quotation.
// Frappe shows the button one time, also when the files of both DocTypes are loaded
["Sales Order", "Quotation"].forEach((doctype) => {
    frappe.ui.form.on(doctype, {
        refresh: function(frm) {
            frm.add_custom_button(__("Pack Size and MoV Guide"), show_sales_quantity_guide, __("Help"));
        },
    });
});

function show_sales_quantity_guide() {
    frappe.call({method: "rigpl_erpnext.utils.guide_utils.get_user_guide",
        args: {guide: "sales_order_quantity"}}).then(r => {
        const dialog = new frappe.ui.Dialog({title: __("Pack Size and Minimum Order Value"), size: "large"});
        dialog.$body.html(r.message);
        dialog.$body.find("table").addClass("table table-bordered");
        dialog.$body.find("summary").css({cursor: "pointer", padding: "6px 0"});
        dialog.show();
    });
}
