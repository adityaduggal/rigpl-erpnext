#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import datetime
from ....utils.report_utils import blank_zeros


def execute(filters=None):
    if not filters: filters = {}

    columns = get_columns()
    data = get_sl_entries(filters)

    return columns, data


def get_columns():
    return [
        "Date:Date:80", "Time:Time:80", "Item:Link/Item:130", "Description::350",
        "Qty:Float:60", "Balance:Float:60", "Warehouse::120", "Rate:Currency:80",
        "Value:Currency: 120", "Incoming Rate:Currency:80",
        {
            "label": "Voucher No",
            "fieldname": "voucher_no",
            "fieldtype": "Dynamic Link",
            "options": "voucher_type",
            "width": 130
        },
        {
            "label": "Voucher Type",
            "fieldname": "voucher_type",
            "width": 140
        },
        {
            "label": "Linked Name",
            "fieldname": "linked_name",
            "fieldtype": "Dynamic Link",
            "options": "link_type",
            "width": 150
        }, "Name::100",
        {
            "label": "Link Type",
            "fieldname": "link_type",
            "width": 50
        }
    ]


# Voucher type: (link type, field) of the party. A Stock Entry links to the first field that is set.
PARTY_LINKS = {
    "Delivery Note": [("Customer", "customer")],
    "Sales Invoice": [("Customer", "customer")],
    "Purchase Receipt": [("Supplier", "supplier")],
    "Purchase Invoice": [("Supplier", "supplier")],
    "Stock Entry": [
        ("Process Job Card RIGPL", "process_job_card"),
        ("Sales Order", "sales_order"),
        ("Delivery Note", "delivery_note_no"),
        ("Sales Invoice", "sales_invoice_no"),
        ("Purchase Order", "purchase_order"),
        ("Purchase Receipt", "purchase_receipt_no"),
    ],
}


def get_sl_entries(filters):
    if not filters.get("item"):
        frappe.msgprint("Please select an Item Code first", raise_exception=1)
    sle = frappe.qb.DocType("Stock Ledger Entry")
    it = frappe.qb.DocType("Item")
    query = (
        frappe.qb.from_(sle)
        .join(it)
        .on(it.name == sle.item_code)
        .select(
            sle.posting_date, sle.posting_time, sle.item_code, it.description, sle.actual_qty,
            sle.qty_after_transaction, sle.warehouse, sle.valuation_rate, sle.stock_value,
            sle.incoming_rate, sle.voucher_no, sle.voucher_type, sle.name,
        )
        .where((sle.is_cancelled == 0) & (sle.item_code == filters["item"]))
        .orderby(sle.posting_date, order=frappe.qb.desc)
        .orderby(sle.posting_time, order=frappe.qb.desc)
        .orderby(sle.name, order=frappe.qb.desc)
    )
    if filters.get("warehouse"):
        query = query.where(sle.warehouse == filters["warehouse"])
    if filters.get("from_date"):
        query = query.where(sle.posting_date >= filters["from_date"])
    if filters.get("to_date"):
        query = query.where(sle.posting_date <= filters["to_date"])
    temp_data = query.run(as_dict=True)

    links = get_links(temp_data)
    data = []
    for d in temp_data:
        posting_time = d.posting_time - datetime.timedelta(microseconds=d.posting_time.microseconds)
        link_type, linked_name = links.get((d.voucher_type, d.voucher_no), (None, None))
        row = [d.posting_date, posting_time, d.item_code, d.description, d.actual_qty, d.qty_after_transaction,
               d.warehouse, d.valuation_rate, d.stock_value, d.incoming_rate, d.voucher_no, d.voucher_type,
               linked_name, d.name, link_type]
        data.append(blank_zeros(row))
    return data


def get_links(rows):
    """Return {(voucher_type, voucher_no): (link_type, linked_name)}, one query per voucher type."""
    vouchers = {}
    for d in rows:
        if d.voucher_type in PARTY_LINKS:
            vouchers.setdefault(d.voucher_type, set()).add(d.voucher_no)
    links = {}
    for voucher_type, names in vouchers.items():
        fields = [field for _, field in PARTY_LINKS[voucher_type]]
        for doc in frappe.get_all(voucher_type, filters={"name": ("in", list(names))},
                fields=["name"] + fields):
            links[(voucher_type, doc.name)] = next(
                ((link_type, doc[field]) for link_type, field in PARTY_LINKS[voucher_type] if doc[field]),
                (None, None))
    return links
