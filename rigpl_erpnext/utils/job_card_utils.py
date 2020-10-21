# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import nowdate
from erpnext.stock.utils import get_bin
from .manufacturing_utils import get_items_from_process_sheet_for_job_card


def create_job_card(pro_sheet, row, quantity=0, enable_capacity_planning=False, auto_create=False):
    doc = frappe.new_doc("Process Job Card RIGPL")
    doc.update({
        'production_item': pro_sheet.production_item,
        'description': pro_sheet.description,
        'process_sheet': pro_sheet.name,
        'operation': row.get("operation"),
        'workstation': row.get("workstation"),
        'posting_date': nowdate(),
        'sales_order': pro_sheet.sales_order,
        'sales_order_item': pro_sheet.sales_order_item,
        'sno': pro_sheet.sno,
        's_warehouse': row.get('source_warehouse'),
        't_warehouse': row.get('target_warehouse'),
        'allow_consumption_of_rm': row.allow_consumption_of_rm,
        'allow_production_of_wip_materials': row.allow_production_of_wip_materials,
        'for_quantity': quantity or (pro_sheet.get('quantity', 0) - pro_sheet.get('produced_qty', 0)),
        'operation_id': row.get("name")
    })

    if auto_create:
        doc.flags.ignore_mandatory = True
        if enable_capacity_planning:
            doc.schedule_time_logs(row)
        get_items_from_process_sheet_for_job_card(doc, "rm_consumed")
        get_items_from_process_sheet_for_job_card(doc, "item_manufactured")
        doc.insert()
        frappe.msgprint(_("Job card {0} created").format(frappe.get_desk_link("Process Job Card RIGPL", doc.name)))

    return doc


def update_job_card_status(jc_doc):
    # Old Name = update_jc_status
    if jc_doc.docstatus == 2:
        jc_doc.status = 'Cancelled'
    elif jc_doc.docstatus == 1:
        jc_doc.status = 'Completed'
    elif jc_doc.docstatus == 0:
        # There are 2 options for Draft Job Cards 1 is Open and Other is Work In Progress
        # WIP JC can be worked on and only possible if its 1st process in Process Sheet or if not then previous
        # process should be complete or there should be stock for that item in the Source Warehouse
        # Also if the Process Sheet is for Special Item then the JC can only be in WIP once previous process
        # is complete.
        op_doc = frappe.get_doc("BOM Operation", jc_doc.operation_id)
        if op_doc.idx == 1:
            jc_doc.status = "Work In Progress"
        else:
            pro_doc = frappe.get_doc('Process Sheet', jc_doc.process_sheet)
            if pro_doc.sales_order_item:
                for prev_op in pro_doc.operations:
                    if prev_op.idx == op_doc.idx - 1:
                        prev_op_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE 
                        operation_id = '%s' AND docstatus != 2""" % prev_op.name, as_dict=1)
                        if prev_op_jc:
                            prev_op_jc_doc = frappe.get_doc("Process Job Card RIGPL", prev_op_jc[0].name)
                            if prev_op_jc_doc.status == "Completed":
                                jc_doc.status = 'Work In Progress'
                            else:
                                jc_doc.status = 'Open'
                        else:
                            frappe.throw("For Item: {} in JC# {} there is no Reference for Previous "
                                         "Process".foramt(jc_doc.production_item, jc_doc.name))
            else:
                # Now the JC is for Items with Attributes or Stock Items. They can be WIP if there is stock in
                # Source Warehouse
                qty_available = get_bin(jc_doc.production_item, jc_doc.s_warehouse).get("actual_qty")
                if qty_available > 0:
                    jc_doc.status = 'Work In Progress'
                else:
                    jc_doc.status = 'Open'


def check_existing_pending_job_card(pro_sheet_name, pro_sheet_row_id):
    exist_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus=0 AND 
    process_sheet = '%s' AND operation_id = '%s'""" % (pro_sheet_name, pro_sheet_row_id), as_dict=1)
    return exist_jc


@frappe.whitelist()
def make_jc_from_pro_sheet_row(pro_sheet_name, pro_sheet_row_id):
    ps_doc = frappe.get_doc("Process Sheet", pro_sheet_name)
    for row in ps_doc.operations:
        if row.name == pro_sheet_row_id:
            existing_pending_job_card = check_existing_pending_job_card(pro_sheet_name, pro_sheet_row_id)
            if existing_pending_job_card:
                frappe.throw("Job Card# {} is already pending for Process Sheet {} in Row# {} and Operation {}".
                             format(frappe.get_desk_link("Process Job Card RIGPL", existing_pending_job_card[0].name),
                                    pro_sheet_name, row.idx, row.operation))
            else:
                create_job_card(ps_doc, row, quantity=(row.planned_qty - row.completed_qty), auto_create=True)
            break
