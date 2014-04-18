wn.query_reports["Todo Report"] = {
	"filters": [
		{
			"fieldname":"owner",
			"label": "Assigned To or Owner",
			"fieldtype": "Link",
			"options": "Profile",
		},
		{
			"fieldname":"assigned_by",
			"label": "Assigned By",
			"fieldtype": "Link",
			"options": "Profile",
		},
	]
}