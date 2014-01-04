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
	data = get_so_data(filters)
	
	return columns, data
	
def get_columns():
	return [
		"Customer ID:Link/Customer:150", "Territory:Link/Territory:150", "Total SO Val:Currency:120",
		"Sale Considered:Currency:120", "# of SO:Int:80", "Avg SO Value:Currency:120", "Last SO Date:Date:100", 
		"#Days Since Last SO:Int:80"
	]
	
def get_so_data(filters):
	conditions = get_conditions(filters)
	conditions_cust = get_conditions_cust(filters)
	
	if (filters.get("from_date")):
		diff = (getdate(filters.get("to_date")) - getdate(filters.get("from_date"))).days
		if diff < 0:
			webnotes.msgprint("From Date has to be less than To Date", raise_exception=1)
	else:
		webnotes.msgprint("Select from date first",raise_exception =1)
	
	data = webnotes.conn.sql("""select so.customer, sum(so.net_total),
	sum(if(so.status = "Stopped", so.net_total * so.per_delivered/100, so.net_total)), count(distinct so.name),
	sum(if(so.status = "Stopped", so.net_total * so.per_delivered/100, so.net_total))/count(distinct so.name)
	from `tabSales Order` so where so.docstatus = 1 %s group by customer
	order by so.customer""" %conditions , as_list=1)
	
	cust_tbl = webnotes.conn.sql("""select cu.name, cu.territory
	from `tabCustomer` cu %s order by cu.name""" %conditions_cust, as_list=1)
	
	last_so = webnotes.conn.sql("""select so.customer, max(so.transaction_date), so.name
	from `tabSales Order` so where so.docstatus = 1 group by so.customer""", as_list=1)
	
	for i in cust_tbl:
		#Below loop would add the Territory to the data
		if any (i[0] in s for s in data):
			for j in data:
				if i[0] == j[0]:
					if j[1] is None:
						i.insert(2,None)
					else:
						i.insert(2,j[1])
					
					if j[2] is None:
						i.insert(3,None)
					else:
						i.insert(3,j[2])

					if j[3] is None:
						i.insert(4,None)
					else:
						i.insert(4,j[3])
					
					if j[4] is None:
						i.insert(5,None)
					else:
						i.insert(5,j[4])
		else:
			i.insert(2,None)
			i.insert(3,None)
			i.insert(4,None)
			i.insert(5,None)
		
		if any (i[0] in s for s in last_so):
			for j in last_so:
				if i[0] == j[0]:
					if j[1] is None:
						i.insert(6,None)
					else:
						i.insert(6,j[1])
		else:
			i.insert(6,None)
		
		if not i[6]:
			i.insert(7,None)
		else:
			days_last_so = (getdate(filters.get("to_date")) - getdate(i[6])).days
			i.insert(7,days_last_so)
	return cust_tbl

	
	
def get_conditions(filters):
	conditions = ""
	
	if filters.get("from_date"):
		conditions += " and so.transaction_date >= '%s'" % filters["from_date"]
	
	if filters.get("to_date"):
		conditions += " and so.transaction_date <= '%s'" % filters["to_date"]
	return conditions
	
def get_conditions_cust(filters):	
	conditions_cust = ""
	
	if filters.get("territory"):
		conditions_cust += " where cu.territory = '%s'" % filters["territory"]
		
	return conditions_cust

