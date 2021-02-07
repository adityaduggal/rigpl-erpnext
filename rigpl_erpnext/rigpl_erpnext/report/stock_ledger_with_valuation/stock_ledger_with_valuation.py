#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import datetime


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


def get_sl_entries(filters):
    conditions = get_conditions(filters)
    temp_data = frappe.db.sql("""SELECT sle.posting_date, sle.posting_time, 
    sle.item_code, it.description, sle.actual_qty, sle.qty_after_transaction, sle.warehouse, sle.valuation_rate, 
    sle.stock_value, sle.incoming_rate, sle.voucher_no, sle.voucher_type, 'X', sle.name, 'X' 
    FROM `tabStock Ledger Entry` sle, `tabItem` it WHERE sle.is_cancelled = "No" AND it.name = sle.item_code %s 
    ORDER BY sle.posting_date DESC, sle.posting_time DESC, sle.name DESC""" % conditions, as_dict=1)

    for d in temp_data:
        d["posting_time"] = d["posting_time"] - datetime.timedelta(microseconds=d["posting_time"].microseconds)
        if d.voucher_type in ('Delivery Note', 'Sales Invoice'):
            dn_doc = frappe.get_doc(d.voucher_type, d.voucher_no)
            d["linked_name"] = dn_doc.customer
            d["link_type"] = "Customer"

        elif d.voucher_type in ('Purchase Receipt', 'Purchase Invoice'):
            dn_doc = frappe.get_doc(d.voucher_type, d.voucher_no)
            d["linked_name"] = dn_doc.supplier
            d["link_type"] = "Supplier"
        elif d.voucher_type == "Stock Entry":
            dn_doc = frappe.get_doc(d.voucher_type, d.voucher_no)
            if dn_doc.process_job_card is not None:
                d["link_type"] = "Process Job Card RIGPL"
                d["linked_name"] = dn_doc.process_job_card
            elif dn_doc.sales_order is not None:
                d["link_type"] = "Sales Order"
                d["linked_name"] = dn_doc.sales_order
            elif dn_doc.delivery_note_no is not None:
                d["link_type"] = "Delivery Note"
                d["linked_name"] = dn_doc.delivery_note_no
            elif dn_doc.sales_invoice_no is not None:
                d["link_type"] = "Sales Invoice"
                d["linked_name"] = dn_doc.sales_invoice_no
            elif dn_doc.purchase_order is not None:
                d["link_type"] = "Purchase Order"
                d["linked_name"] = dn_doc.purchase_order
            elif dn_doc.purchase_receipt_no is not None:
                d["link_type"] = "Purchase Receipt"
                d["linked_name"] = dn_doc.purchase_receipt_no
            else:
                d["link_type"] = None
                d["linked_name"] = None
        else:
            d["link_type"] = None
            d["linked_name"] = None
    data = []
    for d in temp_data:
        row = [d.posting_date, d.posting_time, d.item_code, d.description, d.actual_qty, d.qty_after_transaction,
               d.warehouse, d.valuation_rate, d.stock_value, d.incoming_rate, d.voucher_no, d.voucher_type,
               d.linked_name, d.name, d.link_type]
        data.append(row)
    return data


def get_conditions(filters):
    conditions = ""
    if filters.get("item"):
        conditions += " and sle.item_code = '%s'" % filters["item"]
    else:
        frappe.msgprint("Please select an Item Code first", raise_exception=1)

    if filters.get("warehouse"):
        conditions += " and sle.warehouse = '%s'" % filters["warehouse"]

    if filters.get("from_date"):
        conditions += " and sle.posting_date >= '%s'" % filters["from_date"]

    if filters.get("to_date"):
        conditions += " and sle.posting_date <= '%s'" % filters["to_date"]

    return conditions
