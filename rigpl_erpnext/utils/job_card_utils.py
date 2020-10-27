# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import datetime
from erpnext.stock.utils import get_bin
from frappe.utils import nowdate, nowtime, getdate, get_time, get_datetime, time_diff_in_hours, flt, add_to_date
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
        'allow_consumption_of_rm': row.get("allow_consumption_of_rm"),
        'allow_production_of_wip_materials': row.get("allow_production_of_wip_materials"),
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
        frappe.msgprint(_("{} created").format(frappe.get_desk_link("Process Job Card RIGPL", doc.name)))

    return doc


def update_job_card_qty_available(jc_doc):
    ps_doc = frappe.get_doc("Process Sheet", jc_doc.process_sheet)
    if jc_doc.sales_order != ps_doc.sales_order:
        jc_doc.sales_order = ps_doc.sales_order
    if jc_doc.sales_order_item != ps_doc.sales_order_item:
        jc_doc.sales_order_item = ps_doc.sales_order_item
    if jc_doc.sno != ps_doc.sno:
        jc_doc.sno = ps_doc.sno
    if jc_doc.s_warehouse:
        if not jc_doc.sales_order_item:
            jc_doc.qty_available = get_bin(jc_doc.production_item, jc_doc.s_warehouse).get("actual_qty")
        else:
            jc_doc.qty_available = get_made_to_stock_qty(jc_doc)
    else:
        jc_doc.qty_available = 0


def update_job_card_status(jc_doc):
    # Old Name = update_jc_status
    if jc_doc.docstatus == 2:
        jc_doc.status = 'Cancelled'
    elif jc_doc.docstatus == 1:
        jc_doc.status = 'Completed'
    elif jc_doc.docstatus == 0:
        # Job Card is WIP if No Source Warehouse. If Source Warehouse then if qty available > 0 then WIP else Open
        if jc_doc.s_warehouse:
            if jc_doc.qty_available > 0:
                jc_doc.status = "Work In Progress"
            else:
                jc_doc.status = "Open"
        else:
            jc_doc.status = "Work In Progress"


def check_existing_job_card(item_name, operation, so_detail=None):
    it_doc = frappe.get_doc("Item", item_name)
    if it_doc.made_to_order == 1:
        exist_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus = 0 
            AND operation = '%s' AND sales_order_item = '%s' AND production_item = '%s'"""
                                 %(operation, so_detail, item_name), as_dict=1)
    else:
        exist_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus = 0 
        AND operation = '%s' AND production_item = '%s' """ % (operation, item_name), as_dict=1)
    return exist_jc


def validate_qty_decimal(document, table_name):
    for row in document.get(table_name):
        row.qty = convert_qty_per_uom(row.qty, row.item_code)


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


def validate_job_card_time_logs(jc_doc):
    operation_doc = frappe.get_doc("Operation", jc_doc.operation)
    check_overlap = frappe.get_value("RIGPL Settings", "RIGPL Settings", "check_overlap_for_machines")
    update_job_card_posting_date(jc_doc)
    if operation_doc.is_subcontracting == 1:
        validate_sub_contracting_job_cards(jc_doc, operation_doc)
        return
    validate_job_card_quantities(jc_doc)
    if check_overlap == 1:
        future_time = frappe.get_value("RIGPL Settings", "RIGPL Settings", "future_time_mins")
        max_time = datetime.datetime.now() + datetime.timedelta(minutes=flt(future_time))
        total_mins = 0
        posting_date = getdate('1900-01-01')
        posting_time = get_time('00:00:00')
        now_time = get_datetime(nowtime())
        if not jc_doc.employee:
            frappe.throw("Employee is Needed in {}".format(frappe.get_desk_link(jc_doc.doctype, jc_doc.name)))
        if not jc_doc.workstation:
            frappe.throw("Workstation is Needed in {}".format(frappe.get_desk_link(jc_doc.doctype, jc_doc.name)))
        if jc_doc.get('time_logs'):
            tl_tbl = jc_doc.get('time_logs')
            for i in range(0, len(tl_tbl)):
                if i > 0:
                    if get_datetime(tl_tbl[i].from_time) < get_datetime(tl_tbl[i-1].to_time):
                        frappe.throw("Row# {}: From Time Cannot be Less than To Time in Row# {}".
                                     format(tl_tbl[i].idx, tl_tbl[i-1].idx))
                if get_datetime(tl_tbl[i].to_time) > max_time:
                    frappe.throw("To Time Not Allowed Beyond {} in Row# {}".format(max_time, tl_tbl[i].idx))
                if tl_tbl[i].completed_qty == 0:
                    frappe.throw("Zero Quantity Not Allowed for Row# {}".format(tl_tbl[i].idx))
                if get_datetime(tl_tbl[i].from_time) > get_datetime(tl_tbl[i].to_time):
                    frappe.throw(_("Row {0}: From time must be less than to time").format(tl_tbl[i].idx))
                data = get_overlap_for(jc_doc, tl_tbl[i])
                if data:
                    frappe.throw(_("Row {}: From Time and To Time of {} is overlapping with {}").format(tl_tbl[i].idx,
                            jc_doc.name, frappe.get_desk_link("Process Job Card RIGPL", data.name)))
                if tl_tbl[i].from_time and tl_tbl[i].to_time:
                    if getdate(tl_tbl[i].to_time) > posting_date:
                        posting_date = getdate(tl_tbl[i].to_time)
                        posting_time = get_time(tl_tbl[i].to_time)
                    if int(time_diff_in_hours(tl_tbl[i].to_time, tl_tbl[i].from_time) * 60) != tl_tbl[i].time_in_mins:
                        tl_tbl[i].time_in_mins = int(time_diff_in_hours(tl_tbl[i].to_time, tl_tbl[i].from_time) * 60)
                    total_mins += int(tl_tbl[i].time_in_mins)
                    if jc_doc.total_time_in_mins != int(total_mins):
                        jc_doc.total_time_in_mins = int(total_mins)
                if jc_doc.posting_date != posting_date and jc_doc.manual_posting_date_and_time != 1:
                    jc_doc.posting_date = posting_date
                if jc_doc.posting_time != posting_time and jc_doc.manual_posting_date_and_time != 1:
                    jc_doc.posting_time = str(posting_time)
                if jc_doc.manual_posting_date_and_time == 1:
                    if get_datetime(jc_doc.posting_date + " " + jc_doc.posting_time) > max_time:
                        frappe.throw("Posting Allowed only upto {}".format(max_time))
        else:
            frappe.throw("Time Logs Mandatory for Process Job Card {}".format(jc_doc.name))
    else:
        return


