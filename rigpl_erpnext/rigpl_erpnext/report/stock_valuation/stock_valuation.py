# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from erpnext.stock.report.stock_ageing.stock_ageing import FIFOSlots, get_average_age
from frappe.query_builder.functions import IfNull
from frappe.utils import date_diff, flt, getdate, nowdate
from pypika.analytics import RowNumber
from ....utils.item_attribute_utils import attribute_filters, chunks, get_attribute_map
from ....utils.report_utils import blank_zeros
from ....utils.stock_utils import get_bin_qty, get_sle_for_items, get_sle_for_pairs, \
    get_warehouses

TEXT_ATTS = ["Is RM", "Base Material", "HSS Quality", "Carbide Quality", "Brand", "Tool Type"]
NUMERIC_ATTS = ["d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm"]
FILTER_ATTS = {
    "rm": "Is RM",
    "bm": "Base Material",
    "brand": "Brand",
    "tt": "Tool Type",
    "spl": "Special Treatment",
}


def execute(filters=None):
    filters = frappe._dict(filters or {})
    return get_columns(), StockValuation(filters).get_data()


def get_columns():
    return [
        "Item:Link/Item:120", "Description::300", "Warehouse:Link/Warehouse:150",
        "Quantity:Float:80", "Current Stock:Float:100", "List Price:Currency:80",
        "VR:Currency:80", "Value:Currency:100",
        "BM::80", "Qual::80", "TT::120", "D1:Float:50", "W1:Float:50", "L1:Float:60",
        "D2:Float:50", "L2:Float:60", "Is RM::50", "Brand::60",
        "Set Value:Currency:80", "Last PO Price:Currency:80", "Is Purchase::80",
        "Av Age:Float:80", "Earliest:Int:80", "Latest:Int:80",
    ]


class StockValuation:
    """FIFO stock and ages per item and warehouse on the Valuation Date.
    The number of queries depends on the item count / 1000, not on the row count."""

    def __init__(self, filters):
        self.filters = filters
        self.to_date = getdate(filters.date)

    def get_data(self):
        items = get_items(self.filters)
        names = [d.name for d in items]
        warehouses = get_warehouses(self.filters.get("warehouse"))
        self.item_map = {d.name: d for d in items}
        self.bin_qty = get_bin_qty(names, warehouses)

        data = []
        pairs = self.get_stocked_pairs()
        if pairs is None:
            for chunk in chunks(names):
                data += self.get_chunk_rows(get_sle_for_items(chunk, warehouses, self.to_date))
        else:
            for chunk in chunks(sorted(pairs)):
                data += self.get_chunk_rows(get_sle_for_pairs(chunk, self.to_date))
        data.sort(key=lambda row: (row[0].casefold(), row[2].casefold()))
        return [blank_zeros(row) for row in data]

    def get_stocked_pairs(self):
        """On today or a later date the Bin has the balance, so read only the pairs in stock.
        Return None for a past date: it can have stock that the Bin does not show now."""
        if self.to_date < getdate(nowdate()):
            return None
        return {pair for pair, qty in self.bin_qty.items() if qty > 0}

    def get_chunk_rows(self, sle):
        last_sle = {(d.name, d.warehouse): d for d in sle}
        fifo = FIFOSlots(filters={"show_warehouse_wise_stock": True}, sle=sle).generate()
        shown = {
            key: fifo_dict
            for key, fifo_dict in fifo.items()
            if fifo_dict.get("total_qty") > 0.5 and fifo_dict["fifo_queue"]
        }
        # Most items in the filters have no stock, so look up only the items that get a row
        self.load_item_values([item for item, _ in shown])
        return [
            self.get_row(key, fifo_dict["total_qty"], fifo_dict["fifo_queue"], last_sle[key])
            for key, fifo_dict in shown.items()
        ]

    def load_item_values(self, items):
        self.att_map = get_attribute_map(items, TEXT_ATTS + NUMERIC_ATTS)
        self.list_rates = get_price_list_rates(items, self.filters.get("pl"))
        self.purchase_rates = get_last_purchase_rates(items, self.to_date)

    def get_row(self, key, total_qty, fifo_queue, last_sle):
        item, warehouse = key
        it = self.item_map[item]
        atts = self.att_map.get(item, {})
        text = {att: atts.get(att) or "-" for att in TEXT_ATTS}
        quality = atts.get("HSS Quality") or atts.get("Carbide Quality") or "-"
        numbers = [None if atts.get(att) is None else round(flt(atts[att]), 3) for att in NUMERIC_ATTS]
        return [
            item, it.description, warehouse, total_qty, flt(self.bin_qty.get(key)),
            self.list_rates.get(item), flt(last_sle.valuation_rate), flt(last_sle.stock_value),
            text["Base Material"], quality, text["Tool Type"], *numbers,
            text["Is RM"], text["Brand"], it.valuation_rate, self.purchase_rates.get(item),
            it.is_purchase_item, get_average_age(fifo_queue, self.to_date),
            date_diff(self.to_date, fifo_queue[0][1]), date_diff(self.to_date, fifo_queue[-1][1]),
        ]


def get_items(filters):
    it = frappe.qb.DocType("Item")
    query = (
        frappe.qb.from_(it)
        .select(it.name, it.description, it.valuation_rate, it.is_purchase_item)
        .where(IfNull(it.end_of_life, "2099-12-31") > nowdate())
        .where(attribute_filters(it.name, {att: filters.get(key) for key, att in FILTER_ATTS.items()}))
    )
    if filters.get("item"):
        query = query.where(it.name == filters["item"])
    if filters.get("template"):
        query = query.where(it.variant_of == filters["template"])
    items = query.run(as_dict=True)
    if not items:
        frappe.throw("No Items Found in given Criterion")
    return items


def get_price_list_rates(items, price_list):
    """Return {item: price_list_rate}. With more than one Item Price, the first one is used."""
    rates = {}
    ip = frappe.qb.DocType("Item Price")
    for chunk in chunks(items):
        query = (
            frappe.qb.from_(ip)
            .select(ip.item_code, ip.price_list_rate)
            .where((ip.price_list == price_list) & ip.item_code.isin(chunk))
        )
        for item, rate in query.run():
            rates.setdefault(item, rate)
    return rates


def get_last_purchase_rates(items, to_date):
    """Return {item: base_net_rate} of the last submitted Purchase Receipt on or before `to_date`."""
    rates = {}
    pr = frappe.qb.DocType("Purchase Receipt")
    pri = frappe.qb.DocType("Purchase Receipt Item")
    for chunk in chunks(items):
        ranked = (
            frappe.qb.from_(pri)
            .join(pr)
            .on(pr.name == pri.parent)
            .select(
                pri.item_code,
                pri.base_net_rate,
                RowNumber()
                .over(pri.item_code)
                .orderby(pr.posting_date, order=frappe.qb.desc)
                .orderby(pr.posting_time, order=frappe.qb.desc)
                .orderby(pr.creation, order=frappe.qb.desc)
                .as_("rn"),
            )
            .where((pr.docstatus == 1) & (pr.posting_date <= to_date) & pri.item_code.isin(chunk))
        )
        query = frappe.qb.from_(ranked).select(ranked.item_code, ranked.base_net_rate).where(ranked.rn == 1)
        for item, rate in query.run():
            rates[item] = rate
    return rates
