# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from datetime import datetime, timedelta
from frappe.utils import getdate

def validate(doc,method):
	yr_start = getdate(doc.from_date)
	yr_end = getdate(doc.to_date)
	for d in doc.holidays:
		d.holiday_date = getdate(d.holiday_date)
		if d.holiday_date < yr_start or d.holiday_date > yr_end:
			frappe.msgprint(("""Error in Row# {0} has {1} date as {2} but it is not within 
			FY {3}""").format(d.idx, d.description, d.holiday_date, doc.fiscal_year), raise_exception=1)