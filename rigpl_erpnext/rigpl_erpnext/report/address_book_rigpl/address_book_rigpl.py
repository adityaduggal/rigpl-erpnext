# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import datetime
import urllib.parse
from rohit_common.utils.contact_utils import get_contact_phones, get_contact_emails


def execute(filters=None):
    conditions, tbl_join, fd_add = get_conditions(filters)
    data = get_entries(filters, conditions, tbl_join, fd_add)
    columns, data = get_columns(filters, data)

    return columns, data


def get_columns(filters, data):
    new_data = []
    if filters.get("type") == "Address":
        col_map = [
            {"fieldname": "name", "label": f"{filters.get('type')} Link", "fieldtype":"Link",
                "options":f"{filters.get('type')}", "width": 100},
            {"fieldname": "address_type", "label": "Address Type", "fieldtype":"", "options":""},
            {"fieldname": "address_title", "label": "Address Title", "fieldtype":"", "options":""},
            {"fieldname": "address_line1", "label": "Address Line1", "fieldtype":"", "options":""},
            {"fieldname": "address_line2", "label": "Address Line2", "fieldtype":"", "options":""},
            {"fieldname": "city", "label": "City", "fieldtype":"", "options":""},
            {"fieldname": "state", "label": "State", "fieldtype":"", "option":""},
            {"fieldname": "country", "label": "Country", "fieldtype":"Link", "options":"Country"},
            {"fieldname": "airport", "label": "Airport", "fieldtype":"", "options":""},
            {"fieldname": "sea_port", "label": "Sea Port", "fieldtype":"", "options":""},
            {"fieldname": "email_id", "label": "Email", "fieldtype":"", "options":""},
            {"fieldname": "phone", "label": "Phone", "fieldtype":"", "option":""},
            {"fieldname": "fax", "label": "Fax", "fieldtype":"", "options":""},
            {"fieldname": "gstin", "label": "GSTIN", "fieldtype":"", "options":""},
            {"fieldname": "gst_status", "label": "GST Status", "fieldtype":"", "options":""},
            {"fieldname": "gst_validation_date", "label": "Validation Date", "fieldtype":"Date",
                "options":"", "width": 80},
            {"fieldname": "global_google_code", "label": "Google Code", "fieldtype":"", "options":""},
            {"fieldname": "disabled", "label": "Disabled", "fieldtype":"Int", "options":"",
                "width": 20},
            {"fieldname": "link_doctype", "label": "Master Type", "fieldtype":"", "options":""},
            {"fieldname": "link_name", "label": "Master Name", "fieldtype":"Dynamic Link",
                "options":"link_doctype"}
        ]
    else:
        col_map = [
            {"fieldname": "name", "label": f"{filters.get('type')} Link", "fieldtype":"Link",
                "options":f"{filters.get('type')}", "width": 100},
            {"fieldname": "salutation", "label": "Salutation", "fieldtype":"", "options":"",
                "width": 30},
            {"fieldname": "first_name", "label": "First Name", "fieldtype":"", "options":""},
            {"fieldname": "middle_name", "label": "Middle Name", "fieldtype":"", "options":""},
            {"fieldname": "last_name", "label": "Last Name", "fieldtype":"", "options":""},
            {"fieldname": "phone", "label": "Phone", "fieldtype":"", "options":""},
            {"fieldname": "email", "label": "Email", "fieldtype":"", "options":""},
            {"fieldname": "designation", "label": "Designation", "fieldtype":"", "option":""},
            {"fieldname": "department", "label": "Department", "fieldtype":"", "option":""},
            {"fieldname": "birthday", "label": "Birthday", "fieldtype":"Date", "options":"",
                "width": 80},
            {"fieldname": "anniversary", "label": "Anniversary", "fieldtype":"Date", "options":"",
                "width":80},
            {"fieldname": "notes", "label": "Notes", "fieldtype":"", "option":""},
            {"fieldname": "link_doctype", "label": "Master Type", "fieldtype":"", "options":""},
            {"fieldname": "link_name", "label": "Master Name", "fieldtype":"Dynamic Link",
                "options":"link_doctype"},
            {"fieldname": "gender", "label": "Gender", "fieldtype":"", "options":""}
        ]
    if filters.get("customer_group"):
        cg_fd = {"fieldname": "customer_group", "label": "Cust Group", "fieldtype":"Link",
                    "options":"Customer Group"}
        col_map.append(cg_fd.copy())
    if filters.get("territory"):
        terr_fd = {"fieldname": "territory", "label": "Territory", "fieldtype":"Link",
                    "options":"Territory"}
        col_map.append(terr_fd.copy())
    drop_cols = []
    col_size = []
    cols = frappe._dict({})
    for key in data[0].keys():
        mlen = 0
        for d in data:
            if d.get(key):
                if isinstance(d.get(key), (datetime.date, int, float)):
                    ex_len = 4
                else:
                    ex_len = len(d.get(key))
            else:
                ex_len = 0
            if ex_len > mlen:
                mlen = ex_len
        cols["fieldname"] = key
        cols["width"] = mlen
        col_size.append(cols.copy())
        if mlen == 0:
            drop_cols.append(key)
    for d in col_map:
        for e in col_size:
            if d["fieldname"] == e["fieldname"]:
                if d.get("width", 0) == 0:
                    d["width"] = min(e["width"] * 10, 200)
    for col in col_map:
        if col.get("width") == 0:
            col_map.remove(col)
    for row in data:
        drow = []
        for fd in col_map:
            drow.append(row.get(fd.get("fieldname")))
        new_data.append(drow)

    return col_map, new_data


