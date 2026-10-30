#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
from frappe.utils import nowdate
from ....utils.report_utils import blank_zeros
from ..pending_orders.pending_orders import get_stock_status_columns, get_stock_status_rows


def execute(filters=None):
	if not filters: filters = {}

	columns = get_stock_status_columns()
	data = [blank_zeros(row) for row in get_stock_status_rows(dict(filters, date=filters.get("date") or nowdate()))]

	return columns, data
