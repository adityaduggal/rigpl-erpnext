# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cstr, flt, getdate, new_line_sep
from frappe.desk.reportview import get_match_cond

def validate(doc,method):
	for d in doc.items:
		if doc.is_subcontracting <> 1:
			if d.subcontracted_item:
				frappe.throw(("Subcontracted Item only allowed for Sub Contracting PO. \
					Check Row# {0}. This PO is Not a Subcontracting PO check the box to \
					make this PO as Subcontracting.").format(d.idx))
	for d in doc.items:
		item = frappe.get_doc("Item", d.item_code)
		if doc.is_subcontracting == 1:
			if item.is_sub_contracted_item <> 1:
				frappe.throw(("Only Sub Contracted Items are allowed in Item Code for \
					Sub Contracting PO. Check Row # {0}").format(d.idx))
		else:
			if item.is_purchase_item <> 1:
				frappe.throw(("Only Purchase Items are allowed in Item Code for \
					Purchase Orders. Check Row # {0}").format(d.idx))
		if d.so_detail:
			sod = frappe.get_doc("Sales Order Item", d.so_detail)
			if doc.is_subcontracting <> 1:
				d.item_code = sod.item_code
			else:
				d.subcontracted_item = sod.item_code
			d.description = sod.description
		if doc.is_subcontracting == 1:
			sub_item = frappe.get_doc("Item", d.subcontracted_item)
			if d.so_detail:
				pass
			else:
				d.description = sub_item.description
			if d.subcontracted_item is None or d.subcontracted_item == "" :
				frappe.throw(("Subcontracted Item is Mandatory for Subcontracting Purchase Order\
					Check Row #{0}").format(d.idx))
			if d.from_warehouse is None or d.from_warehouse == "" :
				frappe.throw(("From Warehouse is Mandatory for Subcontracting Purchase Order\
					Check Row #{0}").format(d.idx))
			check_warehouse(doc,method, d.from_warehouse)

def on_submit(doc,method):
	if doc.is_subcontracting == 1:
		chk_ste = get_existing_ste(doc,method)
		if chk_ste:
			if len(chk_ste)>1:
				frappe.throw("More than 1 Stock Entry Exists for the Same PO. ERROR!!!")
			else:
				name = chk_ste[0][0]
				ste_exist = frappe.get_doc("Stock Entry", name)
				ste_exist.submit()
				frappe.msgprint('{0}{1}'.format("Submitted STE# ", ste_exist.name))
		else:
			frappe.throw("No Stock Entry Found for this PO")
	
def on_cancel(doc,method):
	if doc.is_subcontracting == 1:
		chk_ste = get_existing_ste(doc,method)
		if chk_ste:
			if len(chk_ste)>1:
				frappe.throw("More than 1 Stock Entry Exists for the Same PO. ERROR!!!")
			else:
				name = chk_ste[0][0]
				ste_exist = frappe.get_doc("Stock Entry", name)
				ste_exist.cancel()
				frappe.msgprint('{0}{1}'.format("Cancelled STE# ", ste_exist.name))
		else:
			frappe.msgprint("No Stock Entry Found for this PO")

def on_update(doc,method):
	if doc.is_subcontracting == 1:
		create_ste(doc,method)
	
def create_ste(doc, method):
	ste_items = get_ste_items(doc,method)
	chk_ste = get_existing_ste(doc,method)
	if chk_ste:
		if len(chk_ste)>1:
			frappe.throw("More than 1 Stock Entry Exists for the Same PO. ERROR!!!")
		else:
			ste_name = chk_ste[0][0]
			ste_exist = frappe.get_doc("Stock Entry", ste_name)
			ste_exist.items = []
			for i in ste_items:
				ste_exist.append("items", i)
			ste_exist.posting_date = doc.transaction_date
			ste_exist.posting_time = '23:59:59'
			ste_exist.purpose = "Material Transfer"
			ste_exist.purchase_order = doc.name
			ste_exist.remarks = "Material Transfer Entry for PO#" + doc.name
			ste_exist.save()
			frappe.msgprint('{0}{1}'.format("Updated STE# ", ste_exist.name))
	else:
		ste = frappe.get_doc({
				"doctype": "Stock Entry",
				"purpose": "Material Transfer",
				"posting_date": doc.transaction_date,
				"posting_time": '23:59:59',
				"purchase_order": doc.name,
				"remarks": "Material Transfer Entry for PO#" + doc.name,
				"items": ste_items
				})
		ste.insert()
		frappe.msgprint('{0}{1}'.format("Created STE# ", ste.name))

def get_ste_items(doc,method):
	ste_items = []
	target_warehouse = frappe.db.sql("""SELECT name FROM `tabWarehouse` 
		WHERE is_subcontracting_warehouse =1""", as_list=1)
	target_warehouse = target_warehouse[0][0]
	for d in doc.items:
		ste_temp = {}
		ste_temp.setdefault("s_warehouse", d.from_warehouse)
		ste_temp.setdefault("t_warehouse", target_warehouse)
		ste_temp.setdefault("item_code", d.subcontracted_item)
		item = frappe.get_doc("Item", d.subcontracted_item)
		if d.stock_uom == item.stock_uom:
			ste_temp.setdefault("qty", d.qty)
		else:
			ste_temp.setdefault("qty", d.conversion_factor)
		ste_items.append(ste_temp)
	return ste_items
	
def get_existing_ste(doc,method):
	chk_ste = frappe.db.sql("""SELECT ste.name FROM `tabStock Entry` ste
		WHERE ste.docstatus <> 2 AND
		ste.purchase_order = '%s'"""% doc.name, as_list=1)
	return chk_ste
	
def check_warehouse(doc,method, wh):
	warehouse = frappe.get_doc("Warehouse", wh)
	if warehouse.is_subcontracting_warehouse == 1:
		frappe.throw(("Warehouse {0} is not allowed to be Selected in PO# {1}").format\
			(warehouse.name, doc.name))
			
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