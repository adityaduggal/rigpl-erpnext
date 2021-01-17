# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import re
import frappe
import time
from rohit_common.rohit_common.validations.file import delete_file_dt


def execute():
    image_extensions = ["jpg", "jpeg", "png"]
    st_time = time.time()
    items = frappe.db.sql("""SELECT name, variant_of, has_variants FROM `tabItem` WHERE docstatus=0 
    ORDER BY name""", as_dict=1)
    sno = 0
    deleted = 0
    committed = 0
    for d in items:
        sno += 1
        print(f"{sno}. Checking Item Code {d.name}")
        itd = frappe.get_doc("Item", d.name)
        attachments = frappe.db.sql("""SELECT name, file_name, file_url FROM `tabFile` 
        WHERE attached_to_doctype = 'Item' AND attached_to_name = '%s' """ % d.name, as_dict=1)
        print(f"Total No of Files Attached to {d.name} = {len(attachments)}")
        for file in attachments:
            if file.file_url == itd.image:
                another_file = frappe.db.sql("""SELECT name FROM `tabFile` WHERE file_url = '%s' 
                AND attached_to_doctype = 'Item' AND attached_to_name = '%s' AND name != '%s'""" %
                                             (file.file_url, d.name, file.name), as_dict=1)
                if another_file:
                    for ext_file in another_file:
                        deleted += 1
                        fd = frappe.get_doc("File", ext_file.name)
                        delete_file_dt(fd)
                        print(f"Deleting {ext_file.name} as its Attached Extra to {d.name}")
            else:
                for ext in image_extensions:
                    if re.search(ext, file.file_url, re.IGNORECASE):
                        deleted += 1
                        fd = frappe.get_doc("File", file.name)
                        delete_file_dt(fd)
        if deleted - committed >= 100 and deleted > 0:
            frappe.db.commit()
            committed = deleted
            print(f"Committing Changes after {deleted} Changes. Time Elapsed {int(time.time() - st_time)} seconds")
            time.sleep(1)
    tot_time = int(time.time() - st_time)
    print(f"Total Files Deleted = {deleted} nos")
    print(f"Total Time Taken = {tot_time} seconds")

