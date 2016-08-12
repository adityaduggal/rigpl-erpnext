# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from frappe.utils import getdate, get_last_day, today, flt, cint, add_months
from rigpl_erpnext.rigpl_erpnext.item import fn_next_string, fn_check_digit

def validate(doc, method):
	ass_cat = frappe.get_doc("Asset Category", doc.asset_category)
	doc.expected_value_after_useful_life = round((ass_cat.residual_value_percent * doc.gross_purchase_amount)/100,2)
	doc.total_number_of_depreciations = ass_cat.total_number_of_depreciations
	doc.frequency_of_depreciation = ass_cat.frequency_of_depreciation
	doc.depreciation_method = ass_cat.depreciation_method
	doc.next_depreciation_date = get_last_day(today())
	make_dep_schedule(doc,method)
	
def autoname(doc, method):
	if doc.autoname == 1:
		ass_cat = frappe.get_doc("Asset Category", doc.asset_category)
		fa = frappe.db.sql("""SELECT name FROM `tabItem Attribute Value` WHERE parent = 'Tool Type' AND 
			attribute_value = 'Fixed Asset'""", as_list = 1)
		att = frappe.get_doc("Item Attribute Value", fa[0][0])
		purchase = getdate(doc.purchase_date)
		#name = YearMonth-AssetCategorySmall-SerialCheckDigit
		#Don't use - in the actual name for check digit
		name = str(purchase.year) + str('{:02d}'.format(purchase.month)) + \
			ass_cat.asset_short_name + str(att.serial)
		next_serial = fn_next_string(doc, str(att.serial))
		cd = fn_check_digit(doc, name)
		name = name + str(cd)
		doc.name = name
		frappe.db.set_value("Item Attribute Value", fa[0][0], "serial", next_serial)
	doc.asset_name = doc.name
	
def make_dep_schedule(doc,method):
	doc.schedules = []
	if not doc.get("schedules") and doc.next_depreciation_date:
		accumulated_depreciation = flt(doc.opening_accumulated_depreciation)
		value_after_depreciation = flt(doc.value_after_depreciation)
		
		number_of_pending_depreciations = cint(doc.total_number_of_depreciations) - \
			cint(doc.number_of_depreciations_booked)
		if number_of_pending_depreciations:
			for n in xrange(number_of_pending_depreciations):
				schedule_date = add_months(doc.next_depreciation_date,
					n * cint(doc.frequency_of_depreciation))

				depreciation_amount = doc.get_depreciation_amount(value_after_depreciation)
			
				accumulated_depreciation += flt(depreciation_amount)
				value_after_depreciation -= flt(depreciation_amount)

				doc.append("schedules", {
					"schedule_date": schedule_date,
					"depreciation_amount": depreciation_amount,
					"accumulated_depreciation_amount": accumulated_depreciation
				})
