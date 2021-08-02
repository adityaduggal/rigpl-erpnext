# -*- coding: utf-8 -*-
# Copyright (c) 2021, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time


def execute():
    st_time = time.time()
    tot_records = 0
    keydict = [
        {"keyword": "HSS", "cc": "HSS Tools - RIGPL"}, {"keyword": "Carbide", "cc": "Carbide Tools - RIGPL"},
        {"keyword": "Diamond", "cc": "Carbide Tools - RIGPL"}, {"keyword": "RH%RM", "cc": "HSS Tools - RIGPL"},
        {"keyword": "RC%RM", "cc": "Carbide Tools - RIGPL"}, {"keyword": "RT%RM", "cc": "HSS Tools - RIGPL"},
        {"keyword": "Alumin", "cc": "HSS Tools - RIGPL"}, {"keyword": "RE%RM", "cc": "HSS Tools - RIGPL"}
    ]
    for key in keydict:
        # print(key.get("keyword"))
        search_key = "%" + key.get("keyword") + "%"
        query = """SELECT it.name as it_name, itd.name FROM `tabItem` it, `tabItem Default` itd
        WHERE itd.parent = it.name AND it.has_variants=1 AND itd.buying_cost_center IS NULL
        AND it.name LIKE '%s' """ % search_key
        # print(query)
        templates = frappe.db.sql(query, as_dict=1)
        if templates:
            for tp in templates:
                tot_records += 1
                frappe.db.set_value("Item Default", tp.name, "buying_cost_center", key.get("cc"))
                frappe.db.set_value("Item Default", tp.name, "selling_cost_center", key.get("cc"))
    print(f"Total Time Taken = {int(time.time() - st_time)} seconds. \nTotal Records Updated = {tot_records}")
