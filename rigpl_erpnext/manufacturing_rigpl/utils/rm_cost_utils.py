# -*- coding: utf-8 -*-
# Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt
"""
Batched reads of the RM that the submitted Job Cards used, and its real (FIFO) cost from the
Stock Ledger, for the RM Wastage Analysis and RM Cost of Items Made reports.
"""

import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import flt

from ...utils.item_attribute_utils import chunks, get_attribute_map, get_attribute_rows


def get_rm_job_cards(from_date, to_date, bom_template=None):
    """
    Returns the submitted Job Cards of the RM operations posted from `from_date` to `to_date`, with
    the BOM Template of their Process Sheet.
    """
    jc = frappe.qb.DocType("Process Job Card RIGPL")
    ps = frappe.qb.DocType("Process Sheet")
    query = (
        frappe.qb.from_(jc)
        .join(ps).on(ps.name == jc.process_sheet)
        .select(
            jc.name, jc.posting_date, jc.production_item, jc.sales_order_item, jc.process_sheet,
            jc.total_completed_qty, jc.total_rejected_qty, jc.modified_by, ps.bom_template,
        )
        .where(jc.docstatus == 1)
        .where(jc.allow_consumption_of_rm == 1)
        .where(jc.posting_date[from_date:to_date])
        .orderby(jc.posting_date)
    )
    if bom_template:
        query = query.where(ps.bom_template == bom_template)
    return query.run(as_dict=True)


def get_rm_rows(job_cards):
    """{Job Card: [RM rows (item_code, qty, calculated_qty, bypass_qty_check)]}, 1 query per chunk."""
    rows = {}
    for chunk in chunks(job_cards):
        for row in frappe.get_all(
            "Process Sheet Items",
            filters={"parenttype": "Process Job Card RIGPL", "parentfield": "rm_consumed", "parent": ("in", chunk)},
            fields=["parent", "item_code", "qty", "calculated_qty", "bypass_qty_check"],
            order_by="parent, idx",
        ):
            rows.setdefault(row.pop("parent"), []).append(row)
    return rows


def get_rm_costs(job_cards):
    """
    {(Job Card, RM item): (qty out, cost)} from the Stock Ledger rows of the Stock Entries of the
    Job Cards: the outgoing rows only, with their real cost. 1 query per chunk.
    """
    ste = frappe.qb.DocType("Stock Entry")
    sle = frappe.qb.DocType("Stock Ledger Entry")
    costs = {}
    for chunk in chunks(job_cards):
        rows = (
            frappe.qb.from_(sle)
            .join(ste).on((ste.name == sle.voucher_no) & (sle.voucher_type == "Stock Entry"))
            .select(ste.process_job_card, sle.item_code, Sum(sle.actual_qty), Sum(sle.stock_value_difference))
            .where(ste.process_job_card.isin(chunk))
            .where(ste.docstatus == 1)
            .where(sle.is_cancelled == 0)
            .where(sle.actual_qty < 0)
            .groupby(ste.process_job_card, sle.item_code)
            .run()
        )
        for job_card, item_code, qty, value in rows:
            costs[(job_card, item_code)] = (-flt(qty), -flt(value))
    return costs


def get_fg_attribute_values(job_cards, attributes):
    """
    {Job Card: {attribute: value}} of the FG items of the Job Cards. A variant uses its own
    attributes; a special item the Made to Order Item Attributes of its Sales Order Item.
    """
    items = [d.production_item for d in job_cards]
    variant_values = get_attribute_map(items, attributes)
    special = [d for d in job_cards if d.production_item not in variant_values and d.sales_order_item]
    mto_values = {}
    if special:
        docs = {}
        for chunk in chunks(d.sales_order_item for d in special):
            for doc in frappe.get_all("Made to Order Item Attributes", filters={
                    "docstatus": 1, "sales_order_item": ("in", chunk)}, fields=["name", "item_code", "sales_order_item"]):
                docs[(doc.item_code, doc.sales_order_item)] = doc.name
        rows = get_attribute_rows(docs.values(), parenttype="Made to Order Item Attributes")
        for key, doc in docs.items():
            mto_values[key] = {r.attribute: r.attribute_value for r in rows.get(doc, []) if r.attribute in attributes}
    return {
        d.name: variant_values.get(d.production_item) or mto_values.get((d.production_item, d.sales_order_item), {})
        for d in job_cards
    }
