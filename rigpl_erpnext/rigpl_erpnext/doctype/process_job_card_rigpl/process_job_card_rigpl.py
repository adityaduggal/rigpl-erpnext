# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe.model.document import Document
from rigpl_erpnext.utils.manufacturing_utils import *
from ....utils.job_card_utils import *
from ....utils.process_sheet_utils import update_process_sheet_operations


class ProcessJobCardRIGPL(Document):
    def on_submit(self):
        validate_job_card_time_logs(self)
        update_job_card_status(self)
        self.validate_rm_qty_consumed()
        update_produced_qty(self)
        update_planned_qty(self.production_item, frappe.get_value("Process Sheet", self.process_sheet,
                                                                  "fg_warehouse"))
        create_submit_ste_from_job_card(self)
        update_pro_sheet_rm_from_jc(self)
        self.update_next_jc_status()
        self.create_new_jc_if_needed()

    def on_update_after_submit(self):
        update_job_card_qty_available(self)
        update_process_sheet_operations(ps_name=self.process_sheet, op_name=self.operation_id)

    def on_cancel(self):
        update_job_card_status(self)
        cancel_delete_ste(self)
        update_produced_qty(self, status="Cancel")
        update_planned_qty(self.production_item, frappe.get_value("Process Sheet", self.process_sheet,
                                                                  "fg_warehouse"))
        update_pro_sheet_rm_from_jc(self, status="Cancel")
        self.update_next_jc_status()
        update_process_sheet_operations(ps_name=self.process_sheet, op_name=self.operation_id)

    def validate(self):
        update_jc_posting_date_time(self)
        update_job_card_qty_available(self)
        update_job_card_priority(self)
        update_job_card_total_qty(self)
        update_job_card_status(self)
        self.update_job_card_qty_text()
        self.uom = frappe.get_value("Item", self.production_item, "stock_uom")
        if self.s_warehouse == self.t_warehouse:
            self.no_stock_entry = 1
        if not self.flags.ignore_mandatory:
            check_warehouse_in_child_tables(self, table_name="rm_consumed", type_of_table="Consume")
            check_warehouse_in_child_tables(self, table_name="item_manufactured", type_of_table="Production")
            validate_qty_decimal(self, "rm_consumed")
            validate_qty_decimal(self, "item_manufactured")
            pro_doc = frappe.get_doc('Process Sheet', self.process_sheet)
            for row in pro_doc.operations:
                if row.name == self.operation_id:
                    self.operation = row.operation
                    self.allow_consumption_of_rm = row.allow_consumption_of_rm
                    self.allow_production_of_wip_materials = row.allow_production_of_wip_materials

            if self.allow_consumption_of_rm != 1:
                self.set("rm_consumed", [])
            else:
                self.s_warehouse = ''
                if not self.rm_consumed:
                    get_items_from_process_sheet_for_job_card(self, "rm_consumed")

            if self.transfer_entry == 1 and not self.s_warehouse:
                op_doc = frappe.get_doc("BOM Operation", self.operation_id)
                self.s_warehouse = op_doc.source_warehouse
            else:
                op_doc = frappe.get_doc("BOM Operation", self.operation_id)
                if op_doc.transfer_entry != self.transfer_entry:
                    self.transfer_entry = op_doc.transfer_entry

            if self.rm_consumed:
                rm_item_dict = frappe.get_all("Process Sheet Items", fields=["item_code"],
                                              filters={'parenttype': 'Process Job Card RIGPL', 'parent': self.name,
                                                       'parentfield': 'rm_consumed'})
                self.update_calculated_qty(rm_item_dict)
                rm_qty_dict = find_item_quantities(rm_item_dict)

                for rm in rm_qty_dict:
                    for d in self.rm_consumed:
                        if rm.item_code == d.item_code and rm.warehouse == d.source_warehouse:
                            d.qty_available = rm.actual_qty
                            d.projected_qty = rm.actual_qty - rm.prd_qty - rm.on_so + rm.on_po + rm.planned
                            d.uom = rm.stock_uom

            if self.allow_production_of_wip_materials != 1:
                self.set("item_manufactured", [])
            else:
                if not self.item_manufactured:
                    get_items_from_process_sheet_for_job_card(self, "item_manufactured")
            if self.item_manufactured:
                wip_item_dict = frappe.get_all("Process Sheet Items", fields=["item_code"],
                                               filters={'parenttype': 'Process Job Card RIGPL', 'parent': self.name,
                                                        'parentfield': 'item_manufactured'})
                wip_qty_dict = find_item_quantities(wip_item_dict)
                for wip in wip_qty_dict:
                    for d in self.item_manufactured:
                        if wip.item_code == d.item_code and wip.warehouse == d.target_warehouse:
                            d.qty_available = wip.actual_qty
                            d.uom = wip.stock_uom
            check_produced_qty_jc(self)

    def update_job_card_qty_text(self):
        it_doc = frappe.get_doc("Item", self.production_item)
        qd = get_quantities_for_item(it_doc)
        ready = qd.finished_qty + qd.dead_qty
        qty_for_order = qd.on_so - ready
        min_needed = qd.reserved_for_prd + qd.on_so - qd.on_po - ready - qd.dead_qty + qd.calculated_rol
        text = f"SO = {qd.on_so} \n PO = {qd.on_po} \n Needed for PRD = {qd.reserved_for_prd} \n " \
               f"Finished Stock = {qd.finished_qty} \n Dead Stock = {qd.dead_qty} \n " \
               f"Work In Progress = {qd.wip_qty} \n" \
               f"Real ROL = {qd.re_order_level} But Calculated ROL = {qd.calculated_rol} \n " \
               f"Minimum Qty to be Produced = {min_needed} AND Qty Needed for Order = {qty_for_order}"
        if self.quantity_details != text:
            self.quantity_details = text

    def update_calculated_qty(self, rm_item_dict):
        wip_rm_consume = 0
        pro_sheet_doc = frappe.get_doc("Process Sheet", self.process_sheet)
        for d in self.item_manufactured:
            wip_calc_qty_dict = calculated_value_from_formula(rm_item_dict, d.item_code, fg_qty=d.qty,
                                                              bom_template_name= pro_sheet_doc.bom_template,
                                                              process_sheet_name=self.process_sheet, is_wip=1)
            for wip_it in wip_calc_qty_dict:
                if d.item_code == wip_it.fg_item_code:
                    wip_rm_consume += wip_it.qty
                    if d.calculated_qty != wip_it.qty:
                        d.calculated_qty = wip_it.qty
        rm_calc_qty_dict = calculated_value_from_formula(rm_item_dict, self.production_item,
                                                         fg_qty=(self.total_completed_qty + self.total_rejected_qty),
                                                         bom_template_name= pro_sheet_doc.bom_template,
                                                         process_sheet_name=self.process_sheet)
        for rm in self.rm_consumed:
            for rm_it in rm_calc_qty_dict:
                if rm.item_code == rm_it.rm_item_code:
                    wip_rm_consume += rm_it.qty
                    rm.calculated_qty = wip_rm_consume

    def get_items_from_process_sheet(self):
        get_items_from_process_sheet_for_job_card(self, "rm_consumed")
        get_items_from_process_sheet_for_job_card(self, "item_manufactured")

    def validate_rm_qty_consumed(self):
        for row in self.rm_consumed:
            if flt(row.qty) > flt(row.qty_available):
                frappe.throw('Available Qty = {} but Qty Needed = {} for Row# {} and Item Code: {} in '
                             'Warehouse {}'.format(row.qty_available, row.qty, row.idx, row.item_code,
                                                   row.source_warehouse), title="Warehouse Shortage")
            check_qty_job_card(row, row.calculated_qty, row.qty, row.uom, row.bypass_qty_check)

    def update_next_jc_status(self):
        nxt_jc_list = get_next_job_card(self.name)
        if nxt_jc_list:
            for jc in nxt_jc_list:
                nxt_jc_doc = frappe.get_doc(self.doctype, jc[0])
                update_job_card_qty_available(nxt_jc_doc)
                update_job_card_status(nxt_jc_doc)
                nxt_jc_doc.save()

    def create_new_jc_if_needed(self):
        new_jc_qty = 0
        ps_doc = frappe.get_doc("Process Sheet", self.process_sheet)
        jc_data = {}
        jc_data["operation"] = self.operation
        jc_data["workstation"] = self.workstation
        jc_data["source_warehouse"] = self.s_warehouse
        jc_data["target_warehouse"] = self.t_warehouse
        jc_data["allow_consumption_of_rm"] = self.allow_consumption_of_rm
        jc_data["allow_production_of_wip_materials"] = self.allow_production_of_wip_materials
        jc_data["name"] = self.operation_id
        new_jc_qty = (self.for_quantity - self.total_completed_qty)
        if self.check_if_new_jc_needed() == 1:
            create_job_card(pro_sheet=ps_doc, row=jc_data, quantity=new_jc_qty, auto_create=True)
        else:
            frappe.msgprint("No New Job Card needed")

    def check_if_new_jc_needed(self):
        if self.short_close_operation == 1:
            return 0
        allowance = flt(frappe.get_value("Manufacturing Settings", "Manufacturing Settings",
                                     "overproduction_percentage_for_work_order"))
        per_diff = abs(self.for_quantity - self.total_completed_qty - self.total_rejected_qty)
        # Returns 0 or 1: 0= No JC Needed and 1= New JC is needed
        # Checks if new JC is needed for an existing JC if its transfer entry and for Stock Items
        if self.for_quantity > self.total_completed_qty:
            if per_diff > allowance:
                if self.s_warehouse:
                    if self.sales_order_item:
                        return 1
                    else:
                        # This means stock item so check from Manufacturing Settings for allowance of closing
                        if per_diff > allowance:
                            return 1
                        else:
                            if self.shor_close_operation == 1:
                                return 0
                            else:
                                return 1
                else:
                    return 1
            else:
                if self.short_close_operation == 1:
                    return 0
                else:
                    return 1
        else:
            return 0