def get_entries(filters, conditions, tbl_join, fd_add):
    data = []
    if filters.get("type") == "Address":
        if filters.get("orphaned") != 1:
            query = f"""SELECT ad.name, ad.address_title, ad.address_type, ad.address_line1,
            ad.address_line2, ad.city, ad.state, ad.country, ad.pincode, ad.sea_port, ad.airport,
            ad.email_id, ad.phone, ad.fax, ad.gstin, ad.disabled, dl.link_doctype, dl.link_name,
            ad.global_google_code, ad.gst_status, ad.gst_validation_date, ad.latitude, ad.longitude
            {fd_add}
            FROM `tabAddress` ad, `tabDynamic Link` dl {tbl_join}
            WHERE dl.parenttype = 'Address' AND dl.parent = ad.name {conditions}
            ORDER BY dl.link_doctype, dl.link_name, ad.name"""
        else:
            query = f"""SELECT ad.name, ad.address_title, ad.address_type, ad.address_line1,
            ad.address_line2, ad.city, ad.state, ad.country, ad.pincode, ad.sea_port, ad.airport,
            ad.email_id, ad.phone, ad.fax, ad.gstin, ad.disabled, ad.global_google_code,
            ad.gst_status, ad.gst_validation_date
            FROM `tabAddress` ad
            WHERE ad.name NOT IN (SELECT parent FROM `tabDynamic Link` WHERE parenttype = 'Address'
                GROUP BY parent)
            ORDER BY ad.name"""
    else:
        if filters.get("orphaned") != 1:
            query = f"""SELECT con.name,
            IF(TRIM(con.salutation)="" or TRIM(con.salutation) IS NULL , 'zNo Salutation',
            con.salutation) as salutation,
            IF(TRIM(con.first_name)="" or TRIM(con.first_name) IS NULL , 'zNo First Name',
            con.first_name) as first_name,
            IF(TRIM(con.middle_name)="" or TRIM(con.middle_name) IS NULL , 'zNo Middle Name',
            con.middle_name) as middle_name,
            IF(TRIM(con.last_name)="" or TRIM(con.last_name) IS NULL , 'zNo Last Name',
            con.last_name) as last_name,
            IF(TRIM(con.gender)="" or TRIM(con.gender) IS NULL , 'zNo Gender',
            con.gender) as gender,
            con.birthday, con.anniversary, con.designation, con.department, con.notes,
            dl.link_doctype, dl.link_name {fd_add}
            FROM `tabContact` con, `tabDynamic Link` dl {tbl_join}
            WHERE dl.parenttype = 'Contact' AND dl.parent = con.name {conditions}
            ORDER BY dl.link_doctype, dl.link_name, con.name"""
        else:
            query = f"""SELECT con.name,
            IF(TRIM(con.salutation)="" or TRIM(con.salutation) IS NULL , 'zNo Salutation',
            con.salutation) as salutation,
            IF(TRIM(con.first_name)="" or TRIM(con.first_name) IS NULL , 'zNo First Name',
            con.first_name) as first_name,
            IF(TRIM(con.middle_name)="" or TRIM(con.middle_name) IS NULL , 'zNo Middle Name',
            con.middle_name) as middle_name,
            IF(TRIM(con.last_name)="" or TRIM(con.last_name) IS NULL , 'zNo Last Name',
            con.last_name) as last_name,
            IF(TRIM(con.gender)="" or TRIM(con.gender) IS NULL , 'zNo Gender',
            con.gender) as gender,
            con.birthday, con.anniversary, con.designation, con.department, con.notes
            FROM `tabContact` con
            WHERE con.name NOT IN (SELECT parent FROM `tabDynamic Link` WHERE parenttype = 'Contact'
            GROUP BY parent)
            ORDER BY con.name"""
    data = frappe.db.sql(query, as_dict=1)
    if filters.get("type") == "Contact":
        for row in data:
            phone_nos = get_contact_phones(row.name)
            emails = get_contact_emails(row.name)
            row["phone"] = phone_nos
            row["email"] = emails
    return data


