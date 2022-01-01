// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Address Book RIGPL"] = {
	"filters": [
		{
			"fieldname":"type",
			"label": "Address or Contact",
			"fieldtype": "Link",
			"options": "DocType",
			"reqd": 1,
			"get_query": function() {
				return {
					"filters": {
						"name": ["in", "Address, Contact"],
					}
				}
			}
		},
		{
			"fieldname":"link_type",
			"label": "Linked to",
			"fieldtype": "Link",
			"options": "DocType",
			"reqd": 0,
			"get_query": function() {
				let type = frappe.query_report.get_filter_value('type');
				if (type === "Address"){
					return {
						"filters": {
							"fieldtype": ["=", "HTML"],
							"fieldname": ["=", "address_html"],
						}
					}
				} else if (type === "Contact"){
					return {
						"filters": {
							"fieldtype": ["=", "HTML"],
							"fieldname": ["=", "contact_html"],
						}
					}
				} else {
					frappe.throw("Please Select Address or Contact based Report")
				}
			}
		},
		{
			"fieldname":"linked_to",
			"label": "Master Name",
			"fieldtype": "Dynamic Link",
			"options": "DocType",
			"reqd": 0,
			"get_options": function() {
				let link_type = frappe.query_report.get_filter_value('link_type');
				if(!link_type) {
					frappe.throw(__("Please First Select Linked To Type"));
				}
				return link_type;
			}
		},
		{
			"fieldname":"territory",
			"label": "Territory",
			"fieldtype": "Link",
			"reqd": 0,
			"get_options": function() {
				let link_type = frappe.query_report.get_filter_value('link_type');
				if(link_type !== "Customer") {
					frappe.throw(__("Please First Select Linked To Customer"));
				}
				return "Territory";
			}
		},
		{
			"fieldname":"customer_group",
			"label": "Customer Group",
			"fieldtype": "Link",
			"reqd": 0,
			"get_options": function() {
				let link_type = frappe.query_report.get_filter_value('link_type');
				if(link_type !== "Customer") {
					frappe.throw(__("Please First Select Linked To Customer"));
				}
				return "Customer Group";
			}
		},
		{
			"fieldname":"orphaned",
			"label": "Orphaned",
			"fieldtype": "Check",
			"reqd": 0,
		},
	]
}
