# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from time import time
import frappe
from ...utils.process_sheet_utils import make_jc_for_process_sheet


def execute():
    st_time = time()
    pending_psheets = frappe.db.sql("""SELECT name FROM `tabProcess Sheet` WHERE docstatus = 1 
    AND status != 'Completed' AND status != 'Short Closed' AND status != 'Stopped'""", as_dict=1)
    if pending_psheets:
        for ps in pending_psheets:
            psd = frappe.get_doc("Process Sheet", ps.name)
            make_jc_for_process_sheet(psd)
    tot_time = int(time() - st_time)
    print(f"Total Pending Process Sheets {len(pending_psheets)}")
    print(f"Total Time Taken {tot_time} seconds")
