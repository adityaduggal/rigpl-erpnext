// Copyright (c) 2016, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Item Lead Times"] = {
    "filters": [
        {
            "fieldname":"from_date",
            "label": "From Date",
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -12),
        },
        {
            "fieldname":"to_date",
            "label": "To Date",
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1,
        },
        {
            "fieldname":"bm",
            "label": "Base Material",
            "fieldtype": "Link",
            "options": "Item Attribute Value",
            "reqd": 1,
            "ignore_link_validation": true,
            "get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_bm_query"}}
        },
        {
            "fieldname":"tt",
            "label": "Tool Type",
            "fieldtype": "Link",
            "options": "Item Attribute Value",
            "reqd": 1,
            "ignore_link_validation": true,
            "get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_tt_query"}}
        },
        {
            "fieldname":"quality",
            "label": "Quality",
            "fieldtype": "Link",
            "options": "Item Attribute Value",
            "reqd": 1,
            "ignore_link_validation": true,
            "get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_quality_query"}}
        },
        {
            "fieldname":"rm",
            "label": "Is RM",
            "fieldtype": "Link",
            "options": "Item Attribute Value",
            "ignore_link_validation": true,
            "get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_rm_query"}}
        },
        {
            "fieldname":"series",
            "label": "Series",
            "fieldtype": "Link",
            "options": "Item Attribute Value",
            "reqd": 0,
            "ignore_link_validation": true,
            "get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_series_query"}}
        },
        {
            "fieldname":"item",
            "label": "Item Code",
            "fieldtype": "Link",
            "options": "Item",
            "get_query": function(){ return {'filters': [['Item', 'has_variants','=', 0]]}}
        },
        {
            "fieldname":"template",
            "label": "Variant Of",
            "fieldtype": "Link",
            "options": "Item",
            "get_query": function(){ return {'filters': [['Item', 'has_variants','=', 1]]}}
        },
        {
            "fieldname":"detail",
            "label": "Detail",
            "fieldtype": "Check",
        },
    ]
};
