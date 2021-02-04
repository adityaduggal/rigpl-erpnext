# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import getdate


def validate(doc, method):
    yr_start = getdate(doc.from_date)
    yr_end = getdate(doc.to_date)
    if doc.is_base_list == 1:
        doc.base_holiday_list = ""
    else:
        holiday_list_based_on = frappe.db.sql("""SELECT name FROM `tabHoliday List` 
        WHERE base_holiday_list = '%s'""" % doc.name, as_dict=1)
        if holiday_list_based_on:
            frappe.throw("Holiday List {} already is Base List for {} and hence Cannot be made "
                         "non-base Holiday List".format(doc.name, holiday_list_based_on[0].name))
        if doc.base_holiday_list == "":
            frappe.throw("Base Holiday List Mandatory for {}".format(doc.name))
        else:
            base_holiday = frappe.get_value("Holiday List", doc.base_holiday_list, "is_base_list")
            if base_holiday != 1:
                frappe.throw("Base Holiday List {} Selected is Not a Base "
                             "Holiday List in {}".format(doc.base_holiday_list, doc.name))
    for d in doc.holidays:
        d.holiday_date = getdate(d.holiday_date)
        if d.holiday_date < yr_start or d.holiday_date > yr_end:
            frappe.msgprint(("""Error in Row# {0} has {1} date as {2} but it is not within 
            FY {3}""").format(d.idx, d.description, d.holiday_date, doc.fiscal_year), raise_exception=1)


@frappe.whitelist()
def pull_holidays(hd_name, frm_date, to_date):
    base_hdd = frappe.get_doc("Holiday List", hd_name)
    if base_hdd.is_base_list == 1:
        linked_hld = frappe.db.sql("""SELECT name FROM `tabHoliday List` WHERE is_base_list = 0 
        AND base_holiday_list = '%s' AND from_date = '%s' AND to_date = '%s'""" % (hd_name, frm_date,
                                                                                   to_date), as_dict=1)
        if linked_hld:
            # Copy and paste the holidays from there to here
            lnk_hdd = frappe.get_doc("Holiday List", linked_hld[0].name)
            base_hdd.from_date = lnk_hdd.from_date
            base_hdd.to_date = lnk_hdd.to_date
            base_hdd.weekly_off = lnk_hdd.weekly_off
            base_hdd.holidays = []
            new_hlds = frappe._dict({})
            for d in lnk_hdd.holidays:
                new_hlds["idx"] = d.idx
                new_hlds["holiday_date"] = d.holiday_date
                new_hlds["description"] = d.description
                base_hdd.append("holidays", new_hlds.copy())
            base_hdd.save()
            base_hdd.reload()
        else:
            frappe.throw(f"No Holiday List Linked with {hd_name} for From Date: {frm_date} and To Date: {to_date}")
