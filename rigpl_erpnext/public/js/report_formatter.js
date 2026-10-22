// Shared formatter for Script Reports (#143).
// Frappe shows an empty Float cell as "0.000", and the "> 0" column filter then compares the text
// "0.000" > "0", which is true. This formatter shows an empty cell for an empty or 0 number, so
// the cell is easy to read and the "> 0" filter removes it.
// Use it in a report: "formatter": rigpl_erpnext.report.blank_zero_formatter,
frappe.provide("rigpl_erpnext.report");

rigpl_erpnext.report.NUMBER_TYPES = ["Float", "Currency", "Int", "Percent"];

rigpl_erpnext.report.blank_zero_formatter = function (
    value, row, column, data, default_formatter
) {
    if (column && rigpl_erpnext.report.NUMBER_TYPES.includes(column.fieldtype)) {
        const precision =
            column.fieldtype === "Int"
                ? 0
                : cint(column.precision) || cint(frappe.boot.sysdefaults.float_precision) || 3;
        if (value === null || value === undefined || value === "" || flt(value, precision) === 0) {
            return "";
        }
    }
    return default_formatter(value, row, column, data);
};
