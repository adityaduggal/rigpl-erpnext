# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from rigpl_erpnext.utils.item_utils import get_desc, check_text_attributes
from rigpl_erpnext.manufacturing_rigpl.utils.manufacturing_utils import (
    clear_fg_rules_cache,
    group_text_rules,
    split_allowed_values,
)
from frappe.model.document import Document


class BOMTemplateRIGPL(Document):
    def validate(self):
        self.validate_length_oal()
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
        self.validate_rm_map()
        operations = get_operation_details([d.operation for d in self.operations])
        self.validate_operations(operations)
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
            if d.source_warehouse:
                if d.target_warehouse:
                    d.transfer_entry = 1
                else:
                    d.transfer_entry = 0
            else:
                d.transfer_entry = 0

            op_doc = operations.get(d.operation) or get_operation_details([d.operation]).get(d.operation)
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
        self.validate_operation_conditions()
        self.validate_scrap_rules()

    def on_update(self):
        clear_fg_rules_cache()

    def on_trash(self):
        clear_fg_rules_cache()

    def validate_length_oal(self):
        if self.length_formula == 1:
            fg_oal, rm_oal, wip_oal = 0, 0, 0
            for d in self.fg_restrictions:
                if d.renamed_field_name == 'oal':
                    fg_oal += 1
            for d in self.rm_restrictions:
                if d.renamed_field_name == 'oal':
                    rm_oal += 1
            for d in self.wip_restrictions:
                if d.renamed_field_name == 'oal':
                    wip_oal += 1
            if self.fg_restrictions and fg_oal != 1:
                frappe.throw(f"In Finished Restrictions Table 1 Field and Only 1 Field should have OAL as its renamed "
                             f"Field since {self.name} has Length Formula Checked. "
                             f"The Table has {fg_oal} fields marked with oal")
            if self.rm_restrictions and rm_oal != 1:
                frappe.throw(f"In RM Restrictions Table 1 Field and Only 1 Field should have OAL as its renamed "
                             f"Field since {self.name} has Length Formula Checked. "
                             f"The Table has {rm_oal} fields marked with oal")
            if self.wip_restrictions and wip_oal != 1:
                frappe.throw(f"In WIP Restrictions Table 1 Field and Only 1 Field should have OAL as its renamed "
                             f"Field since {self.name} has Length Formula Checked. "
                             f"The Table has {wip_oal} fields marked with oal")

    def validate_restriction_rules(self, table_name):
        if self.get(table_name):
            numeric = dict(frappe.get_all(
                "Item Attribute",
                filters={"name": ("in", list({d.attribute for d in self.get(table_name)}))},
                fields=["name", "numeric_values"],
                as_list=True,
            ))
            att_docs = {}
            for d in self.get(table_name):
                if d.item_number == 0:
                    d.item_number = 1
                d.is_numeric = numeric.get(d.attribute)
                if d.value_source and (d.is_numeric == 1 or table_name == "fg_restrictions"):
                    frappe.throw(f"Row# {d.idx} of {table_name}: "
                                 f"Value Source is only for the non-numeric RM and WIP rules.")
                if d.value_source == "Same as RM" and table_name != "wip_restrictions":
                    frappe.throw(f"Row# {d.idx} of {table_name}: Same as RM is only for the WIP rules.")
                if d.is_numeric == 1:
                    d.allowed_values = ""
                elif d.value_source:
                    d.allowed_values, d.rule = "", ""
                else:
                    if d.attribute not in att_docs:
                        att_docs[d.attribute] = frappe.get_doc("Item Attribute", d.attribute)
                    values = sorted(split_allowed_values(d.allowed_values))
                    for value in values:
                        check_text_attributes(att_doc=att_docs[d.attribute], att_value=value, error=0)
                    d.allowed_values = "\n".join(values)
                    d.rule = ""
            self.validate_value_source_rows(table_name)

    def validate_value_source_rows(self, table_name):
        """
        The rows of the same attribute are joined (OR). An attribute with a Value Source row must
        have only that row, because "the FG value or C-1X" is not a clear rule.
        """
        rows = {}
        for d in self.get(table_name):
            if d.is_numeric != 1:
                rows.setdefault(d.attribute, []).append(d)
        for attribute, att_rows in rows.items():
            if len(att_rows) > 1 and any(d.value_source for d in att_rows):
                frappe.throw(f"{attribute} in {table_name}, rows {', '.join(str(d.idx) for d in att_rows)}: "
                             f"a row with a Value Source must be the only row of its attribute.")

    def validate_rm_map(self):
        """
        Checks the FG to RM Map (#163). The map defines the RM values of its RM attributes, so:
        - 1 row for each FG value and RM attribute, and 1 FG attribute for each RM attribute;
        - an RM attribute of the map has no rows in the RM rules;
        - each FG value that the FG rules allow has a map row.
        """
        att_docs, seen, fg_of_rm = {}, set(), {}
        for d in self.get("fg_rm_map"):
            key = (d.fg_attribute, d.fg_value, d.rm_attribute)
            if key in seen:
                frappe.throw(f"Row# {d.idx} of the FG to RM Map: {d.fg_attribute} = {d.fg_value} "
                             f"for {d.rm_attribute} is already in the table.")
            seen.add(key)
            if fg_of_rm.setdefault(d.rm_attribute, d.fg_attribute) != d.fg_attribute:
                frappe.throw(f"Row# {d.idx} of the FG to RM Map: {d.rm_attribute} is already mapped from "
                             f"{fg_of_rm[d.rm_attribute]}. Use 1 FG attribute for each RM attribute.")
            values = sorted(split_allowed_values(d.rm_values))
            for attribute, check in [(d.fg_attribute, [d.fg_value]), (d.rm_attribute, values)]:
                if attribute not in att_docs:
                    att_docs[attribute] = frappe.get_doc("Item Attribute", attribute)
                for value in check:
                    check_text_attributes(att_doc=att_docs[attribute], att_value=value, error=0)
            d.rm_values = "\n".join(values)
        rm_rule_attributes = {d.attribute for d in self.get("rm_restrictions") if d.is_numeric != 1}
        fg_allowed = group_text_rules(self.get("fg_restrictions"), no_means_any=False)
        for rm_attribute, fg_attribute in fg_of_rm.items():
            if rm_attribute in rm_rule_attributes:
                frappe.throw(f"{rm_attribute} is in the FG to RM Map, so the map defines its RM values. "
                             f"Delete the rows of {rm_attribute} in the Raw Material Restriction table.")
            mapped = {d.fg_value for d in self.get("fg_rm_map") if d.rm_attribute == rm_attribute}
            missing = sorted((fg_allowed.get(fg_attribute) or set()) - mapped)
            if missing:
                frappe.throw(f"The FG rules allow {fg_attribute} = {', '.join(missing)}, but the FG to RM Map "
                             f"has no {rm_attribute} for them. Add the map rows, or no RM is found for these items.")

    def validate_operation_conditions(self):
        """
        Checks the Operation Condition of the operations (#163). The RM operation and the final
        operation cannot have a condition: the RM and the FG warehouse come from them.
        """
        att_docs = {}
        for d in self.operations:
            if not (d.condition_attribute or d.condition_type or (d.condition_values or "").strip()):
                continue
            if not (d.condition_attribute and d.condition_type and split_allowed_values(d.condition_values)):
                frappe.throw(f"Row# {d.idx} of the Operations: set the Condition Attribute, Type and Values, "
                             f"or clear all 3.")
            if d.allow_consumption_of_rm == 1 or d.final_operation == 1:
                frappe.throw(f"Row# {d.idx} of the Operations: {d.operation} consumes the RM or is the final "
                             f"operation, so it cannot have a condition.")
            if d.condition_attribute not in att_docs:
                att_docs[d.condition_attribute] = frappe.get_doc("Item Attribute", d.condition_attribute)
            att_doc = att_docs[d.condition_attribute]
            if att_doc.numeric_values == 1:
                frappe.throw(f"Row# {d.idx} of the Operations: the Condition Attribute {att_doc.name} must not be numeric.")
            values = sorted(split_allowed_values(d.condition_values))
            for value in values:
                check_text_attributes(att_doc=att_doc, att_value=value, error=0)
            d.condition_values = "\n".join(values)

    def validate_scrap_rules(self):
        """An operation with a Scrap Item needs its Scrap Qty Formula and Scrap Warehouse (#164)."""
        for d in self.operations:
            if (d.scrap_item or d.scrap_qty_formula) and not (d.scrap_item and d.scrap_qty_formula and d.scrap_warehouse):
                frappe.throw(f"Row# {d.idx} of the Operations: set the Scrap Item, Scrap Qty Formula and Scrap "
                             f"Warehouse, or clear them.")

    def validate_operations(self, operations):
        for d in self.operations:
            op_doc = operations.get(d.operation) or get_operation_details([d.operation]).get(d.operation)
            if op_doc.is_subcontracting == 1:
                if d.idx == 1:
                    frappe.throw("First Operation Cannot be Sub-Contracting")
                if d.allow_consumption_of_rm == 1:
                    frappe.throw("Sub-Contracting Operation cannot consume Raw Material for Row# {}".format(d.idx))
                if d.idx == len(self.operations):
                    frappe.throw("Sub-Contracting Operation cannot be Last Operation.")

    def generate_title(self):
        """The FG text values, joined for each attribute, then the attributes of the numeric rules."""
        groups = group_text_rules(self.fg_restrictions, no_means_any=False)
        title = " ".join(
            " / ".join(get_desc(attribute, value) or value for value in sorted(values))
            for attribute, values in groups.items()
        )
        rule_attributes = list(dict.fromkeys(d.attribute for d in self.fg_restrictions if d.is_numeric == 1))
        if rule_attributes:
            title += ", Rules For: " + ", ".join(rule_attributes)
        self.title = title


def get_operation_details(operations):
    """
    Returns {operation: {is_subcontracting, sub_contracting_warehouse}} in one query.
    An operation that does not exist stops with the same error as get_doc.
    """
    details = {
        d.name: d
        for d in frappe.get_all(
            "Operation",
            filters={"name": ("in", list(set(operations)))},
            fields=["name", "is_subcontracting", "sub_contracting_warehouse"],
        )
    } if operations else {}
    for operation in operations:
        if operation not in details:
            frappe.get_doc("Operation", operation)
    return details