def validate_job_card_quantities(jc_doc):
    total_comp_qty = 0
    total_rej_qty = 0
    if jc_doc.get('time_logs'):
        for tl in jc_doc.get("time_logs"):
            if tl.completed_qty > 0:
                total_comp_qty += tl.completed_qty
            if flt(tl.rejected_qty) > 0:
                total_rej_qty += tl.rejected_qty
            if flt(tl.salvage_qty) > 0:
                total_rej_qty += tl.salvage_qty
                if not tl.salvage_warehouse:
                    frappe.throw("Salvage Warehouse is Mandatory if Salvage Qty > 0 for Row # {}".
                                 format(tl.idx))
                else:
                    wh_doc = frappe.get_doc("Warehouse", tl.salvage_warehouse)
                    if wh_doc.warehouse_type != "Rejected":
                        roles_list = frappe.get_roles(frappe.session.user)
                        if 'System Manager' not in roles_list:
                            frappe.throw("Only System Manager allowed to Send Salvage Material to Non-Rejected "
                                         "Warehouse in Row# {}".format(tl.idx))

    if jc_doc.total_rejected_qty != total_rej_qty:
        jc_doc.total_rejected_qty = total_rej_qty
    if jc_doc.total_completed_qty != total_comp_qty:
        jc_doc.total_completed_qty = total_comp_qty

def update_job_card_posting_date(jc_doc):
    if jc_doc.manual_posting_date_and_time != 1:
        jc_doc.posting_date = nowdate()
        jc_doc.posting_time = nowtime()


def get_overlap_for(document, row, check_next_available_slot=False):
    production_capacity = 1

    if document.workstation:
        production_capacity = frappe.get_cached_value("Workstation", document.workstation, 'production_capacity') or 1
        validate_overlap_for = " and jc.workstation = %(workstation)s "
    else:
        validate_overlap_for = ""

    extra_cond = ''
    if check_next_available_slot:
        extra_cond = " or (%(from_time)s <= jctl.from_time and %(to_time)s <= jctl.to_time)"

    existing = frappe.db.sql("""SELECT jc.name AS name, jctl.to_time FROM `tabJob Card Time Log` jctl, 
    `tabProcess Job Card RIGPL` jc 
    WHERE jctl.parent = jc.name AND jctl.parenttype = 'Process Job Card RIGPL' AND ((%(from_time)s > 
    jctl.from_time and %(from_time)s < jctl.to_time) OR (%(to_time)s > jctl.from_time and %(to_time)s < 
    jctl.to_time) OR (%(from_time)s <= jctl.from_time AND %(to_time)s >= jctl.to_time) {}) AND jctl.name != %(name)s 
    AND jc.name != %(parent)s and jc.docstatus < 2 {} 
    ORDER BY jctl.to_time desc limit 1""".format(extra_cond, validate_overlap_for), {"from_time": row.from_time,
        "to_time": row.to_time, "name": row.name or "No Name", "parent": row.parent or "No Name",
        "employee": document.employee, "workstation": document.workstation}, as_dict=True)
    if existing and production_capacity > len(existing):
        return

    return existing[0] if existing else None


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
        frappe.msgprint(_("{} created").format(frappe.get_desk_link("Stock Entry", ste.name)))
    else:
        frappe.msgprint("No Stock Entry Created")


