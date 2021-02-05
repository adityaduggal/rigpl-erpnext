# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import datetime
from frappe.utils import nowdate, nowtime, getdate, get_time, get_datetime, time_diff_in_hours, flt
from .manufacturing_utils import *
from .sales_utils import get_priority_for_so
from .stock_utils import cancel_delete_ste_from_name


def create_job_card(pro_sheet, row, quantity=0, auto_create=False):
    doc = frappe.new_doc("Process Job Card RIGPL")
    doc.flags.ignore_permissions = True
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
        "transfer_entry": row.get("transfer_entry"),
        "final_operation": row.get("final_operation"),
        'allow_consumption_of_rm': row.get("allow_consumption_of_rm"),
        'allow_production_of_wip_materials': row.get("allow_production_of_wip_materials"),
        'for_quantity': quantity or (pro_sheet.get('quantity', 0) - pro_sheet.get('produced_qty', 0)),
        'operation_id': row.get("name")
    })
    if auto_create == 1:
        doc.flags.ignore_mandatory = True
        get_items_from_process_sheet_for_job_card(doc, "rm_consumed")
        get_items_from_process_sheet_for_job_card(doc, "item_manufactured")
        doc.insert()
        frappe.msgprint(_(f"{frappe.get_desk_link('Process Job Card RIGPL', doc.name)} created"))
        print(_(f"{doc.name} created"))
    return doc


def update_jc_posting_date_time(jc_doc):
    if jc_doc.manual_posting_date_and_time != 1:
        if jc_doc.docstatus == 0:
            jc_doc.posting_date = nowdate()
            jc_doc.posting_time = nowtime()


def check_produced_qty_jc(doc):
    if doc.s_warehouse:
        if doc.qty_available < (doc.total_completed_qty + doc.total_rejected_qty):
            frappe.throw("For Job Card# {} Qty Available for Item Code: {} in Warehouse: {} is {} but you are trying "
                         "to process {} quantities. Please correct this error.".\
                         format(doc.name, doc.production_item, doc.s_warehouse, doc.qty_available,
                                (doc.total_completed_qty + doc.total_rejected_qty)))
    else:
        min_qty, max_qty = get_min_max_ps_qty(doc.for_quantity)
        if (min_qty > doc.total_completed_qty and doc.short_close_operation == 1) or doc.total_completed_qty > max_qty:
            frappe.throw("For Job Card# {} allowed quantities to Manufacture is between {} and {}. So if you "
                         "are producing lower quantities then you cannot short close the Operation".format(doc.name,
                                                                                                    min_qty, max_qty))


def update_job_card_source_warehouse(jc_doc):
    change_needed = 0
    if jc_doc.transfer_entry == 1:
        if not jc_doc.s_warehouse:
            ps_op = frappe.db.sql("""SELECT name FROM `tabBOM Operation` WHERE parent='%s' 
            AND parenttype = 'Process Sheet' AND parentfield = 'operations' AND name = '%s'""" %
                                  (jc_doc.process_sheet, jc_doc.operation_id), as_dict=1)
            if ps_op:
                psd = frappe.get_doc("BOM Operation", ps_op[0].name)
                jc_doc.s_warehouse = psd.source_warehouse
                change_needed = 1
    return change_needed


def update_job_card_qty_available(jc_doc):
    ps_doc = frappe.get_doc("Process Sheet", jc_doc.process_sheet)
    if jc_doc.sales_order != ps_doc.sales_order:
        jc_doc.sales_order = ps_doc.sales_order
    if jc_doc.sales_order_item != ps_doc.sales_order_item:
        jc_doc.sales_order_item = ps_doc.sales_order_item
    if jc_doc.sno != ps_doc.sno:
        jc_doc.sno = ps_doc.sno
    jc_doc.qty_available = get_job_card_qty_available(jc_doc)


def get_job_card_qty_available(jc_doc):
    if jc_doc.s_warehouse:
        if jc_doc.sales_order_item:
            qty = get_made_to_stock_qty(jc_doc)
            if qty < 0:
                qty = 0
            return qty
        else:
            qty = get_bin(jc_doc.production_item, jc_doc.s_warehouse).actual_qty
            if qty < 0:
                qty = 0
            return qty
    else:
        return 0


