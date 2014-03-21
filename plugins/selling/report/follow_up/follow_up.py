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

	columns = get_columns(filters)
	data = get_data(filters)

	return columns, data
	
def get_columns(filters):
	if not filters.get("doc_type"):
		webnotes.msgprint("Please select the Type of Follow Up first", raise_exception=1)
	elif filters.get("doc_type") == "Lead":
		if not filters.get("owner") and  not filters.get("contact_by"):
			webnotes.msgprint("Please select either Owner or Next Contact by for Lead", raise_exception=1)
		
	if filters.get("doc_type") == "Lead":
		return [
			"Lead:Link/Lead:100", "Company::250", "Contact::120", "Mobile #::100","Status::100", "Territory::100",
			"Lead Owner::120", "Next Contact By::120", "Next Contact Date:Date:80", "Last Contact Date:Date:80", 
			"Last Communication::300"
		]
	elif filters.get("doc_type") =="Customer":
		return [
			"Customer ID:Link/Customer:150", "Territory:Link/Territory:150", "Total SO Val:Currency:120",
			"Sale Considered:Currency:120", "# of SO:Int:80", "Avg SO Value:Currency:120", "Last SO Date:Date:100", 
			"#Days Since Last SO:Int:80"
		]
def get_data(filters):
	#conditions_cust = get_conditions_cust(filters)
	conditions_lead = get_conditions_lead(filters)
	
	if filters.get("doc_type") == "Lead":
		data = webnotes.conn.sql("""SELECT ld.name, ld.company_name, ld.lead_name,ld.mobile_no, 
		ld.status, ld.territory, ld.lead_owner, ld.contact_by, ld.contact_date
		FROM `tabLead` ld %s 
		ORDER BY ld.name""" %conditions_lead , as_list=1)
		
		
	
	return data

	
def get_conditions_cust(filters):	
	conditions_cust = ""
	
	if filters.get("territory"):
		conditions_cust += " and cu.territory = '%s'" % filters["territory"]
		
	#if filters.get("sales_person"):
	#	conditions_cust += " and cu.territory = '%s'" % filters["sales_person"]
		
	return conditions_cust

def get_conditions_lead(filters):	
	conditions_lead = ""
	
	if filters.get("owner"):
		if not filters.get("next_contact"):
			conditions_lead += " WHERE ld.lead_owner = '%s'" % filters["owner"]
		else:
			webnotes.msgprint("You can only select either owner or next contact by field", raise_exception=1)

	if filters.get("next_contact"):
		if not filters.get("owner"):
			conditions_lead += " where ld.contact_by = '%s'" % filters["next_contact"]
		else: 
			webnotes.msgprint("You can only select either owner or next contact by field", raise_exception=1)
		
	return conditions_lead