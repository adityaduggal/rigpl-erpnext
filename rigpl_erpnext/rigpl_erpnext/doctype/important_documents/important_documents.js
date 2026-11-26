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
		frm.set_query('drawing_based_on', () => ({
			filters: [['name', 'in', ['Customer', 'Sales Order', 'Item']]]
		}));
		frm.set_query('item', () => ({ filters: { has_variants: frm.doc.template } }));
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
	type: function(frm) {
		clear_values(frm, ['drawing_based_on', 'sales_order', 'sales_order_item', 'item', 'standard_authority',
			'standard_number', 'standard_year', 'committee', 'description', 'template', 'category',
			'category_name']);
	},
	drawing_based_on: function(frm) {
		clear_values(frm, ['sales_order', 'sales_order_item', 'template', 'item', 'description', 'customer']);
	},
	sales_order: function(frm) {
		// fetch_from sets the customer
		clear_values(frm, ['sales_order_item', 'item', 'description']);
	},
	sales_order_item: function(frm) {
		clear_values(frm, ['item', 'description']);
		if (frm.doc.sales_order_item) {
			frappe.call({
				method: SEARCHES + 'get_sales_order_item_values',
				args: { sales_order_item: frm.doc.sales_order_item }
			}).then(r => frm.set_value(r.message));
		}
	},
	item: function(frm) {
		// A Sales Order Item has its own description
		if (frm.doc.sales_order_item) {
			return;
		}
		if (!frm.doc.item) {
			return frm.set_value('description', '');
		}
		frappe.db.get_value('Item', frm.doc.item, 'description')
			.then(r => frm.set_value('description', r.message.description));
	},
	category: function(frm) {
		if (!frm.doc.category) {
			return frm.set_value('category_name', '');
		}
		frappe.call({
			method: SEARCHES + 'get_category_name',
			args: { category: frm.doc.category }
		}).then(r => frm.set_value('category_name', r.message));
	}
});

function clear_values(frm, fields) {
	for (const field of fields) {
		frm.set_value(field, field === 'template' ? 0 : '');
	}
}
