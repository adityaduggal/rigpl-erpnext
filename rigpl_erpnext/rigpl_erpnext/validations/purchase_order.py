# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cstr, flt, getdate, new_line_sep
from frappe.desk.reportview import get_match_cond

def validate(doc,method):
	for d in doc.items:
		if d.so_detail:
			sod = frappe.get_doc("Sales Order Item", d.so_detail)
			d.item_code = sod.item_code
			d.description = sod.description

def get_pending_prd(doctype, txt, searchfield, start, page_len, filters):

	return frappe.db.sql("""SELECT DISTINCT(prd.name), prd.sales_order, prd.production_order_date,
	prd.item_description
	FROM `tabProduction Order` prd, `tabSales Order` so, `tabSales Order Item` soi
	WHERE 
		prd.docstatus = 1
		AND so.docstatus = 1 
		AND soi.parent = so.name 
		AND so.status <> "Closed"
		AND soi.qty > soi.delivered_qty
		AND prd.sales_order = so.name
		AND (prd.name like %(txt)s
			or prd.sales_order like %(txt)s)
		{mcond}
	order by
		if(locate(%(_txt)s, prd.name), locate(%(_txt)s, prd.name), 1)
	limit %(start)s, %(page_len)s""".format(**{
		'key': searchfield,
		'mcond': get_match_cond(doctype)
	}), {
		'txt': "%%%s%%" % txt,
		'_txt': txt.replace("%", ""),
		'start': start,
		'page_len': page_len,
	})