# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time


def execute():
    st_time = time.time()
    s_per = frappe.db.sql("""SELECT name FROM `tabSales Person` WHERE is_group=0""", as_dict=1)
    for sp in s_per:
        sp_doc = frappe.get_doc("Sales Person", sp.name)
        email_id = frappe.get_value("Employee", sp_doc.employee, "user_id")
        frappe.db.set_value("Sales Person", sp.name, "email_id", email_id)
    frappe.db.commit()
    print("Updated All Sales Persons")
    s_team = frappe.db.sql("""SELECT name, sales_person FROM `tabSales Team`""", as_dict=1)
    for st in s_team:
        email_id = frappe.get_value("Sales Person", st.sales_person, "email_id")
        frappe.db.set_value("Sales Team", st.name, "email_id", email_id)
    print("Updated All Sales Team Table with Email ID")
    tot_time = int(time.time() - st_time)
    print(f"Total Time Take {tot_time} seconds")
