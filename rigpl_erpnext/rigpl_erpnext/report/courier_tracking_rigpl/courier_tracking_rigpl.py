# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt
"""
Courier Tracking RIGPL (#173). One Report Type select picks the view. Each view runs one query
and returns its rows, a chart and summary cards made from the same rows.
"""
import math
from typing import Dict, List, Optional, Sequence, Tuple

import frappe
from frappe.query_builder.functions import Avg, Count, CurDate, IfNull, Max, Min
from frappe.utils import add_days, cint, flt, getdate
from pypika import Case, Order

from ...shipping import status as st
from ...shipping.dashboard import DATEDIFF
from ...shipping.validations import cost_over_limit
from ....utils.report_utils import blank_zeros

PENDING = "Pending Exceptions"
DETAILED = "Detailed"
TOTAL_AWB = "Total AWB by Transporter"
AVG_DELIVERY = "Avg Delivery Time"
OLD_EXCEPTIONS = "Old Exceptions"
PERFORMANCE = "Carrier Performance"
POD_COVERAGE = "POD Coverage"
COST = "Cost vs Charged"
REPORT_TYPES = (PENDING, DETAILED, TOTAL_AWB, AVG_DELIVERY, OLD_EXCEPTIONS, PERFORMANCE, POD_COVERAGE, COST)
NOT_SHIPPED = (st.CANCELLED, st.NOT_BOOKED)
CHART_CARRIERS = 5

def execute(filters=None):
	filters = frappe._dict(filters or {})
	report_type = str(filters.get("report_type") or PENDING)
	if report_type not in VIEWS:
		frappe.throw(f"Report Type {report_type} is not known. Select one of: {', '.join(REPORT_TYPES)}.",
			title="Unknown Report Type")
	validate_dates(filters)
	columns, rows, chart, summary = VIEWS[report_type](filters)
	data = [blank_zeros([row.get(c["fieldname"]) for c in columns]) for row in rows]
	return columns, data, None, chart, summary


def validate_dates(filters):
	filters.from_date = getdate(filters.get("from_date") or add_days(getdate(), -90))
	filters.to_date = getdate(filters.get("to_date") or getdate())
	if filters.from_date > filters.to_date:
		frappe.throw("From Date must be on or before To Date.", title="Wrong Period")


def filtered(query, filters, dates: bool = True):
	"""Adds the filters of the report to a query on Carrier Tracking as parameters."""
	ct = frappe.qb.DocType("Carrier Tracking")
	if dates:
		query = query.where(ct.creation >= filters.from_date).where(ct.creation < add_days(filters.to_date, 1))
	for filter_name, field in (("transporter", ct.carrier_name), ("from_address", ct.from_address),
			("status", ct.status), ("awb_no", ct.awb_number), ("document_name", ct.document_name),
			("receiver_name", ct.receiver_name)):
		value = filters.get(filter_name)
		if value:
			query = query.where(field == str(value))
	return query


# ------------------------------------------------------------------ list views

def column(label, fieldname, fieldtype="Data", width=100, options=None, hidden=0) -> Dict:
	col = {"label": label, "fieldname": fieldname, "fieldtype": fieldtype, "width": width}
	if options:
		col["options"] = options
	if hidden:
		col["hidden"] = 1
	return col


def tracking_columns(detailed: bool) -> List[Dict]:
	cols = [
		column("Tracking No", "name", "Link", 100, "Carrier Tracking"),
		column("Transporter", "carrier_name", "Link", 120, "Transporters"),
		column("AWB No", "awb_number"),
		column("Status", "status", width=90),
		column("Code", "status_code", width=60),
		column("Receiver", "receiver_name", "Dynamic Link", 200, "receiver_document"),
	]
	if detailed:
		cols += [column("Weight", "total_weight", "Float", 60), column("Cost", "shipment_cost", "Currency", 80)]
	cols += [column("City", "ship_to_city"), column("Country", "country", width=90),
		column("Pickup Date", "pickup_date", "Date", 90)]
	if detailed:
		cols.append(column("From Address", "from_address", "Link", 150, "Address"))
	cols += [
		column("Delivery Date", "delivery_date_time", "Datetime", 140),
		column("Days", "days", "Int", 60),
		column("Ref Doc", "document_name", "Dynamic Link", 120, "document"),
		column("Integrity", "invoice_integrity", "Check", 60),
		column("Doc Status", "docstatus", "Int", 60),
		column("Creation", "creation", "Date", 100),
	]
	if detailed:
		cols.append(column("Created By", "owner", "Link", 100, "User"))
	cols += [column("Document", "document", hidden=1), column("Receiver Type", "receiver_document", hidden=1)]
	return cols


