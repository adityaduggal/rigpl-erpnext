from __future__ import unicode_literals
from ....utils.pending_report_utils import check_dates, get_pending_rows
from ....utils.report_utils import blank_zeros


def execute(filters=None):
	if not filters: filters = {}
	check_dates(filters)

	columns = get_columns()
	data = [blank_zeros(row) for row in get_pr_entries(filters)]

	return columns, data


def get_columns():
	return [
		"PR #:Link/Purchase Receipt:120", "Supplier:Link/Supplier:200" ,"Date:Date:100",
		"Item Code:Link/Item:130","Description::350", "PR Qty:Float:70",
		"PR Price:Currency:70", "PR Amount:Currency:80", "PO #:Link/Purchase Order:140",
		"Unbilled Qty:Float:80", "Unbilled Amount:Currency:80"
	]


def get_pr_entries(filters):
	pr_filters = {key: filters.get(key) for key in ("supplier", "from_date", "to_date")}
	return [
		[pr.parent, pr.party, pr.date, pr.item_code, pr.description, pr.qty, pr.base_rate, pr.base_amount,
			pr.prevdoc_docname, pr.pending_qty, pr.pending_amount]
		for pr in get_pending_rows("pr_billing", pr_filters, fields=["child.prevdoc_docname"])
	]
