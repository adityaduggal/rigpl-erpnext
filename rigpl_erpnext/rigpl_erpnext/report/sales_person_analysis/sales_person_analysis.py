# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import datetime
import time
from frappe import msgprint, _

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
    date_field = filters["doc_type"] == "Sales Order" and "transaction_date" or "posting_date"
    conditions_sperson = get_conditions(filters, date_field)[0]
    conditions_so = get_conditions(filters, date_field)[1]
    conditions_si = get_conditions(filters, date_field)[2]

    query = """SELECT
		sp.sales_person_name, spt.target_amount,

		(SELECT SUM(so.base_net_total) FROM `tabSales Order` so, `tabSales Team` st
		WHERE st.sales_person = sp.name AND st.parent = so.name AND so.docstatus = 1 %s),

		(SELECT SUM(si.base_net_total) FROM `tabSales Invoice` si, `tabSales Team` st
		WHERE st.sales_person = sp.name AND st.parent = si.name AND si.docstatus = 1 %s),

		(SELECT SUM(si.outstanding_amount) FROM `tabSales Invoice` si, `tabSales Team` st
		WHERE st.sales_person = sp.name AND st.parent = si.name AND si.docstatus = 1 %s)

		FROM
			`tabSales Person` sp
			LEFT JOIN `tabTarget Detail` spt ON spt.parent = sp.name
				AND spt.parenttype = 'Sales Person'

		WHERE
			sp.is_group = 'No' %s
		ORDER BY sp.sales_person_name""" % (conditions_so, conditions_si, conditions_si, conditions_sperson)

    #frappe.msgprint(query)

    data = frappe.db.sql(query , as_list=1)

    return data

def get_conditions(filters, date_field):
    conditions_sperson = ""
    conditions_so = ""
    conditions_si = ""

    if filters.get("sales_person"):
        conditions_sperson += " AND sp.name = '%s'" % \
            filters["sales_person"].replace("'", "\'")

        conditions_so += " AND st.sales_person = '%s'" % \
            filters["sales_person"].replace("'", "\'")

        conditions_si += " AND st.sales_person = '%s'" % \
            filters["sales_person"].replace("'", "\'")

    if filters.get("fiscal_year"):
        conditions_sperson += " AND spt.fiscal_year = '%s'" % \
            filters["fiscal_year"].replace("'", "\'")

        #conditions_so += " AND so.fiscal_year = '%s'" % \
        #filters["fiscal_year"].replace("'", "\'")

        #conditions_si += " AND si.fiscal_year = '%s'" % \
        #filters["fiscal_year"].replace("'", "\'")

    if filters.get("from_date"):
        conditions_so += " AND so.transaction_date >= '%s'" % \
            filters["from_date"].replace("'", "\'")

        conditions_si += " AND si.posting_date >= '%s'" % \
            filters["from_date"].replace("'", "\'")

    if filters.get("to_date"):
        conditions_so += " AND so.transaction_date <= '%s'" % \
            filters["to_date"].replace("'", "\'")

        conditions_si += " AND si.posting_date <= '%s'" % \
            filters["to_date"].replace("'", "\'")

    return conditions_sperson, conditions_so, conditions_si
