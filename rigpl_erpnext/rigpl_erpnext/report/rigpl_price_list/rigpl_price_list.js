frappe.query_reports["RIGPL Price List"] = {
    "filters": [
        {
            "fieldname":"price_list_type",
            "label": "Price List Type",
            "fieldtype": "Select",
            "options": "\nPrice List\nPricing Rule",
            "default": "Price List",
            "reqd": 1
        },
        {
            "fieldname":"pl",
            "label": "Price List",
            "fieldtype": "Link",
            "options": "Price List",
            "default": frappe.defaults.get_default("selling_price_list"),
            "reqd": 1
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
            "reqd": 0,
            "ignore_link_validation": true,
            "get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_tt_query"}}
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
            "fieldname":"quality",
            "label": "Quality",
            "fieldtype": "Link",
            "options": "Item Attribute Value",
            "reqd": 0,
            "ignore_link_validation": true,
            "get_query": function(){ return {query: "rigpl_erpnext.utils.attribute_query.attribute_quality_query"}}
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
            "label": "Template",
            "fieldtype": "Link",
            "options": "Item",
            "get_query": function(){ return {'filters': [['Item', 'has_variants','=', 1]]}}
        },
        {
            "fieldname":"valid_from",
            "label": "Valid From",
            "fieldtype": "Date",
        },
        {
            "fieldname":"valid_upto",
            "label": "Valid Upto",
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
        },
        {
            "fieldname":"is_pl",
            "label": "Is Price List Item",
            "fieldtype": "Select",
            "options": "\nNo\nYes",
            "default": "Yes"
        },
        {
            "fieldname":"show_zero",
            "label": "Show Non Existent Prices",
            "fieldtype": "Check"
        }
    ]
}
