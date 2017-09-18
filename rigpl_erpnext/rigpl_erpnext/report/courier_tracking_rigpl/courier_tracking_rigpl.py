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
		return[
			"Transporter:Link/Transporters:150", "Total AWB:Int:80", "Delivered:Int:80"
		]
	elif filters.get("avg_delivery_times"):
		return[
			"Transporter:Link/Transporters:150", "Total Delivered:Int:80", "Avg Time (Days):Float:80",
			"Max Days:Int:80", "Min Days:Int:80"
		]
	else:
		return [
			"Tracking No:Link/Carrier Tracking:100", "Transporter:Link/Transporters:100",
			"AWB No::100", "Status::90", "Code::60", 
			"City::100", "Country::90",
			"Pickup Date:Date:80", "Delivery Date:Date:120", "Duration:Float:80",
			"Ref Doc:Dynamic Link/Document:100", "Integrity:Int:50", "Doc Status::50", 
			"Creation:Date:120", "Document::10"
		]

def get_data(filters):
	conditions, cond_dates = get_conditions(filters)
	if filters.get("total_awb_by_transporter"):
		query = """SELECT carrier_name, COUNT(name),0
			FROM `tabCarrier Tracking`
			WHERE docstatus !=2 %s
			GROUP BY carrier_name
			ORDER BY carrier_name"""%(conditions)
	elif filters.get("avg_delivery_times"):
		query = """SELECT carrier_name, COUNT(name), AVG(DATEDIFF(delivery_date_time, pickup_date)),
			MAX(DATEDIFF(delivery_date_time, pickup_date)), MIN(DATEDIFF(delivery_date_time, pickup_date))
			FROM `tabCarrier Tracking`
			WHERE docstatus !=2 AND status_code = "DEL" %s
			GROUP BY carrier_name
			ORDER BY carrier_name"""%(conditions)
	elif filters.get("detailed_report"):
		query = """SELECT name, carrier_name, awb_number, status, status_code, 
			ship_to_city, country, 
			pickup_date, delivery_date_time, DATEDIFF(IFNULL(delivery_date_time, CURDATE()), IFNULL(pickup_date, creation)),
			document_name, invoice_integrity, docstatus, creation, document
			FROM `tabCarrier Tracking`
			WHERE docstatus!=2 %s
			ORDER BY pickup_date ASC"""%(conditions)
	elif filters.get("pending_exceptions"):
		query = """SELECT name, carrier_name, awb_number, status, status_code, 
			ship_to_city, country, 
			pickup_date, delivery_date_time, DATEDIFF(IFNULL(delivery_date_time, CURDATE()), IFNULL(pickup_date, creation)),
			document_name, invoice_integrity, docstatus, creation, document
			FROM `tabCarrier Tracking`
			WHERE docstatus = 0 AND status_code != 'DEL' AND invoice_integrity = 1 %s
			ORDER BY pickup_date ASC"""%(cond_dates)
	else:
		query = """SELECT name, carrier_name, awb_number, status, status_code, 
			ship_to_city, country, 
			pickup_date, delivery_date_time, DATEDIFF(IFNULL(delivery_date_time, CURDATE()), IFNULL(pickup_date, creation)),
			document_name, invoice_integrity, docstatus, creation, document
			FROM `tabCarrier Tracking`
			WHERE docstatus != 0 AND status_code != 'DEL' %s
			ORDER BY pickup_date ASC""" %(cond_dates)
	data = frappe.db.sql(query, as_list=1)

	return data


def get_conditions(filters):
	conditions = ""
	cond_dates = ""
	if filters.get("from_date"):
		conditions += " AND IFNULL(pickup_date, '%s') >= '%s'" %(filters["from_date"],filters["from_date"])
		cond_dates += " AND IFNULL(pickup_date, '%s') >= '%s'" %(filters["from_date"],filters["from_date"])
	if filters.get("to_date"):
		conditions += " AND IFNULL(pickup_date, '%s') <= '%s'" %(filters["to_date"], filters["to_date"])
		cond_dates += " AND IFNULL(pickup_date, '%s') >= '%s'" %(filters["from_date"],filters["from_date"])
	if filters.get("trandporters"):
		conditions += " AND carrier_name = '%s'" %filters["trandporters"]
	if filters.get("awb_no"):
		conditions += " AND awb_number = '%s'" %filters["awb_no"]
	if filters.get("ref_name"):
		conditions += " AND document_name = '%s'" %filters["ref_name"]

	if filters.get("status"):
		if filters.get("status") == "Delivered":
			conditions += " AND status_code = 'DEL'"
		elif filters.get("status") == "Not Delivered":
			conditions += " AND status_code != 'DEL' AND docstatus = 0"
		elif filters.get("status") == "No Information":
			conditions += " AND status_code = 'NFI'"
		elif filters.get("status") == "Cancelled":
			conditions += " AND (status_code = 'CAN' OR status_code = 'UND')"
		else:
			conditions += " AND status_code != 'CAN' AND status_code != 'NFI' \
				AND status_code != 'DEL' AND status_code != 'UND' "



	report_val = flt(filters.get("total_awb_by_transporter")) + \
		flt(filters.get("avg_delivery_times")) + flt(filters.get("detailed_report")) + \
		flt(filters.get("pending_exceptions")) + flt(filters.get("old_exception"))

	if report_val > 1:
		frappe.throw("Error Only 1 Type of Report Selectable at a time")
	elif report_val == 0:
			frappe.throw("Check atleast one report to get")

	return conditions, cond_dates