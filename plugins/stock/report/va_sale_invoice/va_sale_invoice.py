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
	data = get_va_entries(filters)
		
	return columns, data
	
def get_columns():
	

	return [
		"Posting Date:Date:80", "Name:Link/Sales Invoice:150" ,"Customer:Link/Customer:250", 
		"Item Code:Link/Item:150","Description::350", "Quantity:Float/2:60", 
		"List Price:Float/2:60", "Rate*:Float/2:60", "Amount*:Float/2:90",
		"Status::30", "DN #:Link/Delivery Note:150", "DN Date:Date:80",
		"Base Metal::100", "Tool Type::100", "Height or Dia (mm):Float/3:60",
		"Width (mm):Float/3:60", "Length (mm):Float/2:60", "Material::80", 
		"D1:Float/3:60", "L1:Float/3:60", "Coating::80",
	]
	
def get_va_entries(filters):
	conditions = get_conditions(filters)
	
	si = webnotes.conn.sql(""" select si.posting_date, si.name, si.customer,
			sid.item_code, sid.description, sid.qty, sid.base_ref_rate, sid.basic_rate,
			sid.amount, si.docstatus, sid.delivery_note
			FROM `tabSales Invoice` si, `tabSales Invoice Item` sid
			WHERE sid.parent = si.name and
			si.docstatus = 1 %s
			order by si.posting_date ASC, si.name ASC, sid.item_code ASC, 
			sid.description ASC""" % conditions, as_list=1)
	
	item = webnotes.conn.sql("""SELECT it.name, it.base_material, it.tool_type,
		it.height_dia, it.width, it.length, it.quality, it.d1, it.l1, it.special_treatment
		FROM `tabItem` it ORDER BY it.name""" , as_list=1)
	
	for i in range(0, len(si)):
	
		if (si[i][10]):

			dn_date = webnotes.conn.sql("""SELECT dn.posting_date FROM `tabDelivery Note` dn WHERE dn.name = '%s'""" % si[i][10], as_list=1)
			si[i].insert(11, dn_date[0][0])
		else:
			si[i].insert(11, None)
			
		for j in range (0, len(item)):
			if si[i][3]== item[j][0]:
				if (item[j][1]): #insert base material
					si[i].insert(12,item[j][1])
				else:
					si[i].insert(12,None)
				
				if (item[j][2]): #insert tool type
					si[i].insert(13,item[j][2])
				else:
					si[i].insert(13,None)

				if (item[j][3]): #insert h/d
					si[i].insert(14,item[j][3])
				else:
					si[i].insert(14,None)

				if (item[j][4]): #insert wd
					si[i].insert(15,item[j][4])
				else:
					si[i].insert(15,None)

				if (item[j][5]): #insert ln
					si[i].insert(16,item[j][5])
				else:
					si[i].insert(16,None)

				if (item[j][6]): #insert quality
					si[i].insert(17,item[j][6])
				else:
					si[i].insert(17,None)

				if (item[j][7]): #insert d1
					si[i].insert(18,item[j][7])
				else:
					si[i].insert(18,None)

				if (item[j][8]): #insert l1
					si[i].insert(19,item[j][8])
				else:
					si[i].insert(19,None)

				if (item[j][9]): #insert coating
					si[i].insert(20,item[j][9])
				else:
					si[i].insert(20,None)
	si = sorted(si, key = lambda k: (k[12], k[17], k[13], k[14], 
		k[15], k[18], k[19], k[16], k[3], k[0], k[1]))

	return si
	
def get_conditions(filters):
	conditions = ""	
	if filters.get("from_date"):
		conditions += "and si.posting_date >= '%s'" % filters["from_date"]
	else:
		webnotes.msgprint("Please Select a From Date first", raise_exception=1)
	
	if filters.get("to_date"):
		conditions += "and si.posting_date <= '%s'" % filters["to_date"]
	
	return conditions