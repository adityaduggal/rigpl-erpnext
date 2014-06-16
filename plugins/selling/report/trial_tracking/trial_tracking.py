# ERPNext - web based ERP (http://erpnext.com)
# Copyright (C) 2012 Web Notes Technologies Pvt Ltd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals
import webnotes
from webnotes.utils import flt, getdate, nowdate

def execute(filters=None):
	if not filters: filters = {}
	
	columns = get_columns()
	data = get_trial_data(filters)
	
	return columns, data
	
def get_columns():
	return [
		"Trial Status::100", "SO #:Link/Sales Order:100", "SO Date:Date:90", "Customer:Link/Customer:150",
		"Item:Link/Item:120", "Description::350", "Qty:Float/2:60", "PL:Currency:80",
		"Rate:Currency:80", "Amount:Currency:100", "Delivered Qty:Float/2:80", "Sales Person::200"
	]
	
def get_trial_data(filters):
	conditions = get_conditions(filters)
	
	data = webnotes.conn.sql("""select so.trial_status, so.name , so.transaction_date, so.customer,
	soi.item_code, soi.description, soi.qty, soi.ref_rate, soi.export_rate,
	soi.export_amount, soi.delivered_qty, st.sales_person
	from `tabSales Order` so, `tabSales Order Item` soi, `tabSales Team` st
	where so.docstatus = 1 and so.order_type = "Trial Order" 
	and soi.parent = so.name and st.parenttype = "Sales Order" 
	and st.parent = so.name %s 
	order by so.transaction_date""" %conditions , as_list=1)

	return data

	
	
def get_conditions(filters):
	
	conditions = ""
	if (filters.get("from_date")):
		if (filters.get("to_date")):
			if getdate(filters.get("to_date")) < getdate(filters.get("from_date")):	
				webnotes.msgprint("From Date has to be less than To Date", raise_exception=1)
			elif (getdate(filters.get("to_date"))- getdate(filters.get("from_date"))).days>1000:
				webnotes.msgprint("Period should be less than 1000 days", raise_exception=1)

		conditions += " and so.transaction_date >= '%s'" % filters["from_date"]
	else:
		webnotes.msgprint("Please select From Date", raise_exception = 1)
		
	if filters.get("to_date"):
		conditions += " and so.transaction_date <= '%s'" % filters["to_date"]

	if filters.get("trial_status"):
		conditions += " and so.trial_status = '%s'" % filters["trial_status"]


	if filters.get("customer"):
		conditions += " and so.customer = '%s'" % filters["customer"]
		
	return conditions


