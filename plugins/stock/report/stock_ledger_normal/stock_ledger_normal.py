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
from webnotes.utils import flt

def execute(filters=None):
	if not filters: filters = {}
	
	columns = get_columns()
	data = get_sl_entries(filters)
		
	return columns, data
	
def get_columns():
	

	return [
		"Date:Date:80", "Time:Time:70" ,"Item:Link/Item:130", "Description::250",
		"Qty:Float/2:60", "Balance:Float/2:90", "Transaction Link::30", 
		"Warehouse::120", "Voucher No::130", "Voucher Type::140","Name::100"
	]
	
def get_sl_entries(filters):
	conditions = get_conditions(filters)
	conditions_item = get_conditions_item(filters)
	
	data = webnotes.conn.sql("""select posting_date, posting_time, item_code, 
		actual_qty, qty_after_transaction, warehouse, voucher_type, voucher_no, 
		name from `tabStock Ledger Entry` where is_cancelled = "No" %s 
		order by posting_date desc, posting_time desc, name desc""" 
		% conditions, as_list=1)
	
	desc = webnotes.conn.sql("""select it.name, it.description FROM `tabItem` it WHERE %s""" 
		%conditions_item, as_list=1)
	
	#webnotes.msgprint(desc)
	for i in range(0,len(data)):
		data[i].insert(3, desc[0][1])
		data[i].insert(6, """<a href="%s"><i class="icon icon-share" style="cursor: pointer;"></i></a>""" \
			% ("/".join(["#Form", data[i][7], data[i][8]]),))
	
	return data
	
def get_conditions(filters):
	conditions = ""
	if filters.get("item"):
		conditions += " and item_code = '%s'" % filters["item"]
	else:
		webnotes.msgprint("Please select an Item Code first", raise_exception=1)
	
	if filters.get("warehouse"):
		conditions += " and warehouse = '%s'" % filters["warehouse"]
	
	if filters.get("from_date"):
		conditions += " and posting_date >= '%s'" % filters["from_date"]
	
	if filters.get("to_date"):
		conditions += " and posting_date <= '%s'" % filters["to_date"]
	
	return conditions
	
def get_conditions_item(filters):
	conditions_item = ""
	if filters.get("item"):
		conditions_item += " it.name = '%s'" % filters["item"]
	else:
		webnotes.msgprint("Please select an Item Code first", raise_exception=1)
	
	return conditions_item