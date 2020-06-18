// Copyright (c) 2020, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Important Documents', {
	refresh: function(frm) {

	},
	onload: function(frm){
		frm.set_query("sales_order", function(doc) {
			return {
				"filters": {
					"docstatus": 1
				}
			};
		});
		frm.set_query("drawing_based_on", function(doc) {
			return {
				"filters": [
				    ['name', 'in', ['Customer', 'Sales Order', 'Item']]
				]
			};
		});
		frm.set_query("sales_order_item", function(doc) {
			return {
				"filters": {
					"parent": frm.doc.sales_order
				}
			};
		});
	},
});

frappe.ui.form.on('Important Documents', 'type', function(frm){
   var fields = ["drawing_based_on", "sales_order", "sales_order_item", "item", "standard_authority",
    "standard_number", "standard_year", "committee", "description", "template"]
    for (var d of fields){
        frm.set_value(d, "")
        frm.set_df_property(d, "reqd", 0)
    }
    if (frm.doc.type === 'Drawing'){
        frm.set_df_property("description", "read_only", 1);
        frm.set_df_property("drawing_based_on", "reqd", 1);
        frm.set_df_property("standard_authority", "reqd", 0);
        frm.set_df_property("standard_number", "reqd", 0);
        frm.set_df_property("standard_year", "reqd", 0);
        frm.set_df_property("description", "reqd", 0);
    } else {
        frm.set_df_property("description", "read_only", 0);
        frm.set_df_property("description", "read_only", 0);
        frm.set_df_property("standard_authority", "reqd", 1);
        frm.set_df_property("standard_number", "reqd", 1);
        frm.set_df_property("standard_year", "reqd", 1);
        frm.set_df_property("description", "reqd", 1);
    }
});

frappe.ui.form.on('Important Documents', 'drawing_based_on', function(frm){
   var fields = ["sales_order", "sales_order_item", "template", "item", "description", "customer"]
    for (var d of fields){
        frm.set_value(d, "")
    }
    if (frm.doc.drawing_based_on === 'Customer'){
        frm.set_df_property("customer", "reqd", 1);
        frm.set_df_property("description", "reqd", 1);
        frm.set_df_property("sales_order", "reqd", 0);
        frm.set_df_property("sales_order_item", "reqd", 0);
        frm.set_df_property("item", "reqd", 0);

        frm.set_df_property("item", "hidden", true);
        frm.set_df_property("description", "read_only", false);
        frm.set_df_property("description", "hidden", false);
        frm.set_df_property("customer", "read_only", false);
        frm.set_df_property("customer", "hidden", false);
    } else if (frm.doc.drawing_based_on === 'Item'){
        frm.set_df_property("customer", "reqd", 0);
        frm.set_df_property("description", "reqd", 0);
        frm.set_df_property("sales_order", "reqd", 0);
        frm.set_df_property("sales_order_item", "reqd", 0);
        frm.set_df_property("item", "reqd", 1);

        frm.set_df_property("customer", "hidden", true);
        frm.set_df_property("item", "hidden", false);
        frm.set_df_property("item", "read_only", false);
        frm.set_df_property("description", "read_only", true);
        frm.set_df_property("description", "hidden", false);
    } else if (frm.doc.drawing_based_on === 'Sales Order'){
        frm.set_df_property("customer", "reqd", 0);
        frm.set_df_property("description", "reqd", 0);
        frm.set_df_property("sales_order", "reqd", 1);
        frm.set_df_property("sales_order_item", "reqd", 1);
        frm.set_df_property("item", "reqd", 0);

        frm.set_df_property("description", "read_only", true);
        frm.set_df_property("customer", "read_only", true);
        frm.set_df_property("customer", "hidden", false);
        frm.set_df_property("item", "hidden", false);
        frm.set_df_property("item", "read_only", true);
    }
    frm.set_query("item", function(doc){
        return {
            "filters": {
                "has_variants": frm.doc.template
            }
        };
    });
});

frappe.ui.form.on('Important Documents', 'sales_order', function(frm){
    frm.set_df_property("customer", "read_only", 1);
    frm.set_df_property("customer", "hidden", 0);
    frm.add_fetch("sales_order", "customer", "customer");

    frm.set_query("sales_order_item", function(doc){
        return {
            "filters": {
                "parent": frm.doc.sales_order
            }
        };
    });
});

frappe.ui.form.on('Important Documents', 'sales_order_item', function(frm){
    frm.set_df_property("item", "read_only", 1)
    frm.set_df_property("item", "hidden", 0)
    frm.add_fetch("sales_order_item", "item_code", "item");
    frm.add_fetch("sales_order_item", "description", "description");
});

frappe.ui.form.on('Important Documents', 'item', function(frm){
    frm.set_df_property("description", "read_only", 1);
    frm.set_df_property("description", "hidden", 0);
    frm.add_fetch("item", "description", "description");
});

frappe.ui.form.on('Important Documents', 'customer', function(frm){
    frm.set_df_property("description", "read_only", 0);
    frm.set_df_property("description", "hidden", 0);
    frm.set_df_property("item", "hidden", 1)
});