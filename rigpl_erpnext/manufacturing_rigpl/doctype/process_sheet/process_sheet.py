# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

from frappe.model.document import Document
from frappe.utils import nowdate

from ....utils.sales_utils import get_priority_for_so
from ....utils.stock_utils import get_quantities_for_item
from ...utils.job_card_utils import delete_job_card
from ...utils.manufacturing_utils import (
    calculate_batch_size,
    calculate_operation_cost,
    calculate_operation_time,
    calculated_value_from_formula,
    find_item_quantities,
    get_priority_for_stock_prd,
    get_qty_to_manufacture,
    update_warehouse_from_bt,
)
from ...utils.process_sheet_utils import *


class ProcessSheet(Document):
    def on_submit(self):
        bt_doc = frappe.get_doc("BOM Template RIGPL", self.bom_template)
        allow_rm_consumption = 0
        for op in self.operations:
            update_process_sheet_operations(self.name, op.name)
            if op.allow_consumption_of_rm == 1:
                allow_rm_consumption = 1

        if allow_rm_consumption == 1:
            if not self.rm_consumed:
                frappe.throw(
                    "Raw Material Consumption is Required for this Process Sheet"
                )
            else:
                self.validate_no_of_raw_material_items(bt_doc)

        if self.quantity == 0:
            frappe.throw("Not Allowed to Submit Quantity Equal to ZERO")
        update_planned_qty(self.production_item, self.fg_warehouse)
        for d in self.rm_consumed:
            update_qty_for_prod(
                d.item_code, d.source_warehouse, table_name="rm_consumed"
            )
        make_jc_for_process_sheet(self)

    def on_cancel(self):
        frappe.db.set_value("Process Sheet", self.name, "status", "Cancelled")
        update_planned_qty(self.production_item, self.fg_warehouse)
        for d in self.rm_consumed:
            update_qty_for_prod(
                d.item_code, d.source_warehouse, table_name="rm_consumed"
            )
        for row in self.operations:
            existing_jc = check_existing_job_card(
                item_name=self.production_item,
                operation=row.operation,
                so_detail=self.sales_order_item,
                ps_doc=self,
            )
            if existing_jc:
                # Update the Total Quantity for All the Job Cards which are existing
                for jc in existing_jc:
                    jcd = frappe.get_doc("Process Job Card RIGPL", jc.name)
                    update_job_card_total_qty(jcd)
                    if jcd.process_sheet != self.name:
                        jcd.save()
        delete_job_card(self)

    def validate(self):
        itd = frappe.get_doc("Item", self.production_item)
        update_priority_psd(self, itd)
        # Priority and Auto Quantity
        self.update_ps_status()
        self.validate_other_psheet()
        if not self.flags.ignore_mandatory:
            it_doc = frappe.get_doc("Item", self.production_item)
            disallow_templates(self, it_doc)
            if not self.bom_template:
                bom_tmp_name = get_bom_template_from_item(it_doc, self.sales_order_item)
            else:
                bom_tmp_name = [self.bom_template]
            if not bom_tmp_name:
                frappe.throw("No BOM Template Found")
            else:
                bom_tmp_doc = frappe.get_doc("BOM Template RIGPL", bom_tmp_name[0])
                self.update_ps_fields(bom_tmp_doc, it_doc)

    def validate_other_psheet(self):
        if self.production_item:
            it_doc = frappe.get_doc("Item", self.production_item)
            if it_doc.variant_of:
                other_ps = frappe.db.sql(
                    """SELECT name FROM `tabProcess Sheet` WHERE docstatus = 0
                AND production_item = '%s' AND name <> '%s' """
                    % (self.production_item, self.name),
                    as_dict=1,
                )
            else:
                if self.sales_order_item:
                    other_ps = frappe.db.sql(
                        """SELECT name FROM `tabProcess Sheet` WHERE docstatus = 0 AND
                    production_item = '%s' AND sales_order_item = '%s' AND name != '%s'"""
                        % (self.production_item, self.sales_order_item, self.name),
                        as_dict=1,
                    )
                else:
                    frappe.throw(
                        "Sales Order is Mandatory for Item: {} in Process Sheet {}".format(
                            self.production_item, self.name
                        )
                    )
            if other_ps:
                if self.sales_order:
                    frappe.throw(
                        f"{frappe.get_desk_link('Process Sheet', other_ps[0].name)} for Item: "
                        f"{self.production_item} and Sales Order {self.sales_order} already in Draft. "
                        f"Cannot Proceed",
                        title="Another Process Sheet with Same Item in Draft",
                    )
                else:
                    frappe.throw(
                        f"{frappe.get_desk_link('Process Sheet', other_ps[0].name)} for Item: "
                        f"{self.production_item} already in Draft. Cannot Proceed",
                        title="Another Process Sheet with Same Item in Draft",
                    )

    def fill_details_from_item(self):
        item_doc = frappe.get_doc("Item", self.production_item)
        if not self.bom_template:
            bom_template = get_bom_template_from_item(item_doc, self.sales_order_item)
            if not bom_template:
                frappe.msgprint("NO BOM Template Found")
            else:
                self.total_applicable_bom_templates = len(bom_template)
                bom_template = bom_template[0]
        else:
            bom_template = self.bom_template
        if bom_template:
            self.bom_template = bom_template
        else:
            self.set("rm_consumed", [])
            self.set("item_manufactured", [])
            self.set("operations", [])
            frappe.throw("No BOM Template found for {}".format(self.production_item))
        bom_temp_doc = frappe.get_doc("BOM Template RIGPL", self.bom_template)
        self.routing = bom_temp_doc.routing
        self.set("rm_consumed", [])
        self.set("item_manufactured", [])

    def update_ps_fields(self, bt_doc, it_doc):
        if self.date != nowdate():
            self.date = nowdate()
        self.total_applicable_bom_templates = len(
            get_bom_template_from_item(it_doc, self.sales_order_item)
        )
        self.bom_template = bt_doc.name
        if bt_doc.remarks:
            remarks = ", Remarks: " + bt_doc.remarks
        else:
            remarks = ""
        self.bom_template_description = "Title: " + bt_doc.title + remarks
        self.routing = bt_doc.routing
        self.get_routing_from_template()
        self.validate_qty_to_manufacture(it_doc)
        for row in self.operations:
            if row.planned_qty != self.quantity:
                row.planned_qty = self.quantity
        if self.get("__islocal") != 1:
            self.get_rm_sizes(bt_doc)

    def get_rm_sizes(self, bt_doc):
        get_rm = 0
        for op in bt_doc.operations:
            if op.allow_consumption_of_rm == 1:
                get_rm = 1
        if get_rm != 1:
            return

        def_rm_warehouse = ""
        if self.raw_material_source_warehouse:
            def_rm_warehouse = self.raw_material_source_warehouse
        else:
            for d in self.operations:
                if d.allow_consumption_of_rm == 1:
                    def_rm_warehouse = d.rm_warehouse
        item_dict = frappe._dict({})
        item_dict["known_item"] = self.production_item
        item_dict["known_type"] = "fg"
        item_list = self.get_item_list(
            self.production_item, known_type="fg", unknown_type="rm"
        )
        if not self.rm_consumed:
            rm_item_dict = get_req_sizes_from_template(
                bom_temp_name=self.bom_template,
                item_type_list=item_list,
                table_name="rm_restrictions",
                allow_zero_rol=1,
                ps_name=self.name,
            )
        else:
            rm_item_dict = self.make_rm_item_dict()
        if not rm_item_dict:
            frappe.throw(
                "NO Raw Material Found. Possible Solutions /n"
                "1. Check Box for Show Unavailable Raw Material \n"
                "2. Change Raw Material Warehouse in the Process Sheet \n"
                "3. Change the BOM Template from {}".format(self.bom_template)
            )
        rm_calc_qty_list = calculated_value_from_formula(
            rm_item_dict,
            self.production_item,
            fg_qty=self.quantity,
            process_sheet_name=self.name,
            bom_template_name=self.bom_template,
        )
        wip_list = []
        for rm in rm_item_dict:
            wip_item_dict = get_req_wip_sizes_from_template(
                self.bom_template,
                fg_item=self.production_item,
                table_name="wip_restrictions",
                rm_item=rm.get("name"),
                allow_zero_rol=self.allow_zero_rol_for_wip,
                process_sheet_name=self.name,
            )
            dont_add = 0
            if wip_item_dict:
                for wip in wip_item_dict:
                    if wip_list:
                        for final in wip_list:
                            if wip.name in final.name:
                                dont_add = 1
                        if dont_add == 0:
                            wip_list.append(wip.copy())
                    else:
                        wip_list.append(wip.copy())
            else:
                self.item_manufactured = []
        if rm_item_dict:
            if not self.rm_consumed:
                update_item_table(rm_item_dict, "rm_consumed", self)
            for d in self.rm_consumed:
                d.source_warehouse = def_rm_warehouse
            qty_dict = find_item_quantities(rm_item_dict)
            if qty_dict:
                for d in qty_dict:
                    for rm in self.rm_consumed:
                        if (
                            d.item_code == rm.item_code
                            and d.warehouse == rm.source_warehouse
                        ):
                            rm.target_warehouse = ""
                            rm.uom = d.stock_uom
                            rm.qty = 0
                            rm.qty_available = d.actual_qty
                            rm.current_projected_qty = (
                                d.actual_qty - d.prd_qty - d.on_so
                            )
                            rm.projected_qty = (
                                d.actual_qty - d.prd_qty - d.on_so + d.on_po + d.planned
                            )
                        for rm_calc in rm_calc_qty_list:
                            if rm.item_code == rm_calc.rm_item_code:
                                rm.calculated_qty = int(rm_calc.qty)
        else:
            frappe.throw("No RM found as per Rules in BOM Template")
        if wip_list:
            wip_qty_dict = find_item_quantities(wip_list)
            if not self.item_manufactured:
                update_item_table(wip_list, "item_manufactured", self)
            else:
                for wip in self.item_manufactured:
                    if wip_qty_dict:
                        act_qty, so_qty, po_qty, prd_qty, plan_qty = 0, 0, 0, 0, 0
                        for d in wip_qty_dict:
                            if d.item_code == wip.item_code:
                                wip.uom = d.stock_uom
                                act_qty += d.actual_qty
                                so_qty += d.on_so
                                po_qty += d.on_po
                                prd_qty += d.prd_qty
                                plan_qty += d.planned
                        cur_proj = act_qty - so_qty - prd_qty
                        wip.qty_available = act_qty
                        wip.current_projected_qty = cur_proj
                        wip.projected_qty = cur_proj + po_qty + plan_qty
                        wip.qty = 0
            for op in self.operations:
                if op.allow_production_of_wip_materials == 1:
                    for wip in self.item_manufactured:
                        wip.target_warehouse = op.wip_material_warehouse
                        wip.source_warehouse = ""

    def validate_qty_to_manufacture(self, it_doc):
        auto_qty, max_auto_qty = get_qty_to_manufacture(it_doc)
        self.auto_qty = auto_qty
        self.max_auto_qty = max_auto_qty
        dead_qty = get_quantities_for_item(it_doc)["dead_qty"]
        if dead_qty > 0 and self.bypass_all_qty_checks != 1:
            frappe.throw(
                f"There are {dead_qty} Qty in Dead Stock for {self.production_item}.\nHence Cannot Proceed"
            )
        if self.bypass_all_qty_checks == 1:
            if auto_qty != self.quantity:
                frappe.msgprint(
                    f"Qty Calculated = {auto_qty} But Entered Qty= {self.quantity}"
                )
            return
        if auto_qty == self.quantity:
            self.update_qty_manually = 0
        if self.update_qty_manually != 1:
            if not self.sales_order_item:
                self.quantity = auto_qty
            else:
                self.quantity = self.get_balance_qty_from_so(self.sales_order_item)
        else:
            if not self.sales_order_item:
                if self.quantity != auto_qty:
                    frappe.msgprint(
                        "Calculated Qty to Manufacture = "
                        + str(auto_qty)
                        + " but Qty entered to Manufacture  = "
                        + str(self.quantity)
                    )
            else:
                pend_qty = self.get_balance_qty_from_so(self.sales_order_item)
                if pend_qty < self.quantity:
                    self.update_qty_manually = 0
                    self.quantity = pend_qty
                    frappe.msgprint(
                        "For {} Item in Row#{} Pending Qty= {} but Qty Planned= {}".format(
                            frappe.get_desk_link("Sales Order", self.sales_order),
                            self.sno,
                            pend_qty,
                            self.quantity,
                        )
                    )
        if self.quantity > self.max_auto_qty and self.bypass_all_qty_checks != 1:
            vrate = flt(
                frappe.get_value("Item", self.production_item, "valuation_rate")
            )
            max_amt = flt(
                frappe.get_value(
                    "RIGPL Settings", "RIGPL Settings", "max_value_over_max_qty_allowed"
                )
            )
            excess_amt = (self.quantity - self.max_auto_qty) * vrate
            if excess_amt > max_amt and vrate > 1:
                frappe.throw(
                    f"Max Qty Allowed to Manufacture = {max_auto_qty}.<br>"
                    f"Also Max Excess Amount allowed = {max_amt} & Valuation Rate of Item is {vrate}.<br>"
                    f"But you are trying to Manufacture excess qty with amount of {excess_amt}.<br>"
                    f"Either Bypass Qty Check or Change Qty to Manufacture"
                )

    def get_balance_qty_from_so(self, so_detail):
        soi_doc = frappe.get_doc("Sales Order Item", so_detail)
        qty_in_prd = frappe.db.sql(
            """SELECT SUM(quantity) FROM `tabProcess Sheet` WHERE docstatus=1 AND
        status NOT IN ("Stopped", "Short Closed") AND production_item = '%s'
        AND sales_order_item = '%s'"""
            % (soi_doc.item_code, so_detail),
            as_list=1,
        )
        if qty_in_prd:
            qty_in_prd = flt(qty_in_prd[0][0])
        else:
            qty_in_prd = 0
        qty_stopped = frappe.db.sql(
            """SELECT SUM(produced_qty) - SUM(short_closed_qty)
        FROM `tabProcess Sheet` WHERE docstatus=1 AND status IN ("Stopped", "Short Closed")
        AND production_item = '%s' AND sales_order_item = '%s'"""
            % (soi_doc.item_code, so_detail),
            as_list=1,
        )
        if qty_stopped:
            qty_stopped = flt(qty_stopped[0][0])
        else:
            qty_stopped = 0
        forced_qty = soi_doc.qty - soi_doc.delivered_qty - qty_in_prd - qty_stopped
        if forced_qty < 0:
            forced_qty = 0
        return forced_qty

    def update_ps_status(self):
        if self.docstatus == 0:
            self.status = "Draft"
        elif self.docstatus == 1:
            self.status = "Submitted"
        elif self.docstatus == 2:
            self.status = "Cancelled"

    def get_routing_from_template(self):
        fg_it_doc = frappe.get_doc("Item", self.production_item)
        if not self.bom_template:
            bom_tmp_name = get_bom_template_from_item(fg_it_doc, self.sales_order_item)
            if bom_tmp_name:
                self.total_applicable_bom_templates = len(bom_tmp_name)
        else:
            bom_tmp_name = self.bom_template
        item_list = self.get_item_list(
            item_name=self.production_item, known_type="fg", unknown_type="rm"
        )
        bt_doc = frappe.get_doc("BOM Template RIGPL", bom_tmp_name)
        query = (
            """SELECT idx, name, operation, workstation, hour_rate, time_based_on_formula, time_in_mins,
        operation_time_formula, batch_size_based_on_formula, batch_size_formula FROM `tabBOM Operation` WHERE
        parenttype = 'BOM Template RIGPL' AND parent = '%s'"""
            % bt_doc.name
        )
        routing_dict = frappe.db.sql(query, as_dict=1)
        if self.routing:
            self.get_routing()
            if self.get("__islocal") != 1:
                rm_item_dict = get_req_sizes_from_template(
                    bom_tmp_name,
                    item_list,
                    "rm_restrictions",
                    allow_zero_rol=1,
                    ps_name=self.name,
                )
                if not rm_item_dict:
                    frappe.throw("NO RM Found")
                calculate_batch_size(self, routing_dict, fg_it_doc, rm_item_dict)
                calculate_operation_time(self, routing_dict, fg_it_doc, rm_item_dict)
                calculate_operation_cost(self)
                update_warehouse_from_bt(self)

    def get_routing(self):
        self.set("operations", [])
        for d in frappe.get_all(
            "BOM Operation",
            fields=["*"],
            filters={"parenttype": "BOM Template RIGPL", "parent": self.bom_template},
            order_by="idx",
        ):
            child = self.append(
                "operations",
                {
                    "operation": d.operation,
                    "workstation": d.workstation,
                    "description": d.description,
                    "time_in_mins": d.time_in_mins,
                    "batch_size": d.batch_size,
                    "operating_cost": d.operating_cost,
                    "time_based_on_formula": 0,
                    "batch_size_based_on_formula": 0,
                    "hour_rate": d.hour_rate,
                    "allow_consumption_of_rm": d.allow_consumption_of_rm,
                    "rm_warehouse": d.rm_warehouse,
                    "allow_production_of_wip_materials": d.allow_production_of_wip_materials,
                    "wip_material_warehouse": d.wip_material_warehouse,
                    "source_warehouse": d.source_warehouse,
                    "target_warehouse": d.target_warehouse,
                    "transfer_entry": d.transfer_entry,
                    "final_operation": d.final_operation,
                    "final_warehouse": d.final_warehouse,
                    "idx": d.idx,
                },
            )
            if d.final_warehouse:
                self.fg_warehouse = d.final_warehouse

    def get_item_list(self, item_name, known_type, unknown_type):
        it_list = []
        it_dict = frappe._dict({})
        it_dict["known_item"] = item_name
        it_dict[item_name] = known_type
        it_dict["unknown_type"] = unknown_type
        it_list.append(it_dict.copy())
        return it_list

    def validate_no_of_raw_material_items(self, bt_doc):
        if self.rm_consumed:
            for bt_op in bt_doc.operations:
                if bt_op.allow_consumption_of_rm == 1 and not bt_op.rm_warehouse:
                    frappe.throw(
                        "For {} in Row# {} Raw Material Warehouse is Not Mentioned get it "
                        "corrected to Proceed.".format(
                            frappe.get_desk_link("BOM Template RIGPL", bt_doc.name),
                            bt_op.idx,
                        ),
                        "Error: BOM Template Error",
                    )
            if len(self.rm_consumed) != bt_doc.no_of_rm_items:
                frappe.throw(
                    "For {} No of Allowed RM Items = {} but Selected RM = {}".format(
                        frappe.get_desk_link("BOM Template RIGPL", bt_doc.name),
                        bt_doc.no_of_rm_items,
                        len(self.rm_consumed),
                    ),
                    "Error: No of RM Selected is Wrong",
                )

    def make_rm_item_dict(self):
        rm_item_dict = []
        for d in self.rm_consumed:
            rm_dict = {}
            rm_dict["name"] = d.item_code
            rm_dict["description"] = d.description
            rm_item_dict.append(rm_dict.copy())
        return rm_item_dict