def tracking_query():
	ct = frappe.qb.DocType("Carrier Tracking")
	adr = frappe.qb.DocType("Address")
	return (
		frappe.qb.from_(ct)
		.left_join(adr).on(adr.name == ct.to_address)
		.select(
			ct.name, ct.carrier_name, ct.awb_number, ct.status, ct.status_code, ct.receiver_name,
			ct.receiver_document, ct.total_weight, ct.shipment_cost, ct.ship_to_city, adr.country.as_("country"),
			ct.pickup_date, ct.from_address, ct.delivery_date_time, ct.document_name, ct.document,
			ct.invoice_integrity, ct.docstatus, ct.creation, ct.owner,
			DATEDIFF(IfNull(ct.delivery_date_time, CurDate()), IfNull(ct.pickup_date, ct.creation)).as_("days"),
		)
		.orderby(ct.creation, order=Order.asc)
	)


def pending_exceptions(filters):
	ct = frappe.qb.DocType("Carrier Tracking")
	query = (
		tracking_query().where(ct.docstatus < 2).where(ct.status != st.DELIVERED)
		.where(ct.manual_exception_removed == 0)
	)
	rows = filtered(query, filters, dates=False).run(as_dict=True)
	days = [cint(r.days) for r in rows]
	chart = bar_chart(*count_by(rows, "carrier_name"), name="Pending")
	summary = [
		card("Pending", len(rows), "Int", "Red" if rows else "Green"),
		card("Oldest (Days)", max(days, default=0), "Int", "Orange"),
		card("Avg Age (Days)", average(days), "Float", "Blue"),
	]
	return tracking_columns(detailed=True), rows, chart, summary


def detailed(filters):
	ct = frappe.qb.DocType("Carrier Tracking")
	rows = filtered(tracking_query().where(ct.docstatus < 2), filters).run(as_dict=True)
	delivered = [r for r in rows if r.status == st.DELIVERED]
	labels, values = count_by(rows, "status")
	chart = {"data": {"labels": labels, "datasets": [{"name": "Trackings", "values": values}]}, "type": "donut"}
	summary = [
		card("Total", len(rows), "Int", "Blue"),
		card("Delivered", len(delivered), "Int", "Green"),
		card("Avg Transit Days", average([cint(r.days) for r in delivered if r.pickup_date]), "Float", "Blue"),
		card("Total Cost", round(sum(flt(r.shipment_cost) for r in rows), 2), "Currency", "Orange"),
	]
	return tracking_columns(detailed=True), rows, chart, summary


def old_exceptions(filters):
	ct = frappe.qb.DocType("Carrier Tracking")
	query = tracking_query().where(ct.docstatus == 1).where(ct.status != st.DELIVERED)
	rows = filtered(query, filters).run(as_dict=True)
	days = [cint(r.days) for r in rows]
	chart = bar_chart(*count_by(rows, "status"), name="Trackings")
	summary = [
		card("Not Delivered", len(rows), "Int", "Red" if rows else "Green"),
		card("Oldest (Days)", max(days, default=0), "Int", "Orange"),
	]
	return tracking_columns(detailed=False), rows, chart, summary


# ------------------------------------------------------------------ grouped views

def total_awb(filters):
	ct = frappe.qb.DocType("Carrier Tracking")
	query = (
		frappe.qb.from_(ct)
		.select(
			ct.carrier_name, Count(ct.name).as_("total"),
			Count(Case().when(ct.status == st.DELIVERED, 1)).as_("delivered"),
			Count(Case().when(ct.manual_exception_removed == 1, 1)).as_("exceptions"),
		)
		.where(ct.docstatus < 2)
		.groupby(ct.carrier_name)
		.orderby(ct.carrier_name)
	)
	rows = filtered(query, filters).run(as_dict=True)
	columns = [
		column("Transporter", "carrier_name", "Link", 200, "Transporters"),
		column("Total AWB", "total", "Int", 90),
		column("Delivered", "delivered", "Int", 90),
		column("Exception", "exceptions", "Int", 90),
	]
	labels = [r.carrier_name or "" for r in rows]
	chart = bar_chart(labels, [r.total for r in rows], name="Total AWB",
		more=[("Delivered", [r.delivered for r in rows]), ("Exception", [r.exceptions for r in rows])])
	total, delivered = sum(cint(r.total) for r in rows), sum(cint(r.delivered) for r in rows)
	summary = [
		card("Total AWB", total, "Int", "Blue"),
		card("Delivered %", percent(delivered, total), "Percent", "Green"),
		card("Exceptions", sum(cint(r.exceptions) for r in rows), "Int", "Orange"),
	]
	return columns, rows, chart, summary


