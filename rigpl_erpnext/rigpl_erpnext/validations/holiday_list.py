# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from datetime import datetime, timedelta
from frappe.utils import getdate

def validate(doc,method):
	yr_start = getdate(doc.from_date)
	yr_end = getdate(doc.to_date)
	if doc.is_base_list == 1:
		doc.base_holiday_list = ""
	else:
		holiday_list_based_on = frappe.db.sql("""SELECT name FROM `tabHoliday List` 
			WHERE base_holiday_list = '%s'"""%(doc.name),as_dict=1)
		if holiday_list_based_on:
			frappe.throw("Holiday List {} already is Base List for {} and hence Cannot \
				be made non-base Holiday List".format(doc.name, holiday_list_based_on[0].name))
		if doc.base_holiday_list == "":
			frappe.throw("Base Holiday List Mandatory for {}".format(doc.name))
		else:
			base_holiday = frappe.get_value("Holiday List", doc.base_holiday_list, "is_base_list")
			if base_holiday != 1:
				frappe.throw("Base Holiday List {} Selected is Not a Base \
					Holiday List in {}".format(doc.base_holiday_list, doc.name))
	for d in doc.holidays:
		d.holiday_date = getdate(d.holiday_date)
		if d.holiday_date < yr_start or d.holiday_date > yr_end:
			frappe.msgprint(("""Error in Row# {0} has {1} date as {2} but it is not within 
			FY {3}""").format(d.idx, d.description, d.holiday_date, doc.fiscal_year), raise_exception=1)