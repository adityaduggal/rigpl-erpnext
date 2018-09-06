// Copyright (c) 2013, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Employee Attendance"] = {
	"filters": [
		{
			"fieldname":"month",
			"label": __("Month"),
			"fieldtype": "Select",
			"options": "Jan\nFeb\nMar\nApr\nMay\nJun\nJul\nAug\nSep\nOct\nNov\nDec",
			"default": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", 
				"Dec"][frappe.datetime.str_to_obj(frappe.datetime.get_today()).getMonth()],
			"reqd": 1
		},
		{
			"fieldname":"year",
			"label": __("Year"),
			"fieldtype": "Select",
			"reqd": 1
		},
		{
			"fieldname":"employee",
			"label": __("Employee"),
			"fieldtype": "Link",
			"options": "Employee"
		},
		{
			"fieldname":"branch",
			"label": __("Branch"),
			"fieldtype": "Link",
			"options": "Branch"
		},
		{
			"fieldname":"department",
			"label": __("Department"),
			"fieldtype": "Link",
			"options": "Department"
		},
		{
			"fieldname":"designation",
			"label": __("Designation"),
			"fieldtype": "Link",
			"options": "Designation"
		}
	],
	"onload": function(me) {
		return  frappe.call({
			method: "erpnext.hr.report.monthly_attendance_sheet.monthly_attendance_sheet.get_attendance_years",
			callback: function(r) {
				var year_filter = frappe.query_report_filters_by_name.year;
				year_filter.df.options = r.message;
				year_filter.df.default = r.message.split("\n")[0];
				year_filter.refresh();
				year_filter.set_input(year_filter.df.default);
			}
		});
	}
}
