# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.query_builder.functions import IfNull
from frappe.utils import flt
from ....utils.item_attribute_utils import (
	attribute_filters,
	attribute_sort_key,
	chunks,
	get_attribute_details,
	get_attribute_map,
	get_attribute_values,
)
from ....utils.report_utils import blank_zeros


def execute(filters=None):
	if not filters: filters = {}
	items = get_item_list(filters)
	templates = list(dict.fromkeys(d.variant_of for d in items))
	if not templates:
		frappe.throw("No Temps in the given Criterion")

	att_details = get_attribute_details([t for t in templates if t])
	columns = get_columns(att_details)
	data = get_data(items, att_details, filters)
	return columns, data


def get_columns(att_details):
	columns = [
		_("Item") + ":Link/Item:130",
		_("Rate") + ":Currency:80", _("Valuation Rate Date") + ":Date:80",
		_("Base on PL") + ":Link/Price List:80",
		_("PL Rate") + ":Currency:80", _("%age of PL") + ":Float:80",
		_("Set %age") + ":Float:80"
	]
	for att in att_details:
		width = 10 * min(att.max_length, 10)
		col_type = "Float" if att.numeric_values == 1 else ""
		columns.append("%s:%s:%s" % (att.name_in_template, col_type, width))

	columns += [
		_("Description") + "::400", _("EOL") + ":Date:80", _("Created By") + "::150",
		_("Creation") + ":Date:150"
	]
	return columns


def get_item_list(filters):
	it = frappe.qb.DocType("Item")
	query = (
		frappe.qb.from_(it)
		.select(
			it.name, it.valuation_rate, it.valuation_rate_date,
			it.valuation_as_percent_of_default_selling_price, it.variant_of, it.description,
			it.end_of_life, it.owner, it.creation
		)
		.where(attribute_filters(it.name, get_attribute_values(filters)))
	)
	if filters.get("eol"):
		query = query.where(IfNull(it.end_of_life, "2099-12-31") > filters["eol"])
	if filters.get("show_in_website") == 1:
		query = query.where(it.pl_item == 1)
	if filters.get("item"):
		query = query.where(it.name == filters["item"])
	if filters.get("variant_of"):
		query = query.where(it.variant_of == filters["variant_of"])
	return query.run(as_dict=True)


def get_item_prices(items, price_list):
	"""
	Returns {item: [Item Price rows]} of the price list
	"""
	itp = frappe.qb.DocType("Item Price")
	prices = {}
	for chunk in chunks(items):
		rows = (
			frappe.qb.from_(itp)
			.select(itp.item_code, itp.price_list, itp.price_list_rate)
			.where(itp.item_code.isin(chunk))
			.where(itp.price_list == price_list)
			.run(as_dict=True)
		)
		for row in rows:
			prices.setdefault(row.item_code, []).append(row)
	return prices


def get_data(items, att_details, filters):
	"""
	Returns 1 row for each Item Price of the item in the price list (1 row with no price if it has
	none), sorted by the attribute columns and then the Item name
	"""
	names = [d.name for d in items]
	attributes = [att.name for att in att_details]
	numeric = {att.name for att in att_details if att.numeric_values == 1}
	att_map = get_attribute_map(names, attributes)
	prices = get_item_prices(names, filters.get("pl"))
	items.sort(
		key=lambda d: (attribute_sort_key(att_map.get(d.name, {}), attributes, numeric), d.name)
	)

	data = []
	no_price = [frappe._dict(price_list=None, price_list_rate=None)]
	for d in items:
		values = att_map.get(d.name, {})
		att_cells = []
		for att in attributes:
			value = values.get(att)
			if att in numeric:
				att_cells.append(None if value is None else round(flt(value), 3))
			else:
				att_cells.append("-" if value is None else value)
		for price in prices.get(d.name) or no_price:
			percent = None
			if price.price_list_rate:
				percent = flt(d.valuation_rate) / price.price_list_rate * 100
			row = [
				d.name, d.valuation_rate, d.valuation_rate_date, price.price_list,
				price.price_list_rate, percent, d.valuation_as_percent_of_default_selling_price
			]
			row += att_cells
			row += [d.description, d.end_of_life or "2099-12-31", d.owner or "X", d.creation]
			data.append(blank_zeros(row))
	return data
