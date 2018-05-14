# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def execute():
	pending_so = frappe.db.sql("""SELECT 
	 so.name as so_name, sod.name as sod_name, so.idx as idx, so.docstatus, sod.item_code, so.selling_price_list,
	 sod.rate, sod.base_rate, sod.net_rate as basic_rate, sod.base_net_rate,
	 so.taxes_and_charges, so.customer, sod.rate/sod.net_rate
	 FROM
	 `tabSales Order` so, `tabSales Order Item` sod
	WHERE
	 sod.parent = so.name
	 AND so.docstatus != 2
	 AND so.docstatus != 0
	 AND so.status != 'Closed'
	 AND so.selling_price_list = 'PL49'
	 AND sod.net_rate != sod.rate
	 AND sod.net_rate > 0
	 AND so.currency = 'INR'
	 AND so.taxes_and_charges != 'OGL'
	 AND ifnull(sod.delivered_qty,0) < ifnull(sod.qty,0)
	ORDER BY so.transaction_date DESC""", as_dict=1)
	for pso in pending_so:
		frappe.db.set_value("Sales Order Item", pso.sod_name, "rate", pso.basic_rate)
		frappe.db.set_value("Sales Order Item", pso.sod_name, "base_rate", pso.basic_rate)
		print("Updated SO# " + str(pso.so_name) + " at Row # " + str(pso.idx) )
	print(len(pending_so))

	pending_dn = frappe.db.sql("""SELECT dn.name as dn_name, dn.customer as cust, dni.item_code, dni.name as dni_name,
	dni.rate as inclusive_rate, dni.base_rate, dni.net_rate as basic_rate, dni.base_net_rate, dn.taxes_and_charges as taxes,
	dni.against_sales_order as so, dni.so_detail as so_detail
     
	
	FROM `tabDelivery Note` dn, `tabDelivery Note Item` dni

	WHERE dn.docstatus = 1 
    	AND dn.name = dni.parent
    	AND dni.against_sales_order IS NOT NULL
    	AND (dni.qty - ifnull((SELECT sum(sid.qty) FROM `tabSales Invoice Item` sid, 
			`tabSales Invoice` si
        	WHERE sid.delivery_note = dn.name
				AND sid.parent = si.name
				AND sid.qty > 0
				AND sid.dn_detail = dni.name), 0)>=0.01)
	
	ORDER BY dn.posting_date ASC  """, as_dict=1)

	for pdn in pending_dn:
		if pdn.taxes != 'OGL' and pdn.taxes != 'RIGB Export Under Bond':
			if pdn.inclusive_rate == pdn.basic_rate:
				sod_doc = frappe.get_doc("Sales Order Item", pdn.so_detail)
				frappe.db.set_value("Delivery Note Item", pdn.dni_name, "rate", sod_doc.net_rate)
				frappe.db.set_value("Delivery Note Item", pdn.dni_name, "net_rate", sod_doc.net_rate)
				frappe.db.set_value("Delivery Note Item", pdn.dni_name, "base_net_rate", sod_doc.net_rate)
				frappe.db.set_value("Delivery Note Item", pdn.dni_name, "base_rate", sod_doc.net_rate)
				print ("Update DN# " + pdn.dn_name + " for Customer " + pdn.cust + " where rates were same")
			else:
				frappe.db.set_value("Delivery Note Item", pdn.dni_name, "rate", pdn.basic_rate)
				frappe.db.set_value("Delivery Note Item", pdn.dni_name, "net_rate", pdn.basic_rate)
				print ("Update DN# " + pdn.dn_name + " for Customer " + pdn.cust + " where rates were different")

	print(len(pending_dn))