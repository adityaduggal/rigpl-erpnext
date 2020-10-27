# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import time
import frappe
from ...utils.job_card_utils import check_existing_job_card


def execute():
    draft_jc = frappe.db.sql("""SELECT name, production_item, sales_order_item, operation
    FROM `tabProcess Job Card RIGPL` WHERE docstatus=0 ORDER BY name""", as_dict=1)
    delete_jc = 0
    for jc in draft_jc:
        print("Processing Job Card # {} for Item Code {}".format(jc.name, jc.production_item))
        existing_jc = check_existing_job_card(item_name=jc.production_item, so_detail=jc.sales_order_item,
                                              operation=jc.operation)
        if existing_jc:
            for oth_jc in existing_jc:
                if oth_jc.name != jc.name:
                    delete_jc += 1
                    frappe.delete_doc("Process Job Card RIGPL", oth_jc.name)
                    print("Deleted Job Card = {}".format(oth_jc.name))
                    removed_jc = next(jc for jc in draft_jc if jc["name"] == oth_jc.name)
                    draft_jc.remove(removed_jc)
    print("Total Job Cards to be Deleted = {}".format(delete_jc))