def get_conditions(filters):
    cond = ""
    tbl_join = ""
    fd_add = ""
    if filters.get("link_type"):
        cond += f" AND dl.link_doctype = '{filters.get('link_type')}'"

    if filters.get("linked_to"):
        cond += f" AND dl.link_name = '{filters.get('linked_to')}'"

    if filters.get("territory"):
        fd_add += ", cu.territory"
        if tbl_join == "":
            tbl_join += """ LEFT JOIN `tabCustomer` cu ON dl.link_doctype = 'Customer'
                AND dl.link_name = cu.name"""
        terr = frappe.get_doc("Territory", filters["territory"])
        if terr.is_group == 1:
            child_territories = frappe.db.sql(f"""SELECT name FROM `tabTerritory`
                WHERE lft >= {terr.lft} AND rgt <= {terr.rgt}""", as_list=1)
            for i in child_territories:
                if child_territories[0] == i:
                    cond += " AND (cu.territory = '%s'" % i[0]
                elif child_territories[len(child_territories) - 1] == i:
                    cond += " OR cu.territory = '%s')" % i[0]
                else:
                    cond += " OR cu.territory = '%s'" % i[0]
        else:
            cond += " AND cu.territory = '%s'" % filters["territory"]

    if filters.get("customer_group"):
        fd_add += ", cu.customer_group"
        if tbl_join == "":
            tbl_join += """ LEFT JOIN `tabCustomer` cu ON dl.link_doctype = 'Customer'
                AND dl.link_name = cu.name"""
        cg = frappe.get_doc("Customer Group", filters["customer_group"])
        if cg.is_group == 1:
            child_cgs = frappe.db.sql(f"""SELECT name FROM `tabCustomer Group`
                WHERE lft >= {cg.lft} AND rgt <= {cg.rgt}""", as_list=1)
            for i in child_cgs:
                if child_cgs[0] == i:
                    cond += " AND (cu.customer_group = '%s'" % i[0]
                elif child_cgs[len(child_cgs) - 1] == i:
                    cond += " OR cu.customer_group = '%s')" % i[0]
                else:
                    cond += " OR cu.customer_group = '%s'" % i[0]
        else:
            cond += " AND cu.customer_group = '%s'" % filters["customer_group"]
    return cond, tbl_join, fd_add
