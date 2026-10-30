"""
Common base for the reports of open document rows (#182): Pending Orders, Orders To Dispatch,
Pending Orders With Stock Status, DN To Be Billed and PR to be Billed.

Each report names a flow from `FLOWS` and calls `get_pending_rows`. The pending qty of a row is
its qty minus the qty already done: the delivered qty of a Sales Order row, or the qty of the
invoice rows linked through `dn_detail` / `pr_detail`. The invoice qty comes from one grouped
subquery, so the query count does not depend on the row count.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import frappe
from frappe.query_builder import Order
from frappe.query_builder.functions import IfNull, Sum
from frappe.utils import flt, getdate
from pypika.terms import Tuple as QbTuple

from .item_attribute_utils import attribute_filters, chunks

FLOWS = {
    "so_delivery": frappe._dict(
        parent="Sales Order", party="customer", date="transaction_date",
        statuses=["To Deliver and Bill", "To Deliver", "On Hold"], done_field="delivered_qty", min_qty=0,
    ),
    "dn_billing": frappe._dict(
        parent="Delivery Note", party="customer", date="posting_date", skip_status=["Completed"],
        invoice="Sales Invoice", invoice_link="delivery_note", invoice_detail="dn_detail",
        invoice_dates=True, positive_invoice_qty=True, min_qty=0.01,
    ),
    # No status filter: a Completed Purchase Receipt can still have a row that is not billed by qty
    "pr_billing": frappe._dict(
        parent="Purchase Receipt", party="supplier", date="posting_date", skip_status=[],
        invoice="Purchase Invoice", invoice_link="purchase_receipt", invoice_detail="pr_detail",
        min_qty=1, min_amount=1,
    ),
}


def get_pending_rows(
    flow_name: str, filters: dict, fields: Sequence[str] = (), order: Order = Order.asc
) -> List[frappe._dict]:
    """
    Returns the open rows of a flow, oldest first or newest first, as dicts with: parent, date,
    party, row_name, idx, item_code, description, qty, base_rate, base_amount, pending_qty,
    pending_amount and each of `fields` ("parent.<field>" or "child.<field>", named after the field).

    Filters: party (customer or supplier), item, from_date, to_date, territory (of the Customer),
    bm (Base Material), made_to_order (1 = only, 0 = none) and draft (count draft invoices).
    """
    flow = FLOWS[flow_name]
    parent, child = frappe.qb.DocType(flow.parent), frappe.qb.DocType(flow.parent + " Item")
    tables = {"parent": parent, "child": child}
    query = (
        frappe.qb.from_(parent)
        .join(child).on(child.parent == parent.name)
        .select(
            parent.name.as_("parent"), parent[flow.date].as_("date"), parent[flow.party].as_("party"),
            child.name.as_("row_name"), child.idx, child.item_code, child.description, child.qty,
            child.base_rate, child.base_amount,
        )
        .where(get_parent_filters(flow, parent, filters))
        .where(get_item_filters(child, filters))
        .orderby(parent[flow.date], order=order)
        .orderby(parent.name, order=order)
        .orderby(child.idx)
    )
    for field in fields:
        table, fieldname = field.split(".")
        query = query.select(tables[table][fieldname])
    if filters.get("made_to_order") in (0, 1):
        it = frappe.qb.DocType("Item")
        query = query.join(it).on(it.name == child.item_code).where(it.made_to_order == filters["made_to_order"])

    if flow.invoice:
        billed = get_invoiced_qty_query(flow, filters)
        done_qty, done_amount = IfNull(billed.qty, 0), IfNull(billed.amount, 0)
        query = query.left_join(billed).on(billed.detail == child.name)
    else:
        done_qty = IfNull(child[flow.done_field], 0)
    pending_qty = IfNull(child.qty, 0) - done_qty
    query = query.select(pending_qty.as_("pending_qty"))
    if flow.min_qty:
        query = query.where(pending_qty >= flow.min_qty)
    else:
        query = query.where(pending_qty > 0)
    if flow.min_amount:
        query = query.where(child.base_amount - done_amount >= flow.min_amount)

    rows = query.run(as_dict=True)
    for row in rows:
        row.pending_amount = flt(row.pending_qty) * flt(row.base_rate)
    return rows


def get_parent_filters(flow, parent, filters):
    criteria = [parent.docstatus == 1]
    if flow.statuses:
        criteria.append(parent.status.isin(flow.statuses))
    if flow.skip_status:
        criteria.append(parent.status.notin(flow.skip_status))
    if filters.get(flow.party):
        criteria.append(parent[flow.party] == filters[flow.party])
    if filters.get("from_date"):
        criteria.append(parent[flow.date] >= filters["from_date"])
    if filters.get("to_date"):
        criteria.append(parent[flow.date] <= filters["to_date"])
    if filters.get("territory") and flow.party == "customer":
        cu = frappe.qb.DocType("Customer")
        terr, group = frappe.qb.DocType("Territory"), frappe.qb.DocType("Territory").as_("group")
        territories = (
            frappe.qb.from_(terr)
            .join(group).on((terr.lft >= group.lft) & (terr.rgt <= group.rgt))
            .select(terr.name)
            .where(group.name == filters["territory"])
        )
        criteria.append(parent.customer.isin(
            frappe.qb.from_(cu).select(cu.name).where(cu.territory.isin(territories))))
    criterion = criteria[0]
    for term in criteria[1:]:
        criterion &= term
    return criterion


def get_item_filters(child, filters):
    criterion = attribute_filters(child.item_code, {"Base Material": filters.get("bm")})
    if filters.get("item"):
        criterion &= child.item_code == filters["item"]
    return criterion


def get_invoiced_qty_query(flow, filters):
    """Returns a subquery "billed" with the invoiced qty and amount of each row of the flow"""
    inv, inv_item = frappe.qb.DocType(flow.invoice), frappe.qb.DocType(flow.invoice + " Item")
    parent = frappe.qb.DocType(flow.parent)
    query = (
        frappe.qb.from_(inv_item)
        .join(inv).on(inv.name == inv_item.parent)
        .select(
            inv_item[flow.invoice_detail].as_("detail"), Sum(inv_item.qty).as_("qty"),
            Sum(inv_item.base_amount).as_("amount"),
        )
        .where(inv_item[flow.invoice_link].isin(
            frappe.qb.from_(parent).select(parent.name).where(get_parent_filters(flow, parent, filters))))
        .where((inv.docstatus != 2) if filters.get("draft") else (inv.docstatus == 1))
        .groupby(inv_item[flow.invoice_detail])
    )
    if flow.positive_invoice_qty:
        query = query.where(inv_item.qty > 0)
    if flow.invoice_dates and filters.get("from_date"):
        query = query.where(inv.posting_date >= filters["from_date"])
    if flow.invoice_dates and filters.get("to_date"):
        query = query.where(inv.posting_date <= filters["to_date"])
    return query.as_("billed")


def get_bin_qtys(pairs: Iterable[Tuple[str, str]]) -> Dict[Tuple[str, str], frappe._dict]:
    """
    Returns {(item_code, warehouse): {actual_qty, reserved_qty}} of the Bins of the pairs
    """
    bn = frappe.qb.DocType("Bin")
    bins = {}
    for chunk in chunks(list(set(pairs))):
        for row in (
            frappe.qb.from_(bn)
            .select(bn.item_code, bn.warehouse, bn.actual_qty, bn.reserved_qty)
            .where(QbTuple(bn.item_code, bn.warehouse).isin([QbTuple(*pair) for pair in chunk]))
            .run(as_dict=True)
        ):
            bins[(row.item_code, row.warehouse)] = row
    return bins


def get_process_sheets(so_items: Iterable[str]) -> Dict[str, List[str]]:
    """
    Returns {sales_order_item: [Process Sheets that are not cancelled, oldest first]}
    """
    ps = frappe.qb.DocType("Process Sheet")
    sheets = {}
    for chunk in chunks(list(set(so_items))):
        for name, so_item in (
            frappe.qb.from_(ps)
            .select(ps.name, ps.sales_order_item)
            .where(ps.docstatus != 2)
            .where(ps.sales_order_item.isin(chunk))
            .orderby(ps.creation)
            .run()
        ):
            sheets.setdefault(so_item, []).append(name)
    return sheets


def get_doc_values(doctype: str, names: Iterable[str], fields: Sequence[str]) -> Dict[str, frappe._dict]:
    """
    Returns {name: {fields}} of the documents, read in one query per chunk
    """
    values = {}
    for chunk in chunks([name for name in set(names) if name]):
        for row in frappe.get_all(doctype, filters={"name": ["in", chunk]}, fields=["name"] + list(fields)):
            values[row.name] = row
    return values


def check_dates(filters: dict, required: Optional[str] = None):
    if required and not filters.get(required):
        frappe.throw("Please select a Date first")
    if filters.get("from_date") and filters.get("to_date") and \
            getdate(filters["from_date"]) > getdate(filters["to_date"]):
        frappe.throw("From Date cannot be greater than To Date")
