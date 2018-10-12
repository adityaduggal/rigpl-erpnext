# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

#This scheduled tasks runs to check the status of Work Orders
#Some Work Orders of HSP,CSP and JCNO are submitted but not closed
#All of those Work Orders if the Status of SO is delivered or closed then close


def execute():
	wo_list = frappe.db.sql("""SELECT name, production_order_date, 
		production_item, status, docstatus, so_detail, sales_order
		FROM `tabWork Order` WHERE docstatus != 2 
		AND status != 'Completed' AND status != 'Stopped'
		AND so_detail IS NOT NULL 
		ORDER BY production_order_date""", as_dict=1)

	if wo_list:
		sno = 0
		for wo in wo_list:
			sno += 1
			wo_doc = frappe.get_doc("Work Order", wo.name)
			so_doc = frappe.get_doc("Sales Order", wo.sales_order)
			so_detail = frappe.get_doc("Sales Order Item", wo.so_detail)
			if so_detail.qty == so_detail.delivered_qty:
				frappe.db.set_value("Work Order", wo.name, "status", "Completed")
				print (str(sno) + " " +  "Work Order # " + wo.name + \
					" Completed as Material is Delivered")
			elif so_doc.status == 'Closed':
				frappe.db.set_value("Work Order", wo.name, "status", "Stopped")
				print (str(sno) + " " + "Work Order # " + wo.name + \
					"Stopped as Sales Order is Stopped")
			else:
				print(str(sno) + " Work Order No: " + wo.name + " Dated: " \
					+ str(wo_doc.production_order_date) + " NOT DELIVERED" + \
					" Work Order Status is " + str(wo_doc.docstatus))