def get_bin(item_code, warehouse):
    return frappe.db.sql("""SELECT name, item_code, warehouse, reserved_qty, actual_qty, ordered_qty, indented_qty,
        planned_qty, projected_qty, reserved_qty_for_production, reserved_qty_for_sub_contract, stock_uom, 
        valuation_rate, stock_value FROM `tabBin` WHERE item_code = '%s' 
        AND warehouse = '%s'""" % (item_code, warehouse), as_dict=1)[0]


def update_job_card_status(jc_doc):
    # Old Name = update_jc_status
    update_job_card_process_no(jc_doc)
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


def update_job_card_process_no(jc_doc):
    operation_sno, final_operation = get_job_card_process_sno(jc_doc)
    if jc_doc.operation_serial_no != operation_sno:
        jc_doc.operation_serial_no = operation_sno
    if jc_doc.final_operation != final_operation:
        jc_doc.final_operation = final_operation


def get_job_card_process_sno(jc_doc):
    ps_doc = frappe.get_doc("Process Sheet", jc_doc.process_sheet)
    bt_doc = frappe.get_doc("BOM Template RIGPL", ps_doc.bom_template)
    op_sno, final_op, found = [0,0,0]
    for op in bt_doc.operations:
        if op.operation == jc_doc.operation:
            found = 1
            op_sno = op.idx
            if op.final_operation == 1:
                final_op = 1
    if found == 0:
        op_sno = 0
        final_op = 0
    return op_sno, final_op


def return_job_card_qty(jcd):
    # Get Pending Process Sheets with Same Process and then check if RM Consumed in Process Sheet then RM should be same
    # If only Transfer entry then there is no need for RM.
    tot_qty = 0
    trf_entry = 0
    for_qty = 0
    extra_cond = ""
    if jcd.sales_order_item:
        extra_cond = " AND ps.sales_order_item = '%s'" % jcd.sales_order_item
    ps_sheet = frappe.db.sql("""SELECT ps.name, pso.operation, pso.planned_qty, pso.completed_qty, ps.creation,
    pso.allow_consumption_of_rm, pso.status, pso.transfer_entry, pso.name AS op_name
    FROM `tabProcess Sheet` ps, `tabBOM Operation` pso WHERE ps.docstatus = 1 AND pso.parent = ps.name 
    AND pso.parenttype = 'Process Sheet' AND pso.completed_qty < pso.planned_qty AND pso.status != "Completed" 
    AND pso.status != "Short Closed" AND pso.status != "Stopped" AND pso.status != "Obsolete"
    AND ps.production_item = '%s' AND pso.operation = '%s' %s ORDER BY ps.creation""" %
                             (jcd.production_item, jcd.operation, extra_cond), as_dict=1)
    for ps in ps_sheet:
        if ps.op_name == jcd.operation_id:
            for_qty = ps.planned_qty - ps.completed_qty
        if ps.allow_consumption_of_rm == 1 and jcd.allow_consumption_of_rm == 1:
            # Now check if the Raw Material is Same in both the PS and JC then you can combine the quantities
            psd = frappe.get_doc("Process Sheet", ps.name)

            psd_rm = []
            jcd_rm = []
            same_rm = 0
            for rm in jcd.rm_consumed:
                jcd_rm.append(rm.item_code)
            for rm in psd.rm_consumed:
                psd_rm.append(rm.item_code)
            if len(psd_rm) == len(jcd_rm):
                for rm in psd_rm:
                    if rm in jcd_rm:
                        same_rm += 1
                if same_rm == len(psd_rm):
                    tot_qty += (ps.planned_qty - ps.completed_qty)
        elif ps.transfer_entry == 1 and jcd.transfer_entry == 1:
            # Transfer entry if the qty available is less than total qty then total qty else available qty in WH
            trf_entry = 1
            tot_qty += (ps.planned_qty - ps.completed_qty)
        else:
            tot_qty += jcd.for_quantity
    if trf_entry == 1:
        pen_qty_prv_proces = 1
        qty_available = get_job_card_qty_available(jc_doc=jcd)
        if tot_qty < qty_available:
            tot_qty = qty_available
    return tot_qty, for_qty


def update_job_card_total_qty(jcd):
    tot_qty, for_qty = return_job_card_qty(jcd)
    jcd.total_qty = flt(tot_qty)
    jcd.for_quantity = flt(for_qty)


