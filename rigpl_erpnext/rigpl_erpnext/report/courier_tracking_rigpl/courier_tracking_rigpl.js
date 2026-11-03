// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt
// Report Type picks the view; each view shows its own chart and summary cards (#173).

frappe.query_reports["Courier Tracking RIGPL"] = {
	"filters": [
		{
			"fieldname": "report_type",
			"label": "Report Type",
			"fieldtype": "Select",
			"options": [
				"Pending Exceptions", "Detailed", "Total AWB by Transporter", "Avg Delivery Time",
				"Old Exceptions", "Carrier Performance", "POD Coverage", "Cost vs Charged"
			].join("\n"),
			"default": "Pending Exceptions",
			"reqd": 1,
		},
		{
			"fieldname": "from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -3),
		},
		{
			"fieldname": "to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
		},
		{
			"fieldname": "transporter",
			"label": "Transporter",
			"fieldtype": "Link",
			"options": "Transporters",
		},
		{
			"fieldname": "from_address",
			"label": "From Address",
			"fieldtype": "Link",
			"options": "Address",
			"get_query": function () {
				return {"filters": [["Address", "is_your_company_address", "=", 1]]};
			}
		},
		{
			"fieldname": "status",
			"label": "Status",
			"fieldtype": "Select",
			"options": [
				"", "Booked", "In Transit", "Out for Delivery", "Delivered", "RTO", "Exception", "Cancelled",
				"No Information", "Closed - No Update", "Not Booked"
			].join("\n"),
		},
		{
			"fieldname": "awb_no",
			"label": "AWB No",
			"fieldtype": "Data",
		},
		{
			"fieldname": "document_name",
			"label": "Document Name",
			"fieldtype": "Data",
		},
		{
			"fieldname": "receiver_name",
			"label": "Receiver Name",
			"fieldtype": "Data",
		},
	],
	"formatter": rigpl_erpnext.report.blank_zero_formatter,
};
