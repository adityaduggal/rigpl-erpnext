# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import time


def execute():
    pr_list = frappe.db.sql("""SELECT name, modified FROM `tabPricing Rule` ORDER BY modified""", as_dict=1)
    error_pr = []
    processed = 0
    for pr in pr_list:
        print(f"Processing {pr.name} Last Modified {pr.modified}")
        prd = frappe.get_doc("Pricing Rule", pr.name)
        try:
            processed += 1
            prd.save()
        except:
            error_pr.append(pr.name)
        if processed%100 == 0 and processed > 0:
            frappe.db.commit()
            print(f"Committing Changes after {processed} updates")
            time.sleep(0.5)
    print(f"Error Pricing Rules = {error_pr}")
    print(f"Total Pricing Rules Saved = {processed}")
