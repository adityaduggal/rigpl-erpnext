// Copyright (c) 2020, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

const SEARCHES = 'rigpl_erpnext.rigpl_erpnext.doctype.important_documents.important_documents.';

// The link dropdown shows the row id in bold. For hash ids, show the first search column there.
function hide_row_id(awesomplete) {
	const render = awesomplete.item;
	awesomplete.item = function(item) {
		const $li = $(render.apply(this, arguments));
		const row = this.get_item(item.value);
		if (row.description && !row.action) {
			const [title, ...details] = row.description.split(', ');
			$li.find('strong').html(title);
			$li.find('.small').html(details.join(', '));
			$li.find('p').attr('title', title);
		}
		return $li.get(0);
	};
}

frappe.ui.form.on('Important Documents', {
	setup: function(frm) {
		frm.set_query('sales_order', () => ({ query: SEARCHES + 'sales_order_query' }));
		frm.set_query('sales_order_item', () => ({
			query: SEARCHES + 'sales_order_item_query',
			filters: { sales_order: frm.doc.sales_order }
		}));
		frm.set_query('category', () => ({ query: SEARCHES + 'category_query' }));
		for (const field of ['sales_order_item', 'category']) {
			frm.fields_dict[field].custom_awesomplete_filter = hide_row_id;
		}
	},
	refresh: function(frm) {

	},
	onload: function(frm){
	    if (frm.doc.type === 'Standard'){
            frm.set_df_property("standard_authority", "reqd", 1);
            frm.set_df_property("standard_number", "reqd", 1);
            frm.set_df_property("standard_year", "reqd", 1);
            frm.set_df_property("description", "reqd", 1);
            frm.set_df_property("category", "reqd", 1);
	    }
	    if (frm.doc.type === 'Drawing'){
            frm.set_df_property("drawing_based_on", "reqd", 1);
	    }
	    if (frm.doc.drawing_based_on === 'Sales Order'){
            frm.set_df_property("sales_order", "reqd", 1);
            frm.set_df_property("sales_order_item", "reqd", 1);
            frm.set_df_property("customer", "read_only", 1);
            frm.set_df_property("description", "read_only", 1);
            frm.set_df_property("item", "read_only", 1);
	    } else if (frm.doc.drawing_based_on === 'Item'){
	        frm.set_df_property("customer", "hidden", 1);
	        frm.set_df_property("item", "reqd", 1);
	        frm.set_df_property("description", "read_only", 1);
	    } else if (frm.doc.drawing_based_on === 'Customer'){
	        frm.set_df_property("item", "hidden", 1);
	        frm.set_df_property("customer", "reqd", 1);
	        frm.set_df_property("description", "reqd", 1);
	    }
		frm.set_query("drawing_based_on", function(doc) {
			return {
				"filters": [
				    ['name', 'in', ['Customer', 'Sales Order', 'Item']]
				]
			};
		});
        frm.set_query("item", function(doc){
            return {
                "filters": {
                    "has_variants": frm.doc.template
                }
            };
        });
	},
});

frappe.ui.form.on('Important Documents', 'type', function(frm){
   var fields = ["drawing_based_on", "sales_order", "sales_order_item", "item", "standard_authority",
    "standard_number", "standard_year", "committee", "description", "template", "category", "category_name"]
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
        frm.set_df_property("category", "reqd", 0);
    } else {
        frm.set_df_property("description", "read_only", 0);
        frm.set_df_property("description", "read_only", 0);
        frm.set_df_property("standard_authority", "reqd", 1);
        frm.set_df_property("standard_number", "reqd", 1);
        frm.set_df_property("standard_year", "reqd", 1);
        frm.set_df_property("description", "reqd", 1);
        frm.set_df_property("category", "reqd", 1);
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
});

frappe.ui.form.on('Important Documents', 'sales_order', function(frm){
    var fields = ["sales_order_item", "customer", "item", "description"]
    for (var d of fields){
        frm.set_value(d, "")
    }
    frm.set_df_property("customer", "read_only", 1);
    frm.set_df_property("customer", "hidden", 0);
    frm.add_fetch("sales_order", "customer", "customer");
});

frappe.ui.form.on('Important Documents', 'sales_order_item', function(frm){
    var fields = ["item", "description"]
    for (var d of fields){
        frm.set_value(d, "")
    }
    frm.set_df_property("item", "read_only", 1)
    frm.set_df_property("item", "hidden", 0)
    if (frm.doc.sales_order_item) {
        frappe.call({
            method: SEARCHES + 'get_sales_order_item_values',
            args: { sales_order_item: frm.doc.sales_order_item }
        }).then(r => frm.set_value(r.message));
    }
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

frappe.ui.form.on('Important Documents', 'category', function(frm){
    if (!frm.doc.category) {
        return frm.set_value('category_name', '');
    }
    frappe.call({
        method: SEARCHES + 'get_category_name',
        args: { category: frm.doc.category }
    }).then(r => frm.set_value('category_name', r.message));
});