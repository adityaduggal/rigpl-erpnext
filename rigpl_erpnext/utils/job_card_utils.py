# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import nowdate, flt
from erpnext.stock.utils import get_bin
from .manufacturing_utils import get_items_from_process_sheet_for_job_card, convert_qty_per_uom


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


def check_existing_job_card(item_name, operation):
    exist_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus !=2 AND operation_id = 
    '%s' AND production_item = '%s' """ % (operation, item_name), as_dict=1)
    return exist_jc


def check_qty_job_card(row, calculated_qty, qty, uom, bypass=0):
    uom_doc = frappe.get_doc('UOM', uom)
    error_title = "Error for Raw Material Quantity Entered"
    warning_title = "Warning for Raw Material Quantity Entered"
    if uom_doc.variance_allowed > 0:
        variance = uom_doc.variance_allowed / 100
        upper_limit = (1+variance)*flt(calculated_qty)
        lower_limit = (1-variance)*flt(calculated_qty)
        if flt(qty) > upper_limit or flt(qty) < lower_limit:
            message = "Entered Quantity {} in Row# {} for {} is Not in Range and must be between {} and {}".\
                format(row.qty, row.idx, row.parent, lower_limit, upper_limit)
            if bypass == 0:
                frappe.throw(message, title=error_title)
            else:
                frappe.msgprint(message, title=warning_title)
    else:
        calculated_qty = convert_qty_per_uom(calculated_qty, row.item_code)
        if flt(qty) != calculated_qty:
            message = "Entered Quantity = {} is Not Equal to the Calculated Qty = {} for RM Size = {} in Row# {}".\
                format(row.qty, row.calculated_qty, row.item_code, row.idx)
            if bypass == 0:
                frappe.throw(message, title=error_title)
            else:
                frappe.msgprint(message, title=warning_title)


def create_submit_ste_from_job_card(jc_doc):
    if jc_doc.no_stock_entry != 1:
        remarks = 'STE for Process Job Card # {}'.format(jc_doc.name)
        item_table = []
        it_dict = {}
        it_dict.setdefault("item_code", jc_doc.production_item)
        it_dict.setdefault("allow_zero_valuation_rate", 1)
        it_dict.setdefault("s_warehouse", jc_doc.s_warehouse)
        it_dict.setdefault("t_warehouse", jc_doc.t_warehouse)
        it_dict.setdefault("qty", jc_doc.total_completed_qty)
        item_table.append(it_dict.copy())
        for d in jc_doc.time_logs:
            if d.rejected_qty > 0 and jc_doc.s_warehouse:
                it_dict = {}
                it_dict.setdefault("item_code", jc_doc.production_item)
                it_dict.setdefault("allow_zero_valuation_rate", 1)
                it_dict.setdefault("qty", d.salvage_qty)
                it_dict.setdefault("s_warehouse", jc_doc.s_warehouse)
                it_dict.setdefault("t_warehouse", "")
                item_table.append(it_dict.copy())
            if d.salvage_qty > 0:
                it_dict = {}
                it_dict.setdefault("item_code", jc_doc.production_item)
                it_dict.setdefault("allow_zero_valuation_rate", 1)
                it_dict.setdefault("qty", d.salvage_qty)
                if jc_doc.s_warehouse:
                    it_dict.setdefault("s_warehouse", jc_doc.s_warehouse)
                it_dict.setdefault("t_warehouse", d.salvage_warehouse)
                item_table.append(it_dict.copy())
        if jc_doc.rm_consumed:
            for row in jc_doc.rm_consumed:
                if row.qty > 0:
                    it_dict = {}
                    it_dict.setdefault("item_code", row.item_code)
                    it_dict.setdefault("allow_zero_valuation_rate", 1)
                    it_dict.setdefault("qty", row.qty)
                    it_dict.setdefault("s_warehouse", row.source_warehouse)
                    it_dict.setdefault("t_warehouse", row.target_warehouse)
                    item_table.append(it_dict.copy())
        if jc_doc.item_manufactured:
            for row in jc_doc.item_manufactured:
                if row.qty > 0:
                    it_dict = {}
                    it_dict.setdefault("item_code", row.item_code)
                    it_dict.setdefault("allow_zero_valuation_rate", 1)
                    it_dict.setdefault("qty", row.qty)
                    it_dict.setdefault("s_warehouse", row.source_warehouse)
                    it_dict.setdefault("t_warehouse", row.target_warehouse)
                    item_table.append(it_dict.copy())
        ste_type = 'Repack'
        ste = frappe.new_doc("Stock Entry")
        ste.flags.ignore_permissions = True
        for i in item_table:
            ste.append("items", i)
        ste.update({
            "posting_date": jc_doc.posting_date,
            "posting_time": jc_doc.posting_time,
            "stock_entry_type": ste_type,
            "set_posting_time": 1,
            "process_job_card": jc_doc.name,
            "remarks": remarks
        })
        ste.save()
        ste.submit()
        frappe.msgprint(_("Stock Entry {} created").format(frappe.get_desk_link("Stock Entry", ste.name)))
    else:
        frappe.msgprint("No Stock Entry Created")


def cancel_delete_ste(jc_doc, trash_can=1):
    if jc_doc.no_stock_entry != 1:
        if trash_can == 0:
            ignore_on_trash = True
        else:
            ignore_on_trash = False

        ste_jc = frappe.db.sql("""SELECT name FROM `tabStock Entry` WHERE process_job_card = '%s'""" %
                               jc_doc.name, as_dict=1)
        if ste_jc:
            ste_doc = frappe.get_doc("Stock Entry", ste_jc[0].name)
            ste_doc.flags.ignore_permissions = True
            if ste_doc.docstatus == 1:
                ste_doc.cancel()
            frappe.delete_doc('Stock Entry', ste_jc[0].name, for_reload=ignore_on_trash)
        sle_dict = frappe.db.sql("""SELECT name FROM `tabStock Ledger Entry` WHERE voucher_type = 'Stock Entry' AND 
        voucher_no = '%s'""" % ste_jc[0].name, as_dict=1)
        for sle in sle_dict:
            frappe.delete_doc('Stock Ledger Entry', sle.name, for_reload=ignore_on_trash)
    else:
        frappe.msgprint("No Stock Entry Cancelled")


def delete_job_card(pro_sheet_doc, trash_can=1):
    if trash_can == 0:
        ignore_on_trash = True
    else:
        ignore_on_trash = False
    for row in pro_sheet_doc.operations:
        pro_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus < 1 AND operation_id 
        = '%s'""" % row.name, as_dict=1)
        if pro_jc:
            frappe.delete_doc('Process Job Card RIGPL', pro_jc[0].name, for_reload=ignore_on_trash)


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
