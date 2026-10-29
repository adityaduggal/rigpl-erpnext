# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from rigpl_erpnext.utils.item_attribute_utils import chunks
from rigpl_erpnext.utils.lead_share_utils import sync_lead_shares
from rohit_common.rohit_common.validations.docshare import create_docshare, get_file_tree
from time import time


def execute():
    st_time = time()
    delete_disabled_user_shares()
    to_add, to_remove = sync_lead_shares()
    print(f"Lead DocShares: {len(to_add)} added, {len(to_remove)} removed in {int(time() - st_time)} seconds")
    sync_folder_shares()
    print(f"Total Time Taken for all processes = {int(time() - st_time)} seconds")


def delete_disabled_user_shares():
    docshare = frappe.qb.DocType("DocShare")
    for chunk in chunks(frappe.get_all("User", filters={"enabled": 0}, pluck="name")):
        frappe.qb.from_(docshare).delete().where(docshare.user.isin(chunk)).run()


def sync_folder_shares():
    """
    Shares the folders of the File rules with the users of the role, and shares each file in a
    shared folder that is not shared yet. The DocShare hook shares a folder's files only when
    the folder share is made, so files added later were never shared (#151).
    """
    rules = frappe.get_all("User Share Rules", filters={"parent": "User Share Settings", "document_type": "File"},
                           fields=["role", "document_name", "read_access", "write_access", "share_access"])
    existing = set(frappe.db.sql("""SELECT user, share_name FROM `tabDocShare`
        WHERE share_doctype = 'File' AND user IS NOT NULL"""))
    if rules:
        users_by_role = {}
        for user, role in frappe.db.sql("""SELECT hr.parent, hr.role FROM `tabHas Role` hr
                JOIN `tabUser` u ON u.name = hr.parent WHERE hr.parenttype = 'User' AND u.enabled = 1
                AND hr.role IN %(roles)s""", {"roles": tuple(rule.role for rule in rules)}):
            users_by_role.setdefault(role, []).append(user)
        for rule in rules:
            for user in users_by_role.get(rule.role, []):
                if rule.document_name and (user, rule.document_name) not in existing:
                    create_docshare(user=user, dt="File", dn=rule.document_name, read=rule.read_access,
                                    write=rule.write_access, share=rule.share_access)
        existing = set(frappe.db.sql("""SELECT user, share_name FROM `tabDocShare`
            WHERE share_doctype = 'File' AND user IS NOT NULL"""))

    folder_shares = frappe.db.sql("""SELECT d.user, d.share_name, d.read, d.write, d.share
        FROM `tabDocShare` d JOIN `tabFile` f ON f.name = d.share_name
        WHERE d.share_doctype = 'File' AND f.is_folder = 1 AND d.user IS NOT NULL""", as_dict=1)
    added = 0
    for folder in folder_shares:
        for child in get_file_tree("File", folder.share_name):
            if (folder.user, child.name) not in existing:
                create_docshare(user=folder.user, dt="File", dn=child.name, read=folder.read, write=folder.write,
                                share=folder.share, from_tree=1)
                existing.add((folder.user, child.name))
                added += 1
    print(f"File DocShares: {added} files in shared folders shared")
