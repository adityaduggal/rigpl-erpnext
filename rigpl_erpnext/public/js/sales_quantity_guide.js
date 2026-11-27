// Help button for the Pack Size and Minimum Order Value guide (#256).
// hooks.py loads this file for Sales Order and Quotation.
// Frappe shows the button one time, also when the files of both DocTypes are loaded
["Sales Order", "Quotation"].forEach((doctype) => {
    frappe.ui.form.on(doctype, {
        refresh: function(frm) {
            frm.add_custom_button(__("Pack Size and MoV Guide"), () => rigpl_erpnext.show_user_guide(
                "sales_order_quantity", __("Pack Size and Minimum Order Value")), __("Help"));
        },
    });
});
