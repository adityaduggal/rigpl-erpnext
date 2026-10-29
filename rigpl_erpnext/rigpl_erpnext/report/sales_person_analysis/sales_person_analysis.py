# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import Sum
from ....utils.report_utils import blank_zeros

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns(filters)
    data = get_entries(filters)

    return columns, data

def get_columns(filters):
    return [
        "Sales Person:Link/Sales Person:150","FY Target:Currency:100","SO Booked:Currency:100",
        "SI Raised:Currency:100", "Est AR:Currency:100"
        #, "D::100", "E::100", "F::100", "G::100", "H::100", "J::100", #"K::100","L::100","M::100", "N::100"
    ]

def get_entries(filters):
    so_totals = get_totals(filters, "Sales Order", "transaction_date", ["base_net_total"])
    si_totals = get_totals(filters, "Sales Invoice", "posting_date", ["base_net_total", "outstanding_amount"])
    data = []
    for person, name, target in get_persons(filters):
        so = so_totals.get(person, (None,))
        si = si_totals.get(person, (None, None))
        data.append(blank_zeros([name, target, so[0], si[0], si[1]]))
    return data


def get_persons(filters):
    """Return (name, sales_person_name, target_amount) of each Sales Person that is not a group."""
    sp = frappe.qb.DocType("Sales Person")
    spt = frappe.qb.DocType("Target Detail")
    query = (
        frappe.qb.from_(sp)
        .left_join(spt)
        .on((spt.parent == sp.name) & (spt.parenttype == "Sales Person"))
        .select(sp.name, sp.sales_person_name, spt.target_amount)
        .where(sp.is_group == 0)
        .orderby(sp.sales_person_name)
    )
    if filters.get("sales_person"):
        query = query.where(sp.name == filters["sales_person"])
    if filters.get("fiscal_year"):
        query = query.where(spt.fiscal_year == filters["fiscal_year"])
    return query.run()


def get_totals(filters, doctype, date_field, fields):
    """Return {sales_person: (sum of each field)} of the submitted documents in the dates."""
    doc = frappe.qb.DocType(doctype)
    st = frappe.qb.DocType("Sales Team")
    query = (
        frappe.qb.from_(st)
        .join(doc)
        .on(doc.name == st.parent)
        .select(st.sales_person, *[Sum(doc[field]) for field in fields])
        .where((st.parenttype == doctype) & (doc.docstatus == 1))
        .groupby(st.sales_person)
    )
    if filters.get("sales_person"):
        query = query.where(st.sales_person == filters["sales_person"])
    if filters.get("from_date"):
        query = query.where(doc[date_field] >= filters["from_date"])
    if filters.get("to_date"):
        query = query.where(doc[date_field] <= filters["to_date"])
    return {row[0]: row[1:] for row in query.run()}
