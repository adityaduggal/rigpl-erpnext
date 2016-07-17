frappe.query_reports["Follow Up"] = {
	"filters": [
		{
			"fieldname":"doc_type",
			"label": "Follow Up Type",
			"fieldtype": "Select",
			"options": "\nLead\nCustomer",
			"reqd": 1
		},
		{
			"fieldname":"owner",
			"label": "Lead Owner",
			"fieldtype": "Link",
			"options": "User"
		},
		{
			"fieldname":"next_contact",
			"label": "Lead Next Contact",
			"fieldtype": "Link",
			"options": "User"
		},
		{
			"fieldname":"status",
			"label": "Status of Lead OR Customer",
			"fieldtype": "Select",
			"options": "\n----Lead Related----\nHot\nCold\nQuotation Sent\nConverted\nLost\n \
			----Commom----\nTrial Passed\nTrial Failed\n \
			----Customer Related----\nOK\nBlack Listed\nChanged Business\nThrough Dealer\nTrial In Progress"
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
		}
	]
}