def update_job_card_priority(jc_doc):
    old_priority = jc_doc.priority
    new_priority = get_production_priority_for_item(jc_doc.production_item, jc_doc)
    if jc_doc.priority != new_priority:
        jc_doc.priority = new_priority


def get_production_priority_for_item(item_name, jc_doc):
    it_doc = frappe.get_doc("Item", item_name)
    qty_dict = get_quantities_for_item(it_doc)
    qty_before_process = 0
    if it_doc.made_to_order == 1:
        priority = get_priority_for_so(it_name=item_name, prd_qty=jc_doc.for_quantity, short_qty=jc_doc.for_quantity,
                                so_detail=jc_doc.sales_order_item)
        return priority
    else:
        # Check Process of JC Doc in Process Sheet and take decision based on Process Sheet and Operation Qty
        if jc_doc.for_quantity > jc_doc.qty_available:
            prd_qty = jc_doc.for_quantity
        else:
            prd_qty = jc_doc.qty_available
        soqty, poqty, pqty= qty_dict["on_so"], qty_dict["on_po"], qty_dict["planned_qty"]
        fqty, res_prd_qty, wipqty = qty_dict["finished_qty"], qty_dict["reserved_for_prd"], qty_dict["wip_qty"]
        dead_qty = qty_dict["dead_qty"]
        if soqty > 0:
            if soqty > fqty + dead_qty:
                # SO Qty is Greater than Finished Stock
                shortage = soqty - fqty - dead_qty
                if shortage > wipqty:
                    # Shortage of Material is More than WIP Qty
                    # Also check process number since last process should be More Urgent than 1st Process to fasten Prod
                    priority = get_priority_for_so(it_name=item_name, prd_qty=prd_qty, short_qty=shortage)
                    return priority
                else:
                    # Shortage is Less than Items in Production now get shortage for the Job Card First
                    jc_dict = get_open_job_cards_for_item(item_name)
                    if jc_dict:
                        for i in range(0, len(jc_dict)):
                            # Check for all process after the JCard for available qty
                            if jc_dict[i].name != jc_doc.name:
                                if jc_dict[i].transfer_entry == 1:
                                    shortage -= jc_dict[i].qty_available
                                else:
                                    shortage -= jc_dict[i].for_quantity
                            else:
                                # If same JC found then get out of loop since don't to consider later JC for process
                                break
                        if shortage > 0:
                            return get_priority_for_so(it_name=item_name, prd_qty=prd_qty,
                                                       short_qty=shortage)
                        else:
                            qty_before_process += get_qty_before_process(it_name=item_name, jc_doc=jc_doc)
                            return get_priority_for_stock_prd(it_name=item_name, qty_dict=qty_dict,
                                                              qty_before_process=qty_before_process)
                    else:
                        return get_priority_for_so(it_name=item_name, prd_qty=prd_qty,
                                                       short_qty=shortage)
            else:
                # Qty in Production is for Stock Only
                qty_before_process += get_qty_before_process(it_name=item_name, jc_doc=jc_doc)
                return get_priority_for_stock_prd(it_name=item_name, qty_dict=qty_dict,
                                                  qty_before_process=qty_before_process)
        else:
            # No Order for Item
            # For Stock Production Priority
            qty_before_process += get_qty_before_process(it_name=item_name, jc_doc=jc_doc)
            return get_priority_for_stock_prd(it_name=item_name, qty_dict=qty_dict,
                                              qty_before_process=qty_before_process)


def get_qty_before_process(it_name, jc_doc):
    qty_before_process = 0
    all_jc = get_open_job_cards_for_item(it_name)
    if all_jc:
        for jc in all_jc:
            if jc.name != jc_doc.name:
                if jc.transfer_entry == 1:
                    qty_before_process += jc.qty_available
                else:
                    qty_before_process += jc.for_quantity
            else:
                break
    return qty_before_process


def get_open_job_cards_for_item(item_name):
    jc_dict = frappe.db.sql("""SELECT name, production_item, for_quantity, qty_available, operation, 
    operation_serial_no, s_warehouse, transfer_entry FROM `tabProcess Job Card RIGPL` WHERE docstatus=0 
    AND production_item = '%s' ORDER BY operation_serial_no DESC""" % item_name, as_dict=1)
    return jc_dict


