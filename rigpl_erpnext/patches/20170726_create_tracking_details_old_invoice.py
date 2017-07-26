# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe, erpnext
from rigpl_erpnext.rigpl_erpnext.scheduled_tasks.shipment_data_update import *
from frappe.utils import getdate, add_days, now_datetime
from rigpl_erpnext.rigpl_erpnext.validations.sales_invoice import check_existing_track, create_new_ship_track

def execute():
	si_list = frappe.db.sql("""SELECT si.name, si.posting_date, si.transporters, si.lr_no
		FROM `tabSales Invoice` si, `tabTransporters` tp 
		WHERE si.docstatus = 1 AND  tp.name = si.transporters 
			AND tp.track_on_shipway = 1 AND si.posting_date > DATE_SUB(NOW(), INTERVAL 360 day)
		ORDER BY si.posting_date DESC""", as_dict=1)
	
	#create_new_ship_track
	for si in si_list:
		si_doc = frappe.get_doc('Sales Invoice', si.name)
		#print str((si))

		if si.posting_date >= getdate(add_days(now_datetime (), -30)):
			#print(str(si.name) + " " + str(si.transporters) + " " + si.lr_no + " " + str(si.posting_date))
			exist_track = check_existing_track(si.name)
			if exist_track:
				pass
			else:
				create_new_ship_track(si_doc)
				print ("Created New Tracking For SI # " + si_doc.name)
