# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

from frappe.model.document import Document
from frappe.query_builder.functions import Sum
from frappe.utils import flt, nowdate

from ....utils.sales_utils import get_priority_for_so
from ....utils.stock_utils import get_quantities_for_item, get_stock_ages
from ...utils.job_card_utils import delete_job_card
from ...utils.manufacturing_utils import (
    calculate_batch_size,
    calculate_operation_cost,
    calculate_operation_time,
    calculated_value_from_formula,
    find_item_quantities,
    get_best_rm_bypass,
    get_priority_for_stock_prd,
    get_qty_to_manufacture,
    get_rm_rule_errors,
    rank_rm_rows,
    round_up_qty,
    set_rm_row_costs,
    set_wip_row_quantities,
    update_qty_for_prod_rows,
    update_warehouse_from_bt,
)
from ...utils.process_sheet_utils import *


class ProcessSheet(Document):
    def onload(self):
        # The ages change each day, so a draft shows them as on today, not as on the last save
        if self.docstatus == 0:
            self.set_rm_stock_ages()
            set_rm_row_costs(self.rm_consumed)

    def set_rm_stock_ages(self, rows=None):
        """Sets the oldest and average FIFO stock age (days) of each RM row in its source warehouse."""
        rows = self.rm_consumed if rows is None else rows
        ages = get_stock_ages(
            (rm.item_code, rm.source_warehouse) for rm in rows if rm.source_warehouse
        )
        for rm in rows:
            rm.oldest_stock_age, rm.average_stock_age = ages.get(
                (rm.item_code, rm.source_warehouse), (0, 0)
            )

    def on_submit(self):
        bt_doc = frappe.get_doc("BOM Template RIGPL", self.bom_template)
        template_ops = [op.operation for op in bt_doc.operations]
        update_ps_operations(self, template_ops=template_ops)
        allow_rm_consumption = 0
        for op in self.operations:
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
        update_qty_for_prod_rows(
            [(d.item_code, d.source_warehouse) for d in self.rm_consumed],
            table_name="rm_consumed",
        )
        make_jc_for_process_sheet(self, template_ops=template_ops)

    def on_cancel(self):
        frappe.db.set_value("Process Sheet", self.name, "status", "Cancelled")
        update_planned_qty(self.production_item, self.fg_warehouse)
        update_qty_for_prod_rows(
            [(d.item_code, d.source_warehouse) for d in self.rm_consumed],
            table_name="rm_consumed",
        )
        existing = get_existing_job_cards(
            self.production_item,
            [row.operation for row in self.operations],
            so_detail=self.sales_order_item,
            ps_doc=self,
        )
        jc_names = list(
            dict.fromkeys(jc.name for row in self.operations for jc in existing.get(row.operation, []))
        )
        own_jc = set(
            frappe.get_all(
                "Process Job Card RIGPL",
                filters={"name": ("in", jc_names), "process_sheet": self.name},
                pluck="name",
            )
        ) if jc_names else set()
        # Update the Total Quantity for the existing Job Cards of other Process Sheets.
        # The Job Cards of this sheet are deleted below.
        for name in jc_names:
            if name not in own_jc:
                jcd = frappe.get_doc("Process Job Card RIGPL", name)
                update_job_card_total_qty(jcd)
                jcd.save()
        delete_job_card(self)

    def validate(self):
        itd = frappe.get_doc("Item", self.production_item)
        update_priority_psd(self, itd)
        # Priority and Auto Quantity
        self.update_ps_status()
        self.validate_other_psheet(itd)
        if not self.flags.ignore_mandatory:
            disallow_templates(self, itd)
            self.reset_disabled_template()
            # One template lookup per save: the list gives the template and
            # total_applicable_bom_templates
            bom_templates = get_bom_template_from_item(itd, self.sales_order_item)
            if not self.bom_template:
                bom_tmp_name = bom_templates
            else:
                bom_tmp_name = [self.bom_template]
            if not bom_tmp_name:
                frappe.throw("No BOM Template Found")
            else:
                bom_tmp_doc = frappe.get_doc("BOM Template RIGPL", bom_tmp_name[0])
                self.update_ps_fields(bom_tmp_doc, itd, bom_templates)

    def before_submit(self):
        if frappe.db.get_value("BOM Template RIGPL", self.bom_template, "disabled"):
            frappe.throw(
                f"{frappe.get_desk_link('BOM Template RIGPL', self.bom_template)} is disabled. "
                f"Select another BOM Template to submit {self.name}.",
                title="Disabled BOM Template",
            )
        self.check_best_rm()

    def check_best_rm(self):
        """
        Sets the Best RM Item at submit. An RM that ranks below the best RM is not blocked: the user
        gets a message and the Process Sheet gets a comment for audit (#184).
        """
        self.best_rm_item, self.best_rm_bypassed = None, 0
        bt_doc = frappe.get_doc("BOM Template RIGPL", self.bom_template)
        if not self.rm_consumed or not any(op.allow_consumption_of_rm == 1 for op in bt_doc.operations):
            return
        ranked = self.get_ranked_rm_candidates(bt_doc)
        if not ranked:
            return
        self.best_rm_item = ranked[0].item_code
        bypass = get_best_rm_bypass(self.rm_consumed, ranked)
        if not bypass:
            return
        best, kept = bypass
        self.best_rm_bypassed = 1
        text = (
            f"Best RM not selected: {kept.item_code} (Adjusted RM Cost {flt(kept.adjusted_rm_cost, 2)}) "
            f"was submitted, but {best.item_code} (Adjusted RM Cost {flt(best.adjusted_rm_cost, 2)}) "
            f"is rank 1 for {self.bom_template}."
        )
        frappe.msgprint(text, title="Best RM Not Selected", indicator="orange")
        self.add_comment("Comment", text)

    def reset_disabled_template(self):
        """
        A disabled template is cleared with its operations, RM and WIP rows. The save then picks
        the first active template that matches the item, and makes the rows again.
        """
        if not self.bom_template or not frappe.db.get_value(
            "BOM Template RIGPL", self.bom_template, "disabled"
        ):
            return
        frappe.msgprint(
            f"{frappe.get_desk_link('BOM Template RIGPL', self.bom_template)} is disabled. "
            f"The first active BOM Template for {self.production_item} is selected in its place.",
            title="Disabled BOM Template Changed",
        )
        self.bom_template = None
        self.routing = None
        for table in ("operations", "rm_consumed", "item_manufactured"):
            self.set(table, [])

    def validate_other_psheet(self, it_doc=None):
        if self.production_item:
            if it_doc is None:
                it_doc = frappe.get_doc("Item", self.production_item)
            ps = frappe.qb.DocType("Process Sheet")
            query = (
                frappe.qb.from_(ps)
                .select(ps.name)
                .where(ps.docstatus == 0)
                .where(ps.production_item == self.production_item)
                .where(ps.name != self.name)
            )
            if it_doc.variant_of:
                other_ps = query.run(as_dict=True)
            else:
                if self.sales_order_item:
                    other_ps = query.where(ps.sales_order_item == self.sales_order_item).run(as_dict=True)
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

    @frappe.whitelist()
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
        self.routing = frappe.db.get_value("BOM Template RIGPL", self.bom_template, "routing")
        self.set("rm_consumed", [])
        self.set("item_manufactured", [])

    def update_ps_fields(self, bt_doc, it_doc, bom_templates=None):
        if self.date != nowdate():
            self.date = nowdate()
        if bom_templates is None:
            bom_templates = get_bom_template_from_item(it_doc, self.sales_order_item)
        self.total_applicable_bom_templates = len(bom_templates)
        self.bom_template = bt_doc.name
        if bt_doc.remarks:
            remarks = ", Remarks: " + bt_doc.remarks
        else:
            remarks = ""
        self.bom_template_description = "Title: " + bt_doc.title + remarks
        self.routing = bt_doc.routing
        self.get_routing_from_template(it_doc, bt_doc)
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

        if not self.rm_consumed:
            rm_item_dict = self.get_rm_items_from_template()
        else:
            self.validate_rm_rules(bt_doc)
            rm_item_dict = self.make_rm_item_dict()
        if not rm_item_dict:
            frappe.throw(
                "NO Raw Material Found. Possible Solutions /n"
                "1. Check Box for Show Unavailable Raw Material \n"
                "2. Change Raw Material Warehouse in the Process Sheet \n"
                "3. Change the BOM Template from {}".format(self.bom_template)
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
            self.fill_rm_rows(self.rm_consumed, rm_item_dict)
        else:
            frappe.throw("No RM found as per Rules in BOM Template")
        if wip_list:
            wip_qty_dict = find_item_quantities(wip_list)
            if not self.item_manufactured:
                update_item_table(wip_list, "item_manufactured", self)
            else:
                for wip in self.item_manufactured:
                    if wip_qty_dict:
                        set_wip_row_quantities(wip, wip_qty_dict)
            for op in self.operations:
                if op.allow_production_of_wip_materials == 1:
                    for wip in self.item_manufactured:
                        wip.target_warehouse = op.wip_material_warehouse
                        wip.source_warehouse = ""

    def get_rm_warehouse(self):
        if self.raw_material_source_warehouse:
            return self.raw_material_source_warehouse
        rm_warehouse = ""
        for d in self.operations:
            if d.allow_consumption_of_rm == 1:
                rm_warehouse = d.rm_warehouse
        return rm_warehouse

    def get_rm_items_from_template(self):
        item_list = self.get_item_list(
            self.production_item, known_type="fg", unknown_type="rm"
        )
        return get_req_sizes_from_template(
            bom_temp_name=self.bom_template,
            item_type_list=item_list,
            table_name="rm_restrictions",
            allow_zero_rol=1,
            ps_name=self.name,
        )

    def get_ranked_rm_candidates(self, bt_doc):
        """Returns all RM sizes that the BOM Template allows, as RM rows in rank order. self is not changed."""
        rm_item_dict = self.get_rm_items_from_template()
        rows = [frappe._dict(item_code=d.name, description=d.description) for d in rm_item_dict]
        if rows:
            self.fill_rm_rows(rows, rm_item_dict)
        return rows

    def fill_rm_rows(self, rows, rm_item_dict):
        """
        Sets the source warehouse, stock quantities, Calculated Qty, stock ages and costs of the RM
        rows, and sorts them by rank (rank_rm_rows).
        """
        rm_warehouse = self.get_rm_warehouse()
        for d in rows:
            d.source_warehouse = rm_warehouse
        for d in find_item_quantities(rm_item_dict):
            for rm in rows:
                if d.item_code == rm.item_code and d.warehouse == rm.source_warehouse:
                    rm.target_warehouse = ""
                    rm.uom = d.stock_uom
                    rm.qty = 0
                    rm.qty_available = d.actual_qty
                    rm.current_projected_qty = d.actual_qty - d.prd_qty - d.on_so
                    rm.projected_qty = d.actual_qty - d.prd_qty - d.on_so + d.on_po + d.planned
        rm_calc_qty_list = calculated_value_from_formula(
            rm_item_dict,
            self.production_item,
            fg_qty=self.quantity,
            process_sheet_name=self.name,
            bom_template_name=self.bom_template,
        )
        calc_qty = {rm_calc.rm_item_code: round_up_qty(rm_calc.qty) for rm_calc in rm_calc_qty_list}
        for rm in rows:
            if rm.item_code in calc_qty:
                rm.calculated_qty = calc_qty[rm.item_code]
        rates = dict(frappe.get_all(
            "Item",
            filters={"name": ("in", [rm.item_code for rm in rows])},
            fields=["name", "valuation_rate"],
            as_list=True,
        ))
        # The stock age discount is a part of the rank, so the ages come first
        self.set_rm_stock_ages(rows)
        rank_rm_rows(rows, rates)

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
            vrate = flt(it_doc.valuation_rate)
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
        ps = frappe.qb.DocType("Process Sheet")
        so_sheets = (
            frappe.qb.from_(ps)
            .where(ps.docstatus == 1)
            .where(ps.production_item == soi_doc.item_code)
            .where(ps.sales_order_item == so_detail)
        )
        qty_in_prd = (
            so_sheets.select(Sum(ps.quantity))
            .where(ps.status.notin(["Stopped", "Short Closed"]))
            .run()
        )
        if qty_in_prd:
            qty_in_prd = flt(qty_in_prd[0][0])
        else:
            qty_in_prd = 0
        qty_stopped = (
            so_sheets.select(Sum(ps.produced_qty) - Sum(ps.short_closed_qty))
            .where(ps.status.isin(["Stopped", "Short Closed"]))
            .run()
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

    def get_routing_from_template(self, fg_it_doc=None, bt_doc=None):
        if fg_it_doc is None:
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
        if bt_doc is None or bt_doc.name != bom_tmp_name:
            bt_doc = frappe.get_doc("BOM Template RIGPL", bom_tmp_name)
        bop = frappe.qb.DocType("BOM Operation")
        routing_dict = (
            frappe.qb.from_(bop)
            .select(
                bop.idx, bop.name, bop.operation, bop.workstation, bop.hour_rate,
                bop.time_based_on_formula, bop.time_in_mins, bop.operation_time_formula,
                bop.batch_size_based_on_formula, bop.batch_size_formula,
            )
            .where(bop.parenttype == "BOM Template RIGPL")
            .where(bop.parent == bt_doc.name)
            .run(as_dict=True)
        )
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

    def validate_rm_rules(self, bt_doc):
        """Each RM row must pass the RM rules of the BOM Template. There is no override (#183)."""
        errors = get_rm_rule_errors(bt_doc, self.production_item, self.name, self.rm_consumed)
        if errors:
            frappe.throw(
                "The RM rules of {} do not allow:<br>{}".format(
                    frappe.get_desk_link("BOM Template RIGPL", bt_doc.name),
                    "<br>".join(
                        "Row# {}: {} fails {}".format(row.idx, row.item_code, "; ".join(failures))
                        for row, failures in errors
                    ),
                ),
                title="RM Not Allowed by BOM Template",
            )

    def make_rm_item_dict(self):
        rm_item_dict = []
        for d in self.rm_consumed:
            rm_dict = {}
            rm_dict["name"] = d.item_code
            rm_dict["description"] = d.description
            rm_item_dict.append(rm_dict.copy())
        return rm_item_dict


def return_priority_psd(psd, itd, qty_dict=None, so_lines=None):
    """
    Returns the priority of the Process Sheet. Pass `qty_dict` (get_quantities_for_items) and
    `so_lines` (the item's rows of get_open_so_lines) when checking many sheets.
    """
    if itd.made_to_order == 1:
        priority = get_priority_for_so(
            it_name=itd.name,
            prd_qty=psd.quantity,
            short_qty=psd.quantity,
            so_detail=psd.sales_order_item,
            so_lines=so_lines,
        )
    else:
        if qty_dict is None:
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
                        it_name=itd.name, prd_qty=prd_qty, short_qty=shortage, so_lines=so_lines
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
