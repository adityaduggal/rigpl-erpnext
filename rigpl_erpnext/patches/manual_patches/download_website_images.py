# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import time
import frappe
import requests
import os
import shutil
import urllib.request
from os import path
from frappe.utils import get_site_base_path, get_files_path
from six.moves.urllib.parse import quote


def execute():
    st_time = time.time()
    base_path = get_files_path()
    frm_web = input("Enter the Full Website Address: ")
    # Download all images related to website into public folder for local server
    # Images would be from Website Slide Show, Item Master and Item Group and Website Settings
    attached_to_single_dt = ["Website Slideshow", "Website Settings", "Web Page", "Blog Post",
        "About Us Settings", "Letter Head"]
    multi_dt = ["Item Group", "Item"]

    for dt in attached_to_single_dt:
        print(f"Checking Files Attached to Single Doctye = {dt}")
        ss_files = frappe.db.sql(f"""SELECT file_url, file_name FROM `tabFile`
            WHERE attached_to_doctype = '{dt}' AND is_private = 0""", as_dict=1)
        for ff in ss_files:
            web_add = frm_web + quote(ff.file_url)
            local_path = base_path + '/' + ff.file_name
            if not os.path.exists(local_path):
                print(f"Downloaded {ff.file_name}")
                download_file(url=web_add, file_path=local_path)
    for dt in multi_dt:
        print(f"Checking Files Attached to Multi Doctye = {dt}")
        if dt == "Item Group":
            ss_files = frappe.db.sql(f"""SELECT fd.file_url, fd.file_name
                FROM `tabFile` fd, `tab{dt}` it
                WHERE fd.attached_to_doctype = '{dt}' AND fd.attached_to_name = it.name
                AND it.show_in_website = 1
                AND fd.is_private = 0""", as_dict=1)
        elif dt == "Item":
            ss_files = frappe.db.sql(f"""SELECT fd.file_url, fd.file_name
                FROM `tabFile` fd, `tab{dt}` it
                WHERE fd.attached_to_doctype = '{dt}' AND fd.attached_to_name = it.name
                AND (it.show_in_website = 1 OR it.show_variant_in_website = 1)
                AND fd.is_private = 0 """, as_dict=1)
        else:
            ss_files = frappe.db.sql(f"""SELECT fd.file_url, fd.file_name
                FROM `tabFile` fd
                WHERE fd.attached_to_doctype = '{dt}' AND fd.is_private = 0 """, as_dict=1)
        for ff in ss_files:
            web_add = frm_web + quote(ff.file_url)
            local_path = base_path + '/' + ff.file_name
            if not os.path.exists(local_path):
                print(f"Downloaded {ff.file_name}")
                download_file(url=web_add, file_path=local_path)
    print(f"Total Time Taken = {int(time.time() - st_time)} seconds")


def download_file(url, file_path):
    urllib.request.urlretrieve(url, file_path)
