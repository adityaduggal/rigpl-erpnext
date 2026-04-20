from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils import getdate, flt

def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	data = get_pr_entries(filters)

	return columns, data

def get_columns():
	return [
		"PR #:Link/Purchase Receipt:120", "Supplier:Link/Supplier:200" ,"Date:Date:100",
		"Item Code:Link/Item:130","Description::350", "PR Qty:Float:70",
		"PR Price:Currency:70", "PR Amount:Currency:80", "PO #:Link/Purchase Order:140",
		"Unbilled Qty:Float:80", "Unbilled Amount:Currency:80"
	]

def get_pr_entries(filters):
	conditions, params = get_conditions(filters)

	# 1. Base Query: Fetch PR and PRI without correlated subqueries
	pr_items = frappe.db.sql(f"""
		SELECT
			pr.name, pr.supplier, pr.posting_date,
			pri.name as pri_name, pri.item_code, pri.description, 
			pri.qty, pri.base_rate, pri.base_amount, pri.prevdoc_docname
		FROM `tabPurchase Receipt` pr
		JOIN `tabPurchase Receipt Item` pri ON pr.name = pri.parent
		WHERE pr.docstatus = 1 {conditions}
		ORDER BY pr.posting_date ASC
	""", params, as_dict=1)

	if not pr_items:
		return []

	# Get all PR item names
	pri_names = [d.pri_name for d in pr_items]
	
	# 2. Bulk fetch PI Items
	pi_totals = {}
	if pri_names:
		chunk_size = 5000
		for i in range(0, len(pri_names), chunk_size):
			chunk = pri_names[i:i+chunk_size]
			pi_items = frappe.db.sql("""
				SELECT pid.pr_detail, SUM(pid.qty) as billed_qty, SUM(pid.base_amount) as billed_amount
				FROM `tabPurchase Invoice Item` pid
				JOIN `tabPurchase Invoice` pi ON pid.parent = pi.name
				WHERE pi.docstatus = 1 AND pid.pr_detail IN %s
				GROUP BY pid.pr_detail
			""", (tuple(chunk),), as_dict=1)
			
			for pi in pi_items:
				pi_totals.setdefault(pi.pr_detail, {'qty': 0, 'amount': 0})
				pi_totals[pi.pr_detail]['qty'] += flt(pi.billed_qty)
				pi_totals[pi.pr_detail]['amount'] += flt(pi.billed_amount)

	res = []
	for pr in pr_items:
		billed = pi_totals.get(pr.pri_name, {'qty': 0, 'amount': 0})
		unbilled_qty = flt(pr.qty) - billed['qty']
		unbilled_amount = flt(pr.base_amount) - billed['amount']
		
		# Exact original conditions:
		if unbilled_qty >= 1 and unbilled_amount >= 1:
			unbilled_amount_calculated = unbilled_qty * flt(pr.base_rate)
			res.append([
				pr.name, pr.supplier, pr.posting_date,
				pr.item_code, pr.description, pr.qty, pr.base_rate,
				pr.base_amount, pr.prevdoc_docname,
				unbilled_qty, unbilled_amount_calculated
			])
			
	return res

def get_conditions(filters):
	conditions = ""
	params = {}

	if filters.get("supplier"):
		conditions += " AND pr.supplier = %(supplier)s"
		params["supplier"] = filters["supplier"]

	if filters.get("from_date"):
		if filters.get("to_date"):
			if getdate(filters.get("from_date")) > getdate(filters.get("to_date")):
				frappe.msgprint(_("From Date cannot be greater than To Date"), raise_exception=1)
		conditions += " AND pr.posting_date >= %(from_date)s"
		params["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		conditions += " AND pr.posting_date <= %(to_date)s"
		params["to_date"] = filters["to_date"]
		
	return conditions, params
