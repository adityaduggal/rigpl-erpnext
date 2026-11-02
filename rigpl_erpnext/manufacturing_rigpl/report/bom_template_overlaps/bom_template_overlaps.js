// Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["BOM Template Overlaps"] = {
	"filters": [
		{
			"fieldname": "match_level",
			"label": __("Match Level"),
			"fieldtype": "Select",
			"options": "Exact\nAlmost\nSame Operations",
			"default": "Exact",
		},
		{
			"fieldname": "bm",
			"label": __("Base Material"),
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"ignore_link_validation": true,
			"get_query": function() { return {query: "rigpl_erpnext.utils.attribute_query.attribute_bm_query"}; },
		},
		{
			"fieldname": "tt",
			"label": __("Tool Type"),
			"fieldtype": "Link",
			"options": "Item Attribute Value",
			"ignore_link_validation": true,
			"get_query": function() { return {query: "rigpl_erpnext.utils.attribute_query.attribute_tt_query"}; },
		},
	],
	"formatter": rigpl_erpnext.report.blank_zero_formatter,
};
