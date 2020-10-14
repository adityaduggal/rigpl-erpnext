# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def get_columns(filters):
	if filters.get("total_awb_by_transporter"):
		return [
			"Transporter:Link/Transporters:150", "Total AWB:Int:80", "Delivered:Int:80", "Exception:Int:80"
		]
	elif filters.get("avg_delivery_times"):
		return [
			"Transporter:Link/Transporters:150", "Total Delivered:Int:80", "Avg Time (Days):Float:80",
			"Max Days:Int:80", "Min Days:Int:80"
		]
	else:
		return [
			"Tracking No:Link/Carrier Tracking:100", "Transporter:Link/Transporters:100",
			"AWB No::100", "Status::90", "Code::60",
			"Receiver:Dynamic Link/Receiver Name:200", "Weight:Float:60", "Cost:Currency:80",
			"City::100", "Country::90", "Pickup Date:Date:80", "From Address::150",
			"Delivery Date:Date:120", "Duration:Float:80",
			"Ref Doc:Dynamic Link/Document:100", "Integrity:Int:50", "Doc Status::50",
			"Creation:Date:120", "Created By:Link/User:100", "Document::10", "Receiver Name::10"
		]


def get_data(filters):
	conditions, cond_dates = get_conditions(filters)
	if filters.get("total_awb_by_transporter"):
		query = """SELECT ct.carrier_name, COUNT(ct.name) as total, 
			COUNT(CASE WHEN ct.status = 'Delivered' THEN 1 END) as del, 
			COUNT(CASE WHEN ct.manual_exception_removed = 1 THEN 1 END) as excep
			FROM `tabCarrier Tracking` ct
			WHERE ct.docstatus !=2 %s
			GROUP BY ct.carrier_name
			ORDER BY ct.carrier_name""" % (conditions)
	elif filters.get("avg_delivery_times"):
		query = """SELECT ct.carrier_name, COUNT(ct.name), AVG(DATEDIFF(ct.delivery_date_time, ct.pickup_date)),
			MAX(DATEDIFF(ct.delivery_date_time, ct.pickup_date)), 
			MIN(DATEDIFF(ct.delivery_date_time, ct.pickup_date))
			FROM `tabCarrier Tracking` ct
			WHERE ct.docstatus !=2 AND ct.status = "Delivered" %s
			GROUP BY ct.carrier_name
			ORDER BY ct.carrier_name""" % (conditions)
	elif filters.get("detailed_report"):
		query = """SELECT ct.name, ct.carrier_name, ct.awb_number, ct.status, ct.status_code, 
			ct.receiver_name, CAST(IFNULL(ct.total_weight,0) AS DECIMAL(10,2)), 
			IFNULL(ct.shipment_cost, 0), 
			IFNULL(ct.ship_to_city, 'X'), adr.country, IFNULL(ct.pickup_date, '1900-01-01'), 
			IFNULL(ct.from_address,"X"), ct.delivery_date_time, 
			DATEDIFF(IFNULL(ct.delivery_date_time, CURDATE()), IFNULL(ct.pickup_date, ct.creation)),
			ct.document_name, ct.invoice_integrity, ct.docstatus, ct.creation, ct.owner, 
			ct.document, ct.receiver_document
			FROM `tabCarrier Tracking` ct, `tabAddress` adr
			WHERE ct.docstatus!=2 AND ct.to_address = adr.name %s
			ORDER BY ct.creation ASC""" % (conditions)
	elif filters.get("pending_exceptions"):
		query = """SELECT ct.name, ct.carrier_name, ct.awb_number, ct.status, ct.status_code, 
			ct.receiver_name, CAST(IFNULL(ct.total_weight,0) AS DECIMAL(10,2)), 
			IFNULL(ct.shipment_cost, 0), 
			IFNULL(ct.ship_to_city, 'X'), adr.country, ct.pickup_date, IFNULL(ct.from_address,"X"), 
			ct.delivery_date_time, 
			DATEDIFF(IFNULL(ct.delivery_date_time, CURDATE()), IFNULL(ct.pickup_date, ct.creation)),
			ct.document_name, ct.invoice_integrity, ct.docstatus, ct.creation, ct.owner, 
			ct.document, ct.receiver_document
			FROM `tabCarrier Tracking` ct, `tabAddress` adr
			WHERE ct.docstatus != 2 AND ct.status != "Delivered" 
				AND ct.manual_exception_removed = 0 AND ct.to_address = adr.name
			ORDER BY ct.creation ASC"""
	else:
		query = """SELECT ct.name, ct.carrier_name, ct.awb_number, ct.status, ct.status_code, 
			ct.receiver_name, ct.ship_to_city, adr.country, 
			ct.pickup_date, ct.delivery_date_time, DATEDIFF(IFNULL(ct.delivery_date_time, CURDATE()), 
			IFNULL(ct.pickup_date, ct.creation)), ct.document_name, ct.invoice_integrity, 
			ct.docstatus, ct.creation, ct.document, ct.receiver_document
			FROM `tabCarrier Tracking` ct, `tabAddress` adr
			WHERE ct.docstatus != 0 AND ct.status != 'Delivered'  AND ct.to_address = adr.name %s
			ORDER BY ct.creation ASC""" % (cond_dates)
	data = frappe.db.sql(query, as_list=1)

	return data


def get_conditions(filters):
	conditions = ""
	cond_dates = ""
	if filters.get("from_date"):
		conditions += " AND ct.creation >= '%s'" % (filters["from_date"])
		cond_dates += " AND ct.creation >= '%s'" % (filters["from_date"])
	if filters.get("to_date"):
		conditions += " AND ct.creation <= '%s'" % (filters["to_date"])
		cond_dates += " AND ct.creation <= '%s'" % (filters["from_date"])
	if filters.get("transporter"):
		conditions += " AND ct.carrier_name = '%s'" % filters["transporter"]
	if filters.get("awb_no"):
		conditions += " AND ct.awb_number = '%s'" % filters["awb_no"]
	if filters.get("document_name"):
		conditions += " AND ct.document_name = '%s'" % filters["document_name"]

	if filters.get("status"):
		if filters.get("status") == "Delivered":
			conditions += " AND ct.status_code = 'DEL'"
		elif filters.get("status") == "Not Delivered":
			conditions += " AND ct.status_code != 'DEL' AND ct.docstatus = 0"
		elif filters.get("status") == "No Information":
			conditions += " AND ct.status_code = 'NFI'"
		elif filters.get("status") == "Cancelled":
			conditions += " AND (ct.status_code = 'CAN' OR ct.status_code = 'UND')"
		else:
			conditions += " AND ct.status_code != 'CAN' AND ct.status_code != 'NFI' AND ct.status_code != 'DEL' " \
						  "AND ct.status_code != 'UND' "

	if filters.get("from_address"):
		conditions += " AND ct.from_address = '%s'" % (filters["from_address"])

	if filters.get("receiver_name"):
		conditions += " AND ct.receiver_name = '%s'" % (filters["receiver_name"])

	report_val = flt(filters.get("total_awb_by_transporter")) + flt(filters.get("avg_delivery_times")) + \
				 flt(filters.get("detailed_report")) + flt(filters.get("pending_exceptions")) + \
				 flt(filters.get("old_exception"))

	if report_val > 1:
		frappe.throw("Error Only 1 Type of Report Selectable at a time")
	elif report_val == 0:
		frappe.throw("Check atleast one report to get")
	return conditions, cond_dates
