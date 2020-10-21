# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe.model.document import Document
from rigpl_erpnext.utils.manufacturing_utils import *
from ....utils.job_card_utils import *
from erpnext.stock.utils import get_bin


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
        # update_rm_qty_for_production(self)
        # frappe.throw("WIP")

    def on_cancel(self):
        update_job_card_status(self)
        cancel_delete_ste(self, trash_can=0)
        update_produced_qty(self, status="Cancel")
        update_planned_qty(self.production_item, frappe.get_value("Process Sheet", self.process_sheet,
                                                                  "fg_warehouse"))
        update_pro_sheet_rm_from_jc(self, status="Cancel")
        self.update_next_jc_status()

    def validate(self):
        update_job_card_status(self)
        if self.s_warehouse:
            self.qty_available = get_bin(self.production_item, self.s_warehouse).get("actual_qty")
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
                if not self.rm_consumed:
                    get_items_from_process_sheet_for_job_card(self, "rm_consumed")

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

    def update_calculated_qty(self, rm_item_dict):
        wip_rm_consume = 0
        pro_sheet_doc = frappe.get_doc("Process Sheet", self.process_sheet)
        for d in self.item_manufactured:
            wip_calc_qty_dict = calculated_value_from_formula(rm_item_dict, d.item_code, fg_qty=d.qty,
                                                              bom_template_name= pro_sheet_doc.bom_template,
                                                              so_detail=pro_sheet_doc.sales_order_item,
                                                              process_sheet_name=self.process_sheet)
            for wip_it in wip_calc_qty_dict:
                if d.item_code == wip_it.fg_item_code and d.calculated_qty != wip_it.qty:
                    d.calculated_qty = wip_it.qty
                    wip_rm_consume += wip_it.qty

        rm_calc_qty_dict = calculated_value_from_formula(rm_item_dict, self.production_item,
                                                         fg_qty=(self.total_completed_qty + self.total_rejected_qty),
                                                         bom_template_name= pro_sheet_doc.bom_template,
                                                         so_detail= pro_sheet_doc.sales_order_item,
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
        pro_doc = frappe.get_doc("Process Sheet", self.process_sheet)
        for op in pro_doc.operations:
            if op.name == self.operation_id:
                self_idx = op.idx
        for next_op in pro_doc.operations:
            if next_op.idx == self_idx + 1:
                next_op_name = next_op.name
                next_op_doc = frappe.get_doc("BOM Operation", next_op_name)
                update_job_card_status(next_op_doc)
