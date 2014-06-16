wn.query_reports["Sales Partner SO Analysis"] = {
	"filters": [
		{
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date",
			default: wn.defaults.get_user_default("year_start_date"),
		},
		{
			fieldname:"to_date",
			label: "To Date",
			fieldtype: "Date",
			default: get_today()
		},
		{
			fieldname:"sales_partner",
			label: "Sales Partner",
			fieldtype: "Link",
			options: "Sales Partner",
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
	]
}