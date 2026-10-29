# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from operator import itemgetter
import frappe
from erpnext.stock.report.stock_ageing.stock_ageing import FIFOSlots, get_average_age
from frappe import _
from frappe.query_builder.functions import IfNull
from frappe.utils import date_diff, flt, getdate, nowdate
from ....utils.item_attribute_utils import attribute_filters, chunks, get_attribute_map
from ....utils.report_utils import blank_zeros
from ....utils.stock_utils import get_bin_qty, get_sle_for_items, get_sle_for_pairs, \
	get_warehouses

FILTER_ATTS = {
	"rm": "Is RM",
	"bm": "Base Material",
	"brand": "Brand",
	"tt": "Tool Type",
	"spl": "Special Treatment",
}
TEXT_ATTS = ["Is RM", "Base Material", "Tool Type", "Brand", "Special Treatment"]
NUMERIC_ATTS = ["d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm", "Number of Flutes Zn"]
QUALITY_ATTS = ["HSS Quality", "Carbide Quality"]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(filters), StockAgeing(filters).get_data()


class StockAgeing:
	"""FIFO ages of the stock per item, or per item and warehouse, on the As On Date.
	The number of queries depends on the item count / 1000, not on the row count."""

	def __init__(self, filters):
		self.filters = filters
		self.to_date = getdate(filters.to_date)
		self.warehouse_wise = bool(filters.get("show_ageing_warehouse_wise"))

	def get_data(self):
		self.item_map = {d.name: d for d in get_items(self.filters)}
		warehouses = get_warehouses(self.filters.get("warehouse"))
		pairs = self.get_stocked_pairs(warehouses)

		data = []
		for chunk in chunks(self.item_map):
			if pairs is None:
				sle = get_sle_for_items(chunk, warehouses, self.to_date)
			else:
				# All the warehouses of an item stay in one chunk, so FIFOSlots can add them up
				in_chunk = set(chunk)
				chunk_pairs = [pair for pair in pairs if pair[0] in in_chunk]
				sle = get_sle_for_pairs(chunk_pairs, self.to_date) if chunk_pairs else []
			data += self.get_chunk_rows(sle)
		wh_col = 2 if self.warehouse_wise else 0
		data.sort(key=lambda row: (row[0].casefold(), row[wh_col].casefold()))
		return [blank_zeros(row) for row in data]

	def get_stocked_pairs(self, warehouses):
		"""On today or a later date the Bin has the balance, so read only the pairs in stock.
		Return None for a past date: it can have stock that the Bin does not show now."""
		if self.to_date < getdate(nowdate()):
			return None
		bin_qty = get_bin_qty(list(self.item_map), warehouses)
		return sorted(pair for pair, qty in bin_qty.items() if qty > 0)

	def get_chunk_rows(self, sle):
		fifo = FIFOSlots(filters={"show_warehouse_wise_stock": self.warehouse_wise}, sle=sle).generate()
		shown = {}
		for key, fifo_dict in fifo.items():
			fifo_queue = sorted(filter(itemgetter(1), fifo_dict["fifo_queue"]), key=itemgetter(1))
			if fifo_queue and flt(fifo_dict.get("total_qty"), 3) > 0:
				shown[key] = (fifo_dict["total_qty"], fifo_queue)
		# Most items in the filters have no stock, so look up only the items that get a row
		items = [key[0] if self.warehouse_wise else key for key in shown]
		self.att_map = get_attribute_map(items, TEXT_ATTS + NUMERIC_ATTS + QUALITY_ATTS)
		return [self.get_row(key, total_qty, fifo_queue) for key, (total_qty, fifo_queue) in shown.items()]

	def get_row(self, key, total_qty, fifo_queue):
		item = key[0] if self.warehouse_wise else key
		it = self.item_map[item]
		atts = self.att_map.get(item, {})
		text = {att: atts.get(att) or "-" for att in TEXT_ATTS}
		quality = atts.get("HSS Quality") or atts.get("Carbide Quality") or "-"
		numbers = {att: None if atts.get(att) is None else round(flt(atts[att]), 3) for att in NUMERIC_ATTS}
		row = [item, it.description]
		if self.warehouse_wise:
			row.append(key[1])
		row += [
			total_qty, get_average_age(fifo_queue, self.to_date),
			date_diff(self.to_date, fifo_queue[0][1]), date_diff(self.to_date, fifo_queue[-1][1]),
			it.stock_uom, text["Is RM"], text["Base Material"], text["Tool Type"], text["Brand"],
			quality, text["Special Treatment"], numbers["d1_mm"], numbers["w1_mm"], numbers["l1_mm"],
			numbers["d2_mm"], numbers["l2_mm"], numbers["Number of Flutes Zn"],
		]
		return row


def get_items(filters):
	it = frappe.qb.DocType("Item")
	query = (
		frappe.qb.from_(it)
		.select(it.name, it.description, it.stock_uom)
		.where(IfNull(it.end_of_life, "2099-12-31") > nowdate())
		.where(attribute_filters(it.name, {att: filters.get(key) for key, att in FILTER_ATTS.items()}))
	)
	if filters.get("item_code"):
		query = query.where(it.name == filters["item_code"])
	items = query.run(as_dict=True)
	if not items:
		frappe.throw("No Items Found in given Criterion")
	return items


def get_columns(filters):
	columns = [_("Item Code") + ":Link/Item:120", _("Description") + "::200"]

	if filters.get("show_ageing_warehouse_wise"):
		columns.extend([_("Warehouse") + ":Link/Warehouse:130"])

	columns.extend([_("Available Qty") + ":Float:100", _("Average Age") + ":Int:80",
		_("Earliest") + ":Int:80", _("Latest") + ":Int:80", _("UOM") + ":Link/UOM:50",
		_("Is RM") + "::60", _("BM") + "::60", _("TT") + "::150", _("Brand") + "::60", _("Qual") + "::60",
		_("Spl") + "::60", _("D1") + ":Float:60", _("W1") + ":Float:60", _("L1") + ":Float:60",
		_("D2") + ":Float:60", _("L2") + ":Float:60", _("Zn") + ":Float:60"])

	return columns
