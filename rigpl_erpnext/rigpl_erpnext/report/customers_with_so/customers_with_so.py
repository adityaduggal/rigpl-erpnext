from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import Count, IfNull, Max, Sum
from frappe.utils import getdate
from pypika.terms import Case
from ....utils.report_utils import tree_and_descendants


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_so_data(filters)

	return columns, data


def get_columns():
	return [
		"Customer ID:Link/Customer:150", "Territory:Link/Territory:150", "Total SO Val:Currency:120",
		"Sale Considered:Currency:120", "# of SO:Int:80", "Avg SO Value:Currency:120",
		"Last SO Date:Date:100", "#Days Since Last SO:Int:80", "Sales Partner:Link/Sales Partner:100",
		"Sales Person:Link/Sales Person:100", "Allocated %:Float:50", "Customer Rating::100",
		"Customer Group:Link/Customer Group:200"
	]


def get_so_data(filters):
	if not filters.get("from_date"):
		frappe.throw("Select from date first")
	if (getdate(filters.get("to_date")) - getdate(filters["from_date"])).days < 0:
		frappe.throw("From Date has to be less than To Date")

	totals = get_so_totals(filters)
	last_so = get_last_so_dates()
	data = []
	for row in get_customers(filters):
		total = totals.get(row[0]) or [None] * 4
		last_date = last_so.get(row[0])
		days = (getdate(filters.get("to_date")) - getdate(last_date)).days if last_date else None
		data.append(row[:2] + list(total) + [last_date, days] + row[2:])
	return data


def get_so_totals(filters):
	"""{customer: [SO total, sale considered, # SO, average]} of the period. A Closed SO counts only
	its delivered part."""
	so = frappe.qb.DocType("Sales Order")
	considered = Sum(Case().when(so.status == "Closed", so.base_net_total * so.per_delivered / 100)
		.else_(so.base_net_total))
	count = Count(so.name).distinct()
	rows = (
		frappe.qb.from_(so)
		.select(so.customer, Sum(so.base_net_total), considered, count, considered / count)
		.where(so.docstatus == 1)
		.where(so.transaction_date >= filters["from_date"])
		.where(so.transaction_date <= filters["to_date"])
		.groupby(so.customer)
		.run()
	)
	return {row[0]: row[1:] for row in rows}


def get_last_so_dates():
	so = frappe.qb.DocType("Sales Order")
	return dict(frappe.qb.from_(so).select(so.customer, Max(so.transaction_date)).where(so.docstatus == 1)
		.groupby(so.customer).run())


def get_customers(filters):
	"""[customer, territory, sales partner, sales person, allocated %, rating, group]: 1 row for each
	Sales Team row of the customer."""
	cu = frappe.qb.DocType("Customer")
	st = frappe.qb.DocType("Sales Team")
	query = (
		frappe.qb.from_(cu)
		.left_join(st).on((st.parent == cu.name) & (st.parenttype == "Customer"))
		.select(cu.name, cu.territory, IfNull(cu.default_sales_partner, "-"), IfNull(st.sales_person, "-"),
			IfNull(st.allocated_percentage, 0), IfNull(cu.customer_rating, "-"), cu.customer_group)
		.where(cu.docstatus == 0)
		.where(cu.disabled == (1 if filters.get("disabled") == 1 else 0))
		.orderby(cu.name)
	)
	if filters.get("customer"):
		query = query.where(cu.name == filters["customer"])
	if filters.get("sales_partner"):
		query = query.where(cu.default_sales_partner == filters["sales_partner"])
	if filters.get("territory"):
		query = query.where(cu.territory.isin(tree_and_descendants("Territory", filters["territory"])))
	if filters.get("sales_person"):
		query = query.where(st.sales_person.isin(tree_and_descendants("Sales Person", filters["sales_person"])))
	return [list(row) for row in query.run()]
