# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt
from rigpl_erpnext.utils.item_utils import get_desc
from frappe.model.document import Document


class BOMTemplateRIGPL(Document):
    def validate(self):
        if self.item_template:
            it_doc = frappe.get_doc("Item", self.item_template)
            if it_doc.has_variants != 1:
                frappe.throw("{} is not a Template and Only Item Templates are Allowed in {}".format(
                    frappe.get_desk_link("Item", self.item_template), self.name))
            if it_doc.include_item_in_manufacturing != 1:
                frappe.throw("{} is not Allowed for Manufacturing in {}".
                             format(frappe.get_desk_link("Item", self.item_template), self.name))
        self.validate_restriction_rules("rm_restrictions")
        self.validate_restriction_rules("fg_restrictions")
        self.validate_restriction_rules("wip_restrictions")
        self.generate_title()
        if self.routing:
            routing_dict = {}
            if not self.operations:
                routing_doc = frappe.get_doc('Routing', self.routing)
                # This is how you add data in Child table.
                for d in routing_doc.operations:
                    routing_dict["idx"] = d.idx
                    routing_dict["operation"] = d.operation
                    routing_dict["workstation"] = d.workstation
                    routing_dict["description"] = d.description
                    routing_dict["hour_rate"] = d.hour_rate
                    routing_dict["time_in_mins"] = d.time_in_mins
                    routing_dict["batch_size"] = d.batch_size
                    routing_dict["source_warehouse"] = d.source_warehouse
                    routing_dict["target_warehouse"] = d.target_warehouse
                    routing_dict["allow_consumption_of_rm"] = d.allow_consumption_of_rm
                    routing_dict["allow_production_of_wip_materials"] = d.allow_production_of_wip_materials
                    self.append("operations", routing_dict.copy())
        else:
            frappe.throw('Routing is Mandatory for {}'.format(self.name))
        for d in self.operations:
            op_doc = frappe.get_doc("Operation", d.operation)
            if op_doc.is_subcontracting == 1:
                d.target_warehouse = op_doc.sub_contracting_warehouse
            if d.batch_size_based_on_formula == 1 and not d.batch_size_formula:
                frappe.throw("Batch Size Based on Formula but Formula is Missing for Row# {} in Operation Table".format(
                    d.idx))
            if d.time_based_on_formula == 1 and not d.operation_time_formula:
                frappe.throw("Operation Time Based on Formula but Formula is Missing for Row# {}  in Operation "
                             "Table".format(d.idx))
            if d.idx == len(self.operations):
                d.final_operation = 1
            else:
                d.final_operation = 0
            if d.final_operation == 1 and not d.final_warehouse:
                frappe.msgprint("Please set the Final Warehouse in Row# {} of Operations Table for "
                                "Operation {}".format(d.idx, d.operation))

    def validate_restriction_rules(self, table_name):
        if self.get(table_name):
            for d in self.get(table_name):
                d.is_numeric = frappe.get_value("Item Attribute", d.attribute, "numeric_values")
                if d.is_numeric == 1:
                    d.allowed_values = ""
                else:
                    d.rule = ""

    def generate_title(self):
        title = ""
        rule = 0
        for d in self.fg_restrictions:
            if d.is_numeric != 1:
                desc = get_desc(d.attribute, d.allowed_values)
                if d.idx == 1:
                    title += desc
                else:
                    title += " " + desc
            else:
                if rule == 0:
                    title += ", Rules For: " + d.attribute
                    rule = 1
                else:
                    title += ", " + d.attribute
        self.title = title
