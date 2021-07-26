# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from rigpl_erpnext.utils.rigpl_perm import *
from rigpl_erpnext.rigpl_erpnext.validations.lead import lead_docshare, lead_quote_share, lead_address_share
from rohit_common.rohit_common.validations.docshare import get_docshare_from_dt, create_docshare
from frappe.utils.background_jobs import enqueue
from time import time


def enqueue_docshare():
    enqueue(execute, queue="long", timeout=1500)


def execute():
    st_time = time()
    inactive_users = get_users(active=0)
    for user in inactive_users:
        delete_docshare(user=user[0])
    frappe.db.commit()
    lead_list = frappe.db.sql("""SELECT name FROM `tabLead`
        ORDER BY creation DESC""", as_dict=1)
    commit_chk = 0
    for lead in lead_list:
        lead_doc = frappe.get_doc("Lead", lead.name)
        lead_docshare(lead_doc)
        lead_quote_share(lead_doc)
        lead_address_share(lead_doc)
        commit_chk += 1
        if commit_chk %100 == 0:
            frappe.db.commit()
    tot_time = int(time() - st_time)
    file_sharing()
    print(f"Total Time Taken {tot_time} seconds")


def files_sharing():
    st_time = time()
    # Share all files without Doctype or DocName with System Managers
    # Also share folders with mentioned in Settings
    enb_users = frappe.db.get_values("User", filters={"enabled": 1}, as_dict=1)
    share_roles = frappe.db.get_values("User Share Rules", filters={"parent": "User Share Settings", "document_type": "File"},
        fieldname=["name", "role", "document_type", "document_name", "read_access", "write_access", "share_access"], as_dict=1)
    for usr in enb_users:
        if usr.name != "Administrator":
            usr_roles = frappe.get_roles(usr.name)
            if "System Manager" in usr_roles:
                # Add all files without DT or DN and not owned by System Manager to Sharing
                not_owner = "!= %s" % usr.name
                files_without_dt_non_owners = frappe.db.sql("""SELECT name, is_folder, lft, rgt FROM `tabFile`
                    WHERE (attached_to_doctype IS NULL OR attached_to_name IS NULL) AND is_private = 1 AND is_folder = 0
                    AND owner != '%s' """ %usr.name, as_dict=1)
                if files_without_dt_non_owners:
                    for fd in files_without_dt_non_owners:
                        fdd = frappe.get_doc("File", fd.name)
                        create_docshare(dt=fdd.doctype, dn=fdd.name, user=usr.name, read=1, write=1, share=1)
                print(f"For User: {usr.name} there are {len(files_without_dt_non_owners)} Files to be Checked for DocShare")
            else:
                for rl in share_roles:
                    if rl.role in usr_roles:
                        print(f"Checking for User {usr.name}")
                        file_dt = frappe.get_value("File", rl.document_name, fieldname=["is_folder", "lft", "rgt", "folder", "name"],as_dict=1)
                        if file_dt and file_dt.is_folder == 1:
                            doc_childs = frappe.db.sql("""SELECT name, is_folder, lft, rgt, folder FROM `tabFile`
                                WHERE lft > %s AND rgt < %s""" % (file_dt.lft, file_dt.rgt), as_dict=1)
                            if doc_childs:
                                for chd in doc_childs:
                                    create_docshare(user=usr.name, dt=rl.document_type, dn=rl.document_name, read=rl.read_access,
                                        write=rl.write_access, share=rl.share_access, ev_one=rl.ev_one, change_exist=0)
    print(f"Total Time Taken for Files DocSharing = {int(time() - st_time)} seconds")