def check_existing_job_card(item_name, operation, so_detail=None, ps_doc=None):
    """
    Existing Job Card is considered with the following Conditions:
    1. Operation is Same and the Operation is Transfer Entry then the JC is existing
    2. If the operation is same but there is consumption of RM then if the RM is same then existing JC else the JC is
    not same
    """
    it_doc = frappe.get_doc("Item", item_name)
    if it_doc.made_to_order == 1:
        exist_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus = 0 
            AND operation = '%s' AND sales_order_item = '%s' AND production_item = '%s'"""
                                 %(operation, so_detail, item_name), as_dict=1)
    else:
        exist_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus = 0 
            AND operation = '%s' AND production_item = '%s' """ % (operation, item_name), as_dict=1)

    new_exist_jc = []
    new_jc_dict = frappe._dict({})
    if ps_doc:
        for op in ps_doc.operations:
            if op.operation == operation:
                if op.allow_consumption_of_rm == 1:
                    for jc in exist_jc:
                        jcd = frappe.get_doc("Process Job Card RIGPL", jc.name)
                        if jcd.allow_consumption_of_rm == 1:
                            # Now both Operation and JC have consumption of RM and now check if RM is same
                            jc_rm = []
                            ps_rm = []
                            same_rm = 0
                            for rm in jcd.rm_consumed:
                                jc_rm.append(rm.item_code)
                            for rm in ps_doc.rm_consumed:
                                ps_rm.append(rm.item_code)
                            if len(ps_rm) == len(jc_rm):
                                for rm in jc_rm:
                                    if rm in ps_rm:
                                        same_rm += 1
                                if same_rm == len(jc_rm):
                                    # Return JC No
                                    new_jc_dict["name"] = jc.name
                                    new_exist_jc.append(new_jc_dict)
                                else:
                                    # JC is having different RM so no existing JC
                                    pass
                elif op.transfer_entry:
                    for jc in exist_jc:
                        jcd = frappe.get_doc("Process Job Card RIGPL", jc.name)
                        if jcd.transfer_entry == 1:
                            new_jc_dict["name"] = jc.name
                            new_exist_jc.append(new_jc_dict)
    return new_exist_jc


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
                it_dict.setdefault("qty", d.rejected_qty)
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
        frappe.msgprint(_("{} Submitted").format(frappe.get_desk_link("Stock Entry", ste.name)))
    else:
        frappe.msgprint("No Stock Entry Created")


def validate_sub_contracting_job_cards(jc_doc, op_doc):
    if jc_doc.no_stock_entry != 1:
        check_po_submitted(jc_doc)


def check_po_submitted(jc_doc):
    po_list = frappe.db.sql("""SELECT name FROM `tabPurchase Order Item` 
    WHERE docstatus=1 AND reference_dt = '%s' AND reference_dn = '%s'"""%(jc_doc.doctype, jc_doc.name), as_dict=1)
    if po_list:
        # Only allow Sub Contracting JC to be submitted after the  PO has been submitted
        pass
    else:
        frappe.throw("No Submitted PO for {}".format(frappe.get_desk_link(jc_doc.doctype, jc_doc.name)))


