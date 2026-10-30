from __future__ import unicode_literals
import frappe
from frappe.utils import flt
from ....utils.pending_report_utils import check_dates, get_doc_values, get_pending_rows
from ....utils.report_utils import blank_zeros


def execute(filters=None):
	if not filters: filters = {}
	check_dates(filters)

	columns = get_columns(filters)
	data = [blank_zeros(row) for row in get_dn_entries(filters)]

	return columns, data


def get_columns(filters):
	if filters.get("summary") != 1:
		return [
			"DN_No:Link/Delivery Note:120", "Customer:Link/Customer:200", "Date:Date:100",
			"Item_Code:Link/Item:130", "Description::350", "DN_Qty:Float:90",
			"DN_Price:Currency:100", "DN Amount:Currency:120", "SO_No:Link/Sales Order:140",
			"SO_Date:Date:80", "Trial::60"
		]
	else:
		return [
			"Customer:Link/Customer:200", "Payment Terms::250", "Rating::60",
			"Total DN#:Int:80", "No of Items:Int:80",
			"Earliest DN Date:Date:80", "Total Qty:Int:80", "Total Value:Currency:150"
		]


def get_dn_entries(filters):
	dn_filters = {key: filters.get(key) for key in ("customer", "from_date", "to_date", "territory", "draft")}
	rows = get_pending_rows("dn_billing", dn_filters, fields=["child.against_sales_order"])
	if filters.get("summary") == 1:
		return get_summary(rows)
	sales_orders = get_doc_values("Sales Order", [dn.against_sales_order for dn in rows],
		["transaction_date", "track_trial"])
	data = []
	for dn in rows:
		so = sales_orders.get(dn.against_sales_order) or frappe._dict()
		data.append([dn.parent, dn.party, dn.date, dn.item_code, dn.description, dn.qty, dn.base_rate,
			dn.base_amount, dn.against_sales_order, so.transaction_date, "Yes" if so.track_trial == 1 else "No"])
	return data


def get_summary(rows):
	"""One row for each Customer, the Customer with the oldest DN first"""
	customers = {}
	for dn in rows:
		cust = customers.setdefault(dn.party, frappe._dict(dns=set(), rows=0, date=dn.date, qty=0, amount=0))
		cust.dns.add(dn.parent)
		cust.rows += 1
		cust.date = min(cust.date, dn.date)
		cust.qty += flt(dn.qty)
		cust.amount += flt(dn.base_amount)
	details = get_doc_values("Customer", customers, ["payment_terms", "customer_rating"])
	data = []
	for name, cust in sorted(customers.items(), key=lambda item: item[1].date):
		cu = details.get(name) or frappe._dict()
		data.append([name, cu.payment_terms, cu.customer_rating, len(cust.dns), cust.rows, cust.date,
			cust.qty, cust.amount])
	return data
