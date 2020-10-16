# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt
from ...utils.manufacturing_utils import get_bom_template_from_item


def validate(doc, method):
    it_doc = frappe.get_doc("Item", doc.production_item)
    bom_temp = get_bom_template_from_item(it_doc)
    if bom_temp:
        for bt in bom_temp:
            frappe.msgprint("{} already has {}. So make Process Sheet instead of Work Order".
                            format(frappe.get_desk_link(it_doc.doctype, it_doc.name),
                                   frappe.get_desk_link("BOM Template RIGPL", bt)))
        frappe.throw("Not Allowed to Make Work Orders for {}".format(frappe.get_desk_link(it_doc.doctype, it_doc.name)))


@frappe.whitelist()
def add_items_to_purchase_order(source_name, target_doc=None):
    def postprocess(source, target_doc):
        set_missing_values(source, target_doc)

    doclist = get_mapped_doc("Work Order", source_name, {
        "Work Order": {
            "doctype": "Purchase Order",
            "validation": {
                "docstatus": ["=", 1],
                "status": ["!=", "Stopped"]
            }
        },
        "Work Order": {
            "doctype": "Purchase Order Item",
            "field_map": [
                ["production_item", "item_code"],
                ["item_description", "description"],
                ["wip_warehouse", "warehouse"],
                ["sales_order", "prevdoc_docname"]
            ],
            "postprocess": update_item,
            "condition": lambda doc: doc.docstatus == 1
        }
    }, target_doc, postprocess)
    frappe.msgprint(doclist.items)
    return doclist


def update_item(obj, target, source_parent):
    target.conversion_factor = 1
    target.qty = flt(obj.qty)
    target.stock_qty = target.qty


def set_missing_values(source, target_doc):
    target_doc.run_method("set_missing_values")
    target_doc.run_method("calculate_taxes_and_totals")
