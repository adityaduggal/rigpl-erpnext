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
    if inactive_users:
        inactive_user_names = [u[0] for u in inactive_users]
        # Optimized: Single SQL delete instead of individual calls
        frappe.db.sql("DELETE FROM `tabDocShare` WHERE user IN %s", (inactive_user_names,))
    frappe.db.commit()

    lead_list = frappe.db.sql("""SELECT name FROM `tabLead`
        ORDER BY creation DESC""", as_dict=1)
    
    print(f"Checking DocShare for {len(lead_list)} Leads")
    commit_chk = 0
    for lead in lead_list:
        # Use cached doc to avoid repeated DB hits
        lead_doc = frappe.get_cached_doc("Lead", lead.name)
        lead_docshare(lead_doc)
        lead_quote_share(lead_doc)
        lead_address_share(lead_doc)
        commit_chk += 1
        if commit_chk % 200 == 0:
            frappe.db.commit()
    
    frappe.db.commit()
    tot_time = int(time() - st_time)
    print(f"Total Time Taken for Doc Share = {tot_time} seconds")
    files_sharing()
    print(f"Total Time Taken for all processes = {int(time() - st_time)} seconds")


def files_sharing():
    st_time = time()
    # Bulk fetch all user roles to avoid N+1 frappe.get_roles
    all_user_roles = frappe.get_all("Has Role", fields=["parent", "role"], filters={"parenttype": "User"})
    user_role_map = {}
    for r in all_user_roles:
        user_role_map.setdefault(r.parent, []).append(r.role)

    enb_users = frappe.get_all("User", filters={"enabled": 1}, fields=["name"])
    
    share_rules = frappe.get_all("User Share Rules", 
        filters={"parent": "User Share Settings", "document_type": "File"},
        fields=["name", "role", "document_type", "document_name", "read_access", "write_access", "share_access"])

    # Bulk fetch existing File DocShares to avoid redundant inserts
    existing_shares = frappe.get_all("DocShare", filters={"share_doctype": "File"}, fields=["user", "share_name"])
    existing_share_map = set([(s.user, s.share_name) for s in existing_shares])

    for usr in enb_users:
        if usr.name == "Administrator":
            continue
            
        usr_roles = user_role_map.get(usr.name, [])
        if "System Manager" in usr_roles:
            # Add all files without DT or DN and not owned by System Manager to Sharing
            files_to_share = frappe.db.sql("""SELECT name FROM `tabFile`
                WHERE (attached_to_doctype IS NULL OR attached_to_name IS NULL) 
                AND is_private = 1 AND is_folder = 0
                AND owner != %s""", usr.name, as_dict=1)
            
            if files_to_share:
                print(f"Processing {len(files_to_share)} orphan files for System Manager: {usr.name}")
                for fd in files_to_share:
                    if (usr.name, fd.name) not in existing_share_map:
                        try:
                            create_docshare(dt="File", dn=fd.name, user=usr.name, read=1, write=1, share=1)
                        except Exception:
                            # Skip if rohit_common throws "NO SHARE NEEDED"
                            pass
        else:
            for rl in share_rules:
                if rl.role in usr_roles:
                    # Optimized: Fetching folder info already done in SQL
                    file_info = frappe.db.get_value("File", rl.document_name, 
                        fieldname=["is_folder", "lft", "rgt", "name"], as_dict=1)
                    
                    if file_info and file_info.is_folder == 1:
                        doc_childs = frappe.db.sql("""SELECT name FROM `tabFile`
                            WHERE lft > %s AND rgt < %s""", (file_info.lft, file_info.rgt), as_dict=1)
                        
                        if doc_childs:
                            for chd in doc_childs:
                                if (usr.name, chd.name) not in existing_share_map:
                                    try:
                                        create_docshare(user=usr.name, dt="File", dn=chd.name, 
                                            read=rl.read_access, write=rl.write_access, share=rl.share_access, 
                                            change_exist=0)
                                    except Exception:
                                        pass
    
    frappe.db.commit()
    print(f"Total Time Taken for Files DocSharing = {int(time() - st_time)} seconds")
