wn.query_reports["Follow Up"] = {
	"filters": [
		{
			"fieldname":"doc_type",
			"label": "Follow Up Type",
			"fieldtype": "Select",
			"options": "\nLead\nCustomer"
		},
		{
			"fieldname":"sales_person",
			"label": "Sales Person",
			"fieldtype": "Link",
			"options": "Sales Person"
		},
		{
			"fieldname":"territory",
			"label": "Territory",
			"fieldtype": "Link",
			"options": "Territory"
		},
		{
			"fieldname":"owner",
			"label": "Lead Owner",
			"fieldtype": "Link",
			"options": "Profile"
		},
		{
			"fieldname":"next_contact",
			"label": "Lead Next Contact",
			"fieldtype": "Link",
			"options": "Profile"
		}
	]
}