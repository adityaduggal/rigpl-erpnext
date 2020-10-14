# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import getdate

def execute():
    ctrack_dict = frappe.db.sql("""SELECT name, carrier_name FROM `tabCarrier Tracking` WHERE docstatus = 1
        AND status = 'Delivered' AND pickup_date IS NULL ORDER BY creation""", as_dict=1)
    count = 0
    for ct in ctrack_dict:
        count += 1
        commit_changes(count)
        ct_doc = frappe.get_doc("Carrier Tracking", ct.name)
        if ct_doc.document != 'Sales Invoice':
            if ct_doc.creation > ct_doc.delivery_date_time:
                print('Error Creation is After Delivery for ' + ct.name)
                exit()
            else:
                pick_date = (ct_doc.creation).date()
                update_pickup_date(ct_doc, pick_date, ct)
        else:
            sid = frappe.get_doc("Sales Invoice", ct_doc.document_name)
            if sid.creation > ct_doc.delivery_date_time:
                if sid.amended_from:
                    sid_orig = frappe.get_doc("Sales Invoice", sid.amended_from)
                    if sid_orig.creation > ct_doc.delivery_date_time:
                        print("Error Creation after Delivery " + ct.name)
                        exit()
                else:
                    pick_date = (sid_orig.creation).date()
                    update_pickup_date(ct_doc, pick_date, ct, amended="Yes")
            else:
                pick_date = (sid.creation).date()
                update_pickup_date(ct_doc, pick_date, ct)


def update_pickup_date(ct_doc, pick_date, ct_dict, amended="No"):
    ct_doc.pickup_date = pick_date
    ct_doc.save()
    # frappe.db.commit()
    if amended == 'No':
        print("Updating " + ct_dict.name)
    else:
        print("Updating from Amended Document for " + ct_dict.name)


def commit_changes(count):
    if count%1000 == 0:
        print('Committing Changes as Count = ' + str(count))
        frappe.db.commit()
