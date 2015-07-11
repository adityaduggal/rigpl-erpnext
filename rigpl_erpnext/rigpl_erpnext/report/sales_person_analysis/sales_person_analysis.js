// Copyright (c) 2013, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Sales Person Analysis"] = {
	"filters": [
		{
			fieldname: "doc_type",
			label: "Transaction Type",
			fieldtype: "Select",
			options: "\nSales Order\nDelivery Note\nSales Invoice",
			reqd: 1,
			default: "Sales Invoice"
		},
		{
			fieldname: "based_on",
			label: "Base On",
			fieldtype: "Select",
			options: "\nMaster\nTransaction",
			reqd: 1,
			default: "Transaction"
		},
		{
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date",
			reqd: 1,
			default: frappe.defaults.get_user_default("year_start_date"),
		},
		{
			fieldname:"to_date",
			label: "To Date",
			fieldtype: "Date",
			reqd: 1,
			default: get_today()
		},
		{
			fieldname:"sales_person",
			label: "Sales Person",
			fieldtype: "Link",
			reqd: 0,
			options: "Sales Person",
		},
		{
			fieldname:"territory",
			label: "Territory",
			fieldtype: "Link",
			options: "Territory",
		},
		{
			fieldname:"customer",
			label: "Customer",
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "fiscal_year",
			label: "Fiscal Year",
			fieldtype: "Link",
			options: "Fiscal Year",
			reqd: 1,
			default: frappe.defaults.get_user_default("fiscal_year"),
			on_change: function(query_report) {
				var fiscal_year = query_report.get_values().fiscal_year;
				if (!fiscal_year) {
					return;
				}
				frappe.model.with_doc("Fiscal Year", fiscal_year, function(r) {
					var fy = frappe.model.get_doc("Fiscal Year", fiscal_year);
					query_report.filters_by_name.from_date.set_input(fy.year_start_date);
					query_report.filters_by_name.to_date.set_input(fy.year_end_date);
					query_report.trigger_refresh();
				});
			}
		},
		{
			fieldname:"summary",
			label: "Summary",
			fieldtype: "Check",
			default: 1
		},
	]
}