def get_last_jc_for_so(so_item):
    jc_list = frappe.db.sql("""SELECT jc.name, jc.status, jc.operation, jc.priority, jc.for_quantity, jc.qty_available, 
    jc.docstatus, jc.process_sheet, bmop.idx, jc.total_completed_qty
    FROM `tabProcess Job Card RIGPL` jc, `tabBOM Operation` bmop 
    WHERE jc.docstatus < 2 AND bmop.parent = jc.process_sheet AND bmop.operation = jc.operation
    AND jc.sales_order_item = '%s'""" % so_item, as_dict=1)
    jc_list =  sorted(jc_list, key = lambda i: i['idx'])
    jc = {}
    if jc_list:
        for i in range(0, len(jc_list)):
            jc = jc_list[i]
            jc["remarks"] = ""
            if jc_list[i].docstatus == 1:
                if i == len(jc_list) - 1:
                    jc["remarks"] += " All Operations Completed {} Qty Ready for Dispatch".\
                        format(jc_list[i].total_completed_qty)
                else:
                    # Check if Operation is Job Work and if so then check if PO item is completed or Not
                    # if PO is pending then remarks should show PO# and PO Date else show Process Completed
                    op_doc = frappe.get_doc("Operation", jc_list[i].operation)
                    if op_doc.is_subcontracting == 1:
                        po_details = frappe.db.sql("""SELECT po.name, po.transaction_date, poi.stock_qty, 
                        poi.received_qty FROM `tabPurchase Order` po, `tabPurchase Order Item` poi 
                        WHERE po.docstatus = 1 AND poi.parent = po.name AND poi.reference_dt = 'Process Job Card RIGPL' 
                        AND poi.reference_dn = '%s'""" % jc_list[i].name, as_dict=1)
                        if po_details:
                            for po in po_details:
                                if po.stock_qty > po.received_qty:
                                    po_link = """<a href="#Form/Purchase Order/%s" target="_blank">%s</a>""" % (po.name, po.name)
                                    jc["remarks"] += f" PO# {po_link} Pending Qty= {po.stock_qty - po.received_qty} " \
                                                     f"PO Date: {po.transaction_date}"
                                    return jc
                                    break
            else:
                if i == 0:
                    jc["remarks"] += "Taken into Production but First Process is Pending"
                else:
                    jc["remarks"] += " " + jc.operation + " Pending and " + jc_list[i-1].operation + " Completed"
                break
    return jc


def get_made_to_stock_qty(jc_doc):
    # First get the Process Number of the Job Cards if its first Process then qty available = 0 for Made to Order
    # But first process qty = qty of Sales Order if the Item is Sales Job Work Item since JW items are received at SO
    # Else the qty available in Source Warehouse is Equal to the qty available for completed job cards for target WH
    ps_doc = frappe.get_doc("Process Sheet", jc_doc.process_sheet)
    it_doc = frappe.get_doc("Item", jc_doc.production_item)
    found = 0
    for op in ps_doc.operations:
        if op.name == jc_doc.operation_id or op.operation == jc_doc.operation:
            found = 1
            if op.idx == 1:
                if it_doc.sales_job_work == 1:
                    return flt(frappe.get_value("Sales Order Item", jc_doc.sales_order_item, "qty"))
                else:
                    return 0
            else:
                # Completed Qty is equal completed qty for Target WH - Completed Qty of Source WH
                completed_qty = 0
                if jc_doc.s_warehouse:
                    # If Source WH is there then check IN - OUT Qty, IN Qty is also from GRN for Sub-Contracting.
                    query = """SELECT SUM(total_completed_qty)  as in_qty FROM `tab%s` WHERE status = "Completed" 
                    AND t_warehouse = '%s' AND docstatus = 1 AND sales_order_item='%s'""" %\
                            (jc_doc.doctype, jc_doc.s_warehouse, jc_doc.sales_order_item)
                    in_qty = frappe.db.sql(query, as_dict=1)
                    grn_in_qty = get_grn_qty(jc_doc)
                    if in_qty:
                        in_qty = flt(in_qty[0].in_qty)
                    else:
                        in_qty = 0
                    out_qty = frappe.db.sql("""SELECT SUM(total_completed_qty)  as out_qty FROM `tab%s`
                    WHERE status = "Completed" AND s_warehouse = '%s' AND docstatus = 1 AND sales_order_item='%s'""" %
                                           (jc_doc.doctype, jc_doc.s_warehouse, jc_doc.sales_order_item), as_dict=1)
                    if out_qty:
                        out_qty = flt(out_qty[0].out_qty)
                    else:
                        out_qty = 0
                    completed_qty = in_qty - out_qty + grn_in_qty
                return completed_qty
    if found == 0:
        frappe.throw("For {}, Operation {} is not mentioned in {}".
                     format(frappe.get_desk_link(jc_doc.doctype, jc_doc.name), jc_doc.operation,
                            frappe.get_desk_link(ps_doc.doctype, ps_doc.name)))