def validate_sub_contracting_job_cards(jc_doc, op_doc):
    if jc_doc.no_stock_entry != 1:
        check_po_submitted(jc_doc)


def check_po_submitted(jc_doc):
    po_list = frappe.db.sql("""SELECT name FROM `tabPurchase Order Item` 
    WHERE docstatus=1 AND reference_dt = '%s' AND reference_dn = '%s'"""%(jc_doc.doctype, jc_doc.name), as_dict=1)
    if po_list:
        #Only allow Sub Contracting JC to be submitted after the  PO has been submitted
        pass
    else:
        frappe.throw("No Submitted PO for {}".format(frappe.get_desk_link(jc_doc.doctype, jc_doc.name)))


def get_made_to_stock_qty(jc_doc):
    # First get the Process Number of the Job Cards if its first Process then qty available = 0
    # Else the qty available is equal to the qty completed in previous process which are submitted.
    ps_doc = frappe.get_doc("Process Sheet", jc_doc.process_sheet)
    found = 0
    for op in ps_doc.operations:
        if op.name == jc_doc.operation_id or op.operation == jc_doc.operation:
            found = 1
            if op.idx == 1:
                return 0
            else:
                # Completed Qty is equal to Previous Process - Current Process JC Submitted
                completed_qty = 0
                prv_jc_list = get_job_card_from_process_sno((op.idx - 1), ps_doc, docstatus=1)
                same_process_jc_list = get_job_card_from_process_sno(op.idx, ps_doc, docstatus=1)
                if prv_jc_list:
                    for jc in prv_jc_list:
                        completed_qty += frappe.db.get_value("Process Job Card RIGPL", jc[0], "total_completed_qty")
                if same_process_jc_list:
                    for same_op_jc in same_process_jc_list:
                        completed_qty -= frappe.db.get_value("Process Job Card RIGPL", same_op_jc[0],
                                                             "total_completed_qty")
                return completed_qty
    if found == 0:
        frappe.throw("For {}, Operation {} is not mentioned in {}".
                     format(frappe.get_desk_link(jc_doc.doctype, jc_doc.name), jc_doc.operation,
                            frappe.get_desk_link(ps_doc.doctype, ps_doc.name)))


def get_completed_qty_of_jc_for_operation(item, operation, so_detail=None):
    completed_qty = frappe.db.sql("""SELECT SUM(total_completed_qty) FROM `tabProcess Job Card RIGPL` 
    WHERE docstatus = 1 AND production_item = '%s' AND operation = '%s' AND sales_order_item = '%s'""".
                                  format(item, operation, so_detail), as_list=1)
    if completed_qty[0][0]:
        return flt(completed_qty)
    else:
        return 0


def get_next_job_card(jc_no):
    jc_doc = frappe.get_doc("Process Job Card RIGPL", jc_no)
    ps_doc = frappe.get_doc("Process Sheet", jc_doc.process_sheet)
    jc_list = []
    found = 0
    for d in ps_doc.operations:
        if d.name == jc_doc.operation_id or d.operation == jc_doc.operation:
            #Found the Job Card Operation in PSheet
            if d.idx == len(ps_doc.operations):
                pass
            else:
                found = 1
                jc_list = get_job_card_from_process_sno((d.idx+1), ps_doc)
    if found == 0:
        frappe.msgprint("For {} no operation found in Process Sheet".format(frappe.get_desk_link(jc_doc.doctype,
                                                                                                 jc_doc.name)))
    return jc_list

def get_job_card_from_process_sno(operation_sno, ps_doc, docstatus=0):
    for d in ps_doc.operations:
        if d.idx == operation_sno:
            query ="""SELECT name FROM `tabProcess Job Card RIGPL` WHERE operation = '%s' AND docstatus = %s 
            AND production_item ='%s' AND sales_order_item = '%s'""" % (d.operation, docstatus,
                                                                        ps_doc.production_item, ps_doc.sales_order_item)
            jc_list = frappe.db.sql(query, as_list=1)
    return jc_list


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
def make_jc_from_pro_sheet_row(ps_name, production_item, operation, row_no, row_id, so_detail=None):
    existing_pending_job_card = check_existing_job_card(item_name=production_item, operation=operation,
                                                        so_detail=so_detail)
    if existing_pending_job_card:
        frappe.throw("{} is already pending for {} in Row# {} and Operation {}".
                     format(frappe.get_desk_link("Process Job Card RIGPL", existing_pending_job_card[0].name),
                                    production_item, row_no, operation))
    else:
        ps_doc = frappe.get_doc("Process Sheet", ps_name)
        row = frappe.get_doc("BOM Operation", row_id)
        create_job_card(ps_doc, row, quantity=(row.planned_qty - row.completed_qty), auto_create=True)
