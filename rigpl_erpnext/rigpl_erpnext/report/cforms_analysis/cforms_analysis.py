from __future__ import unicode_literals
import frappe
import datetime
import math
from frappe.utils import flt, getdate
from ....utils.item_attribute_utils import chunks


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns(filters)
	data = get_va_entries(filters)

	return columns, data


def exceil(x, s):
	return s * math.ceil(float(x) / s)


def get_columns(filters):
	if filters.get("summary") == 1:
		return ["Customer:Link/Customer:200", "Net Total:Currency:100", "Grand Total:Currency:100",
				"Fiscal Year::100", "Customer Taxes::100"]
	else:
		return ["Invoice Date:Date:80", "Invoice#:Link/Sales Invoice:110", "Customer:Link/Customer:200",
				"Taxes::100", "Customer Taxes::100", "Net Total:Currency:100",
				"Grand Total:Currency:100", "Fiscal Year::100",
				"Q::30", "C-Form:Link/C-Form:130", "C-Form #::100",
				"State::100", "Received On:Date:80"]


def get_va_entries(filters):
	if not filters.get("status"):
		frappe.throw("Please Select the Status of C-Form first")
	received = filters.get("status") == "Received"
	rows = get_invoices(filters, received)
	cust_taxes = get_customer_taxes({row.customer for row in rows})
	years = frappe.get_all("Fiscal Year", fields=["name", "year_start_date", "year_end_date"])
	for row in rows:
		row.fy = next((fy.name for fy in years if fy.year_start_date <= row.posting_date <= fy.year_end_date), None)
		row.cust_taxes = cust_taxes.get(row.customer)
	rows = [row for row in rows if row.fy and row.customer in cust_taxes]

	if filters.get("summary") == 1:
		totals = {}
		for row in rows:
			total = totals.setdefault((row.fy, row.customer), [row.customer, 0, 0, row.fy, row.cust_taxes])
			total[1] += flt(row.net_total)
			total[2] += flt(row.grand_total)
		return [totals[key] for key in sorted(totals, key=lambda k: (k[0], k[1].casefold()))]

	si = []
	for row in rows:
		cform = [row.cform, row.c_form_no, row.state, row.received_date] if received else [None, None, None]
		si.append([row.posting_date, row.name, row.customer, row.taxes_and_charges, row.cust_taxes, row.net_total,
			row.grand_total, row.fy, get_quarter(row.posting_date)] + cform)
	return sorted(si, key=lambda k: (k[0], k[1], k[2], k[3] or ""))


def get_quarter(posting_date):
	mo = posting_date.month
	if mo < 4:
		return "Q4"
	elif mo < 7:
		return "Q1"
	elif mo < 10:
		return "Q2"
	return "Q3"


def get_customer_taxes(customers):
	"""{customer: default_taxes_and_charges}. A join to Customer made MariaDB read all Customers
	first (about 3s)."""
	taxes = {}
	for chunk in chunks(customers):
		taxes.update(frappe.get_all("Customer", filters={"name": ("in", chunk)},
			fields=["name", "default_taxes_and_charges"], as_list=1))
	return taxes


def get_invoices(filters, received):
	si = frappe.qb.DocType("Sales Invoice")
	query = (
		frappe.qb.from_(si)
		.select(si.posting_date, si.name, si.customer, si.taxes_and_charges, si.net_total, si.grand_total)
		.where((si.docstatus == 1) & (si.c_form_applicable == "Yes"))
		.orderby(si.customer)
		.orderby(si.name)
	)
	if received:
		cf = frappe.qb.DocType("C-Form")
		query = query.where(si.c_form_no.isnotnull())
		if filters.get("summary") != 1:
			query = (query.join(cf).on(cf.name == si.c_form_no)
				.select(cf.name.as_("cform"), cf.c_form_no, cf.state, cf.received_date))
	else:
		query = query.where(si.c_form_no.isnull())
	for start, end in get_date_ranges(filters):
		query = query.where(si.posting_date[start:end])
	if filters.get("customer"):
		query = query.where(si.customer == filters["customer"])
	if filters.get("date"):
		query = query.where(si.posting_date <= filters["date"])
	if filters.get("letter_head"):
		query = query.where(si.letter_head == filters["letter_head"])
	return query.run(as_dict=1)


QUARTERS = {"Q1": ((0, 4, 1), (0, 6, 30)), "Q2": ((0, 7, 1), (0, 9, 30)), "Q3": ((0, 10, 1), (0, 12, 31)),
	"Q4": ((1, 1, 1), (1, 3, 31))}


def get_date_ranges(filters):
	"""The (start, end) ranges of the Fiscal Year and Quarter filters."""
	if filters.get("quarter") and not filters.get("fiscal_year"):
		frappe.throw("Please select fiscal year before selecting Quarter")
	if not filters.get("fiscal_year"):
		return []
	start, end = frappe.db.get_value("Fiscal Year", filters["fiscal_year"], ["year_start_date", "year_end_date"])
	ranges = [(start, end)]
	if filters.get("quarter") in QUARTERS:
		year = getdate(start).year
		(add_from, m_from, d_from), (add_to, m_to, d_to) = QUARTERS[filters["quarter"]]
		ranges.append((datetime.date(year + add_from, m_from, d_from), datetime.date(year + add_to, m_to, d_to)))
	return ranges