def avg_delivery(filters):
	ct = frappe.qb.DocType("Carrier Tracking")
	transit = DATEDIFF(ct.delivery_date_time, ct.pickup_date)
	query = (
		frappe.qb.from_(ct)
		.select(ct.carrier_name, Count(ct.name).as_("delivered"), Count(transit).as_("timed"),
			Avg(transit).as_("avg_days"), Max(transit).as_("max_days"), Min(transit).as_("min_days"))
		.where(ct.docstatus < 2)
		.where(ct.status == st.DELIVERED)
		.groupby(ct.carrier_name)
		.orderby(ct.carrier_name)
	)
	rows = filtered(query, filters).run(as_dict=True)
	columns = [
		column("Transporter", "carrier_name", "Link", 200, "Transporters"),
		column("Total Delivered", "delivered", "Int", 100),
		column("Avg Time (Days)", "avg_days", "Float", 100),
		column("Max Days", "max_days", "Int", 80),
		column("Min Days", "min_days", "Int", 80),
	]
	chart = bar_chart([r.carrier_name or "" for r in rows], [round(flt(r.avg_days), 1) for r in rows],
		name="Avg Days")
	delivered = sum(cint(r.delivered) for r in rows)
	weighted = sum(flt(r.avg_days) * cint(r.timed) for r in rows)
	timed = sum(cint(r.timed) for r in rows)
	summary = [
		card("Delivered", delivered, "Int", "Green"),
		card("Overall Avg Days", round(weighted / timed, 1) if timed else 0, "Float", "Blue"),
	]
	return columns, rows, chart, summary


def pod_coverage(filters):
	ct = frappe.qb.DocType("Carrier Tracking")
	has_pod = (ct.pod_file.isnotnull()) & (ct.pod_file != "")
	query = (
		frappe.qb.from_(ct)
		.select(ct.carrier_name, Count(ct.name).as_("delivered"), Count(Case().when(has_pod, 1)).as_("with_pod"))
		.where(ct.docstatus < 2)
		.where(ct.status == st.DELIVERED)
		.groupby(ct.carrier_name)
		.orderby(ct.carrier_name)
	)
	rows = filtered(query, filters).run(as_dict=True)
	for row in rows:
		row.without_pod = cint(row.delivered) - cint(row.with_pod)
		row.coverage = percent(row.with_pod, row.delivered)
	columns = [
		column("Transporter", "carrier_name", "Link", 200, "Transporters"),
		column("Delivered", "delivered", "Int", 90),
		column("With POD", "with_pod", "Int", 90),
		column("Without POD", "without_pod", "Int", 100),
		column("Coverage %", "coverage", "Percent", 100),
	]
	chart = bar_chart([r.carrier_name or "" for r in rows], [r.with_pod for r in rows], name="With POD",
		more=[("Without POD", [r.without_pod for r in rows])], stacked=True)
	delivered, with_pod = sum(cint(r.delivered) for r in rows), sum(cint(r.with_pod) for r in rows)
	summary = [
		card("Delivered", delivered, "Int", "Blue"),
		card("With POD", with_pod, "Int", "Green"),
		card("Coverage %", percent(with_pod, delivered), "Percent", "Green" if with_pod == delivered else "Orange"),
	]
	return columns, rows, chart, summary