def get_grn_qty(jc_doc):
    qty = 0
    prev_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE sales_order_item = '%s'
    AND docstatus = 1 AND name != '%s'""" % (jc_doc.sales_order_item, jc_doc.name),
                            as_dict=1)
    if prev_jc:
        for oth_jc in prev_jc:
            oth_doc = frappe.get_doc(jc_doc.doctype, oth_jc.name)
            op_doc = frappe.get_doc("Operation", oth_doc.operation)
            if op_doc.is_subcontracting == 1:
                po = frappe.db.sql("""SELECT po.name as po, poi.name FROM `tabPurchase Order` po, 
                `tabPurchase Order Item` poi WHERE po.docstatus=1 AND poi.parent = po.name ANd poi.reference_dn = '%s'
                AND poi.reference_dt = '%s'""" % (oth_jc.name, jc_doc.doctype), as_dict=1)
                if po:
                    # Check if GRN is submitted for this PO
                    grn_list = frappe.db.sql("""SELECT pri.qty, pri.warehouse FROM `tabPurchase Receipt` pr, 
                    `tabPurchase Receipt Item` pri WHERE pri.parent = pr.name AND pr.docstatus = 1 
                    AND pri.purchase_order_item = '%s'""" % po[0].name, as_dict=1)
                    if grn_list:
                        for grn in grn_list:
                            if grn.warehouse == jc_doc.s_warehouse:
                                qty += grn.qty
    return qty


def get_next_job_card(jc_no):
    jc_doc = frappe.get_doc("Process Job Card RIGPL", jc_no)
    ps_doc = frappe.get_doc("Process Sheet", jc_doc.process_sheet)
    jc_list = []
    found = 0
    for d in ps_doc.operations:
        if d.name == jc_doc.operation_id or d.operation == jc_doc.operation:
            # Found the Job Card Operation in PSheet
            if d.idx == len(ps_doc.operations):
                pass
            else:
                found = 1
                jc_list = get_job_card_from_process_sno((d.idx+1), ps_doc)
    return jc_list


def get_job_card_from_process_sno(operation_sno, ps_doc):
    if ps_doc.sales_order_item:
        cond = " AND sales_order_item = '%s'" % ps_doc.sales_order_item
    else:
        cond = ""
    for d in ps_doc.operations:
        if d.idx == operation_sno:
            query = """SELECT name FROM `tabProcess Job Card RIGPL` WHERE operation = '%s' AND docstatus = 0
            AND production_item ='%s' %s ORDER BY creation""" % (d.operation, ps_doc.production_item, cond)
            jc_list = frappe.db.sql(query, as_list=1)
    return jc_list


def cancel_delete_ste(jc_doc):
    if jc_doc.no_stock_entry != 1:
        ste_jc = frappe.db.sql("""SELECT name FROM `tabStock Entry` WHERE process_job_card = '%s'""" %
                               jc_doc.name, as_dict=1)
        if ste_jc:
            cancel_delete_ste_from_name(ste_jc[0].name)
    else:
        frappe.msgprint("No Stock Entry Cancelled")


def delete_job_card(pro_sheet_doc):
    for row in pro_sheet_doc.operations:
        pro_jc = frappe.db.sql("""SELECT name FROM `tabProcess Job Card RIGPL` WHERE docstatus < 1 AND operation_id 
        = '%s'""" % row.name, as_dict=1)
        if pro_jc:
            frappe.delete_doc('Process Job Card RIGPL', pro_jc[0].name, for_reload=True)


@frappe.whitelist()
def make_jc_from_pro_sheet_row(ps_name, production_item, operation, row_no, row_id, so_detail=None):
    psd = frappe.get_doc("Process Sheet", ps_name)
    opd = frappe.get_doc("BOM Operation", row_id)
    existing_pending_job_card = check_existing_job_card(item_name=production_item, operation=operation,
                                                        so_detail=so_detail, ps_doc=psd)
    jcr_needed = check_jc_needed_for_ps(psd)
    if jcr_needed == 1:
        if existing_pending_job_card:
            frappe.msgprint("{} is already pending for {} in Row# {} and Operation {}".
                         format(frappe.get_desk_link("Process Job Card RIGPL", existing_pending_job_card[0].name),
                                        production_item, row_no, operation))
        else:
            ps_doc = frappe.get_doc("Process Sheet", ps_name)
            row = frappe.get_doc("BOM Operation", row_id)
            create_job_card(ps_doc, row, quantity=(row.planned_qty - row.completed_qty), auto_create=True)
        if opd.completed_qty > 0:
            opd.status = "In Progress"
        else:
            opd.status = "Pending"
        opd.save()
    else:
        frappe.msgprint(f"No Job Card is Needed for {psd.name}")
