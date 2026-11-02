// Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt

const rm_cost_year = frappe.datetime.get_today().slice(0, 4);

frappe.query_reports["RM Cost of Items Made"] = {
	"filters": [
		{"fieldname": "from_date_1", "label": __("Period 1 From"), "fieldtype": "Date", "reqd": 1,
			"default": `${rm_cost_year - 1}-01-01`},
		{"fieldname": "to_date_1", "label": __("Period 1 To"), "fieldtype": "Date", "reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -12)},
		{"fieldname": "from_date_2", "label": __("Period 2 From"), "fieldtype": "Date", "reqd": 1,
			"default": `${rm_cost_year}-01-01`},
		{"fieldname": "to_date_2", "label": __("Period 2 To"), "fieldtype": "Date", "reqd": 1,
			"default": frappe.datetime.get_today()},
		{
			"fieldname": "group_by",
			"label": __("Group By"),
			"fieldtype": "MultiSelectList",
			"default": ["Base Material", "Tool Type"],
			"get_data": function(txt) {
				return frappe.db.get_link_options("Item Attribute", txt);
			},
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
		{
			"fieldname": "item_template",
			"label": __("Item Template"),
			"fieldtype": "Link",
			"options": "Item",
			"get_query": function() { return {filters: {has_variants: 1}}; },
		},
		{"fieldname": "bom_template", "label": __("BOM Template"), "fieldtype": "Link", "options": "BOM Template RIGPL"},
		{"fieldname": "show_items", "label": __("Show Items"), "fieldtype": "Check"},
	],
	"formatter": rigpl_erpnext.report.blank_zero_formatter,
};