def cost_vs_charged(filters):
	ct = frappe.qb.DocType("Carrier Tracking")
	tpt = frappe.qb.DocType("Transporters")
	query = (
		frappe.qb.from_(ct)
		.left_join(tpt).on(tpt.name == ct.carrier_name)
		.select(ct.name, ct.carrier_name, ct.awb_number, ct.document, ct.document_name, ct.amount,
			ct.shipment_cost, ct.courier_charged, tpt.max_percent_of_invoice_value.as_("max_percent"))
		.where(ct.docstatus < 2)
		.where((ct.shipment_cost > 0) | (ct.courier_charged > 0))
		.orderby(ct.creation, order=Order.asc)
	)
	rows = filtered(query, filters).run(as_dict=True)
	for row in rows:
		annotate_cost(row)
	columns = [
		column("Tracking No", "name", "Link", 100, "Carrier Tracking"),
		column("Transporter", "carrier_name", "Link", 150, "Transporters"),
		column("AWB No", "awb_number"),
		column("Ref Doc", "document_name", "Dynamic Link", 120, "document"),
		column("Invoice Amount", "amount", "Currency", 110),
		column("Shipment Cost", "shipment_cost", "Currency", 100),
		column("Courier Charged", "courier_charged", "Currency", 100),
		column("Difference", "difference", "Currency", 100),
		column("Cost % of Invoice", "cost_percent", "Percent", 100),
		column("Max %", "max_percent", "Percent", 70),
		column("Over Limit", "over_limit", "Check", 70),
		column("Document", "document", hidden=1),
	]
	cost, charged = sum_by(rows, "carrier_name", "shipment_cost"), sum_by(rows, "carrier_name", "courier_charged")
	labels = list(cost)
	chart = bar_chart(labels, [cost[k] for k in labels], name="Shipment Cost",
		more=[("Courier Charged", [charged[k] for k in labels])], fieldtype="Currency")
	over = sum(r.over_limit for r in rows)
	summary = [
		card("Shipment Cost", round(sum(cost.values()), 2), "Currency", "Orange"),
		card("Courier Charged", round(sum(charged.values()), 2), "Currency", "Blue"),
		card("Over Limit", over, "Int", "Red" if over else "Green"),
	]
	return columns, rows, chart, summary


def annotate_cost(row):
	"""Adds difference, cost percent and the over limit flag. A Max % of 0 means no limit is set."""
	row.difference = flt(row.courier_charged) - flt(row.shipment_cost)
	row.cost_percent = flt(row.shipment_cost) / flt(row.amount) * 100 if flt(row.amount) > 0 else 0
	row.over_limit = 1 if cost_over_limit(row.shipment_cost, row.amount, flt(row.max_percent) or None) else 0


# ------------------------------------------------------------------ carrier performance

def carrier_performance(filters):
	ct = frappe.qb.DocType("Carrier Tracking")
	query = (
		frappe.qb.from_(ct)
		.select(ct.carrier_name, ct.creation, ct.status, ct.pickup_date, ct.delivery_date_time,
			ct.expected_delivery_date)
		.where(ct.docstatus < 2)
	)
	rows = aggregate_performance(filtered(query, filters).run(as_dict=True))
	columns = [
		column("Transporter", "carrier_name", "Link", 180, "Transporters"),
		column("Month", "month", width=80),
		column("Shipped", "shipped", "Int", 80),
		column("Delivered", "delivered", "Int", 80),
		column("RTO", "rto", "Int", 60),
		column("Closed No Update", "closed", "Int", 90),
		column("Avg Days", "avg_days", "Float", 80),
		column("P90 Days", "p90_days", "Int", 80),
		column("Max Days", "max_days", "Int", 80),
		column("On Time %", "on_time", "Percent", 90),
	]
	totals = aggregate_performance_totals(rows)
	summary = [
		card("Shipped", totals["shipped"], "Int", "Blue"),
		card("Delivered", totals["delivered"], "Int", "Green"),
		card("RTO", totals["rto"], "Int", "Red" if totals["rto"] else "Green"),
		card("P90 Days", totals["p90_days"], "Int", "Orange"),
		card("On Time %", totals["on_time"], "Percent", "Blue"),
	]
	return columns, rows, performance_chart(rows), summary


def aggregate_performance(trackings: Sequence[Dict]) -> List[frappe._dict]:
	"""One row for each carrier and month of creation, sorted by carrier and month."""
	groups = {}
	for t in trackings:
		key = (t.get("carrier_name") or "", getdate(t["creation"]).strftime("%Y-%m"))
		groups.setdefault(key, []).append(t)
	rows = []
	for (carrier, month), group in sorted(groups.items()):
		row = frappe._dict(carrier_name=carrier, month=month)
		row.update(performance_stats(group))
		rows.append(row)
	return rows