def return_priority_psd(psd, itd):
    if itd.p_to_order == 1:
        priority = get_priority_for_so(
            it_name=itd.name,
            prd_qty=psd.quantity,
            short_qty=psd.quantity,
            so_detail=psd.sales_order_item,
        )
    else:
        qty_dict = get_quantities_for_item(itd)
        prd_qty = psd.quantity
        soqty, poqty, pqty = (
            qty_dict["on_so"],
            qty_dict["on_po"],
            qty_dict["planned_qty"],
        )
        fqty, res_prd_qty, wipqty = (
            qty_dict["finished_qty"],
            qty_dict["reserved_for_prd"],
            qty_dict["wip_qty"],
        )
        dead_qty = qty_dict["dead_qty"]
        if soqty > 0:
            if soqty > fqty + dead_qty:
                # SO Qty is Greater than Finished Stock
                shortage = soqty - fqty - dead_qty
                if shortage > wipqty + poqty:
                    # Shortage of Material is More than WIP Qty
                    shortage -= wipqty + poqty
                    priority = get_priority_for_so(
                        it_name=itd.name, prd_qty=prd_qty, short_qty=shortage
                    )
                else:
                    # Shortage is Less than Items in Production now get shortage for the Job Card First
                    priority = get_priority_for_stock_prd(
                        it_name=itd.name, qty_dict=qty_dict
                    )
            else:
                # Qty in Production is for Stock Only
                priority = get_priority_for_stock_prd(
                    it_name=itd.name, qty_dict=qty_dict
                )
        else:
            # No Order for Item, For Stock Production Priority
            priority = get_priority_for_stock_prd(it_name=itd.name, qty_dict=qty_dict)
    return priority


def update_priority_psd(psd, itd, backend=0):
    priority = return_priority_psd(psd, itd)
    old_priority = psd.priority
    if old_priority != priority:
        if backend == 1:
            print(f"Updated Priority for {psd.name} from {old_priority} to {priority}")
            frappe.db.set_value("Process Sheet", psd.name, "priority", priority)
        else:
            psd.priority = priority
