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


def validate_job_card_time_logs(document):
    operation_doc = frappe.get_doc("Operation", document.operation)
    check_overlap = frappe.get_value("RIGPL Settings", "RIGPL Settings", "check_overlap_for_machines")
    if operation_doc.is_subcontracting == 1:
        validate_sub_contracting_job_cards(document, operation_doc)
        return
    if check_overlap == 1:
        future_time = frappe.get_value("RIGPL Settings", "RIGPL Settings", "future_time_mins")
        max_time = datetime.datetime.now() + datetime.timedelta(minutes=flt(future_time))
        total_mins = 0
        total_comp_qty = 0
        total_rej_qty = 0
        posting_date = getdate('1900-01-01')
        posting_time = get_time('00:00:00')
        now_time = get_datetime(nowtime())
        if not document.employee:
            frappe.throw("Employee is Needed in {}".format(frappe.get_desk_link(document.doctype, document.name)))
        if not document.workstation:
            frappe.throw("Workstation is Needed in {}".format(frappe.get_desk_link(document.doctype, document.name)))
        if document.get('time_logs'):
            tl_tbl = document.get('time_logs')
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
                data = get_overlap_for(document, tl_tbl[i])
                if data:
                    frappe.throw(_("Row {}: From Time and To Time of {} is overlapping with {}").format(tl_tbl[i].idx,
                            document.name, frappe.get_desk_link("Process Job Card RIGPL", data.name)))
                if tl_tbl[i].from_time and tl_tbl[i].to_time:
                    if getdate(tl_tbl[i].to_time) > posting_date:
                        posting_date = getdate(tl_tbl[i].to_time)
                        posting_time = get_time(tl_tbl[i].to_time)
                    if int(time_diff_in_hours(tl_tbl[i].to_time, tl_tbl[i].from_time) * 60) != tl_tbl[i].time_in_mins:
                        tl_tbl[i].time_in_mins = int(time_diff_in_hours(tl_tbl[i].to_time, tl_tbl[i].from_time) * 60)
                    total_mins += int(tl_tbl[i].time_in_mins)
                    if document.total_time_in_mins != int(total_mins):
                        document.total_time_in_mins = int(total_mins)
                if tl_tbl[i].completed_qty > 0:
                    total_comp_qty += tl_tbl[i].completed_qty
                if flt(tl_tbl[i].rejected_qty) > 0:
                    total_rej_qty += tl_tbl[i].rejected_qty
                if flt(tl_tbl[i].salvage_qty) > 0:
                    total_rej_qty += tl_tbl[i].salvage_qty
                    if not tl_tbl[i].salvage_warehouse:
                        frappe.throw("Salvage Warehouse is Mandatory if Salvage Qty > 0 for Row # {}".
                                     format(tl_tbl[i].idx))
                    else:
                        wh_doc = frappe.get_doc("Warehouse", tl_tbl[i].salvage_warehouse)
                        if wh_doc.warehouse_type != "Rejected":
                            roles_list = frappe.get_roles(frappe.session.user)
                            if 'System Manager' not in roles_list:
                                frappe.throw("Only System Manager allowed to Send Salvage Material to Non-Rejected "
                                             "Warehouse in Row# {}".format(tl_tbl[i].idx))

                if document.total_rejected_qty != total_rej_qty:
                    document.total_rejected_qty = total_rej_qty
                if document.total_completed_qty != total_comp_qty:
                    document.total_completed_qty = total_comp_qty
                if document.posting_date != posting_date and document.manual_posting_date_and_time != 1:
                    document.posting_date = posting_date
                if document.posting_time != posting_time and document.manual_posting_date_and_time != 1:
                    document.posting_time = str(posting_time)
                if document.manual_posting_date_and_time == 1:
                    if get_datetime(document.posting_date + " " + document.posting_time) > max_time:
                        frappe.throw("Posting Allowed only upto {}".format(max_time))
        else:
            frappe.throw("Time Logs Mandatory for Process Job Card {}".format(document.name))
    else:
        return


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
                frappe.throw("{} is already pending for Process Sheet {} in Row# {} and Operation {}".
                             format(frappe.get_desk_link("Process Job Card RIGPL", existing_pending_job_card[0].name),
                                    pro_sheet_name, row.idx, row.operation))
            else:
                create_job_card(ps_doc, row, quantity=(row.planned_qty - row.completed_qty), auto_create=True)
            break