def performance_stats(trackings: Sequence[Dict]) -> Dict:
	delivered = [t for t in trackings if t.get("status") == st.DELIVERED]
	days = sorted(d for d in (transit_days(t) for t in delivered) if d is not None)
	with_expected = [t for t in delivered if t.get("expected_delivery_date") and t.get("delivery_date_time")]
	on_time = [t for t in with_expected if getdate(t["delivery_date_time"]) <= getdate(t["expected_delivery_date"])]
	return {
		"shipped": len([t for t in trackings if t.get("status") not in NOT_SHIPPED]),
		"delivered": len(delivered),
		"rto": len([t for t in trackings if t.get("status") == st.RTO]),
		"closed": len([t for t in trackings if t.get("status") == st.CLOSED]),
		"avg_days": average(days),
		"p90_days": percentile(days, 90),
		"max_days": max(days, default=0),
		"on_time": percent(len(on_time), len(with_expected)),
		"days": days,
		"on_time_count": len(on_time),
		"expected_count": len(with_expected),
	}


def aggregate_performance_totals(rows: Sequence[Dict]) -> Dict:
	days = sorted(d for r in rows for d in r["days"])
	on_time = sum(r["on_time_count"] for r in rows)
	expected = sum(r["expected_count"] for r in rows)
	return {
		"shipped": sum(r["shipped"] for r in rows),
		"delivered": sum(r["delivered"] for r in rows),
		"rto": sum(r["rto"] for r in rows),
		"p90_days": percentile(days, 90),
		"on_time": percent(on_time, expected),
	}


def performance_chart(rows: Sequence[Dict]) -> Optional[Dict]:
	"""On Time % by month, one line for each of the carriers that shipped most."""
	months = sorted({r["month"] for r in rows})
	if not months:
		return None
	shipped = sum_by(rows, "carrier_name", "shipped")
	carriers = sorted(shipped, key=lambda c: -shipped[c])[:CHART_CARRIERS]
	by_key = {(r["carrier_name"], r["month"]): r["on_time"] for r in rows}
	datasets = [{"name": c, "values": [by_key.get((c, m), 0) for m in months]} for c in carriers]
	return {"data": {"labels": months, "datasets": datasets}, "type": "line", "fieldtype": "Percent"}


def transit_days(tracking: Dict) -> Optional[int]:
	if not tracking.get("pickup_date") or not tracking.get("delivery_date_time"):
		return None
	return (getdate(tracking["delivery_date_time"]) - getdate(tracking["pickup_date"])).days


# ------------------------------------------------------------------ small helpers

def percentile(sorted_values: Sequence[float], pct: float) -> float:
	"""Nearest-rank percentile of values sorted from low to high. 0 for no values."""
	if not sorted_values:
		return 0
	rank = max(1, math.ceil(pct / 100 * len(sorted_values)))
	return sorted_values[rank - 1]


def average(values: Sequence[float]) -> float:
	return round(sum(values) / len(values), 1) if values else 0


def percent(part, whole) -> float:
	return round(flt(part) * 100 / flt(whole), 1) if flt(whole) else 0


def count_by(rows: Sequence[Dict], field: str) -> Tuple[List[str], List[int]]:
	counts = {}
	for row in rows:
		key = row.get(field) or "Not Set"
		counts[key] = counts.get(key, 0) + 1
	labels = sorted(counts, key=lambda k: -counts[k])
	return labels, [counts[k] for k in labels]


def sum_by(rows: Sequence[Dict], key_field: str, value_field: str) -> Dict[str, float]:
	sums = {}
	for row in rows:
		key = row.get(key_field) or "Not Set"
		sums[key] = sums.get(key, 0) + flt(row.get(value_field))
	return sums


def bar_chart(labels, values, name, more=(), stacked=False, fieldtype="Int") -> Optional[Dict]:
	if not labels:
		return None
	datasets = [{"name": name, "values": list(values)}]
	datasets += [{"name": n, "values": list(v)} for n, v in more]
	chart = {"data": {"labels": list(labels), "datasets": datasets}, "type": "bar", "fieldtype": fieldtype}
	if stacked:
		chart["barOptions"] = {"stacked": 1}
	return chart


def card(label, value, datatype, indicator) -> Dict:
	return {"label": label, "value": value, "datatype": datatype, "indicator": indicator}


VIEWS = {
	PENDING: pending_exceptions,
	DETAILED: detailed,
	TOTAL_AWB: total_awb,
	AVG_DELIVERY: avg_delivery,
	OLD_EXCEPTIONS: old_exceptions,
	PERFORMANCE: carrier_performance,
	POD_COVERAGE: pod_coverage,
	COST: cost_vs_charged,
}
