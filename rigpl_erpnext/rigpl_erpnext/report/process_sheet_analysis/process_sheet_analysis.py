# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt


def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data


def get_columns(filters):
    if filters.get("process_wise") == 1:
        columns = [
            "Process Sheet:Link/Process Sheet:100", "Status::80", "Priority:Int:50",
            "Item:Link/Item:120",
            "Operation::120", "Op Plan Qty:Int:50", "Op Comp Qty:Int:50", "Balance:Int:50",
            "Description::500",
            "OP Status::100", "RM Consume:Int:50", "PS Pending:Int:50", "PS Date:Date:80",
            "BT:Link/BOM Template RIGPL:120", "Source::120", "Target::120"
        ]
    elif filters.get("pending") == 1:
        columns = [
            "Process Sheet:Link/Process Sheet:100", "PS Date:Date:90", "Status::80",
            "Priority:Int:50", "Item:Link/Item:120",
            "BM::60", "TT::60", "SPL::60", "Series::40",
            "D1:Float:50", "W1:Float:50", "L1:Float:50", "D2:Float:50", "L2:Float:50", "Qty:Int:50",
            "Comp Qty:Int:50", "Pending Qty:Int:50", "BT:Link/BOM Template RIGPL:80",
            "SO#:Link/Sales Order:200", "Description::500", "Created On:Date:150"
        ]
    elif filters.get("rm_used") == 1:
        columns = [
            "PS#:Link/Process Sheet:120", "PS Date:Date:80", "RM:Link/Item:150",
            "RM Description::300", "Calc Qty:Float:100", "Qty Used:Float:100",
            "Balance Needed:Float:100",
            "From WH:Link/Warehouse:150", "Production Item:Link/Item:150",
            "Prod Item Desc::300", "For Prod Qty:Float:100", "Qty Produced:Float:100"
        ]
    else:
        columns = [
            "Process Sheet:Link/Process Sheet:100", "Status::80", "Priority:Int:50",
            "Item:Link/Item:120",
            "BM::60", "TT::60", "SPL::60", "Series::40",
            "D1:Float:50", "W1:Float:50", "L1:Float:50", "D2:Float:50", "L2:Float:50", "Qty:Int:50",
            "Comp Qty:Int:50", "SC Qty:Int:50", "BT:Link/BOM Template RIGPL:80",
            "SO#:Link/Sales Order:200", "Description::500", "Created On:Date:150"
        ]
    return columns


def get_data(filters):
    conditions_it, conditions_ps = get_conditions(filters)
    if filters.get("process_wise") == 1:
        query = """SELECT ps.name, ps.status, ps.priority, ps.production_item, pso.operation,
         pso.planned_qty,
        pso.completed_qty, IF ((pso.planned_qty - pso.completed_qty > 0) AND (pso.status NOT IN
        ('Short Closed', 'Stopped', 'Obsolete')), pso.planned_qty - pso.completed_qty, 0) ,
        ps.description, pso.status, pso.allow_consumption_of_rm,
        IF(ps.quantity - ps.produced_qty > 0, ps.quantity - ps.produced_qty, 0), ps.date,
        ps.bom_template,
        pso.source_warehouse, pso.target_warehouse
        FROM `tabProcess Sheet` ps, `tabBOM Operation` pso
        WHERE pso.parent = ps.name AND pso.parenttype = 'Process Sheet'
        AND ps.docstatus != 2 %s ORDER BY ps.name, pso.idx""" % conditions_it
    elif filters.get("rm_used") == 1:
        query = f"""SELECT ps.name, ps.status, ps.priority, ps.production_item, ps.date,
        rm.item_code as rm_item, rm.source_warehouse, rm.calculated_qty, rm.qty,
        (rm.calculated_qty - rm.qty) as bal_qty, rm.description as rm_desc,
        ps.description as prod_desc, ps.quantity as prod_qty, ps.produced_qty
        FROM `tabProcess Sheet` ps, `tabProcess Sheet Items` rm
        WHERE ps.docstatus = 1 AND ps.status NOT IN ('Short Closed', 'Stopped', 'Completed')
        AND rm.parent = ps.name AND rm.parenttype = 'Process Sheet'
        AND rm.parentfield = 'rm_consumed' AND rm.donot_consider_rm_for_production = 0
        AND rm.qty < rm.calculated_qty AND rm.item_code = '{filters.get("item")}'"""

    elif filters.get("pending") == 1:
        query = """SELECT ps.name, ps.date, ps.status, ps.priority, ps.production_item,
        bm.attribute_value AS bm,
        tt.attribute_value AS tt, spl.attribute_value as spl, ser.attribute_value as series,
        d1.attribute_value as d1,
        w1.attribute_value as w1, l1.attribute_value as l1, d2.attribute_value as d2,
        l2.attribute_value as l2,
        ps.quantity, IF(ps.produced_qty=0, NULL,ps.produced_qty) as prod_qty,
        (ps.quantity - ps.produced_qty) as pend_qty, ps.bom_template, ps.sales_order,
         ps.description, ps.creation
        FROM `tabProcess Sheet` ps
        LEFT JOIN `tabItem` it ON it.name = ps.production_item
        LEFT JOIN `tabItem Variant Attribute` bm ON it.name = bm.parent
            AND bm.attribute = 'Base Material'
        LEFT JOIN `tabItem Variant Attribute` tt ON it.name = tt.parent
            AND tt.attribute = 'Tool Type'
        LEFT JOIN `tabItem Variant Attribute` spl ON it.name = spl.parent
            AND spl.attribute = 'Special Treatment'
        LEFT JOIN `tabItem Variant Attribute` ser ON it.name = ser.parent
            AND ser.attribute = 'Series'
        LEFT JOIN `tabItem Variant Attribute` d1 ON it.name = d1.parent
            AND d1.attribute = 'd1_mm'
        LEFT JOIN `tabItem Variant Attribute` w1 ON it.name = w1.parent
            AND w1.attribute = 'w1_mm'
        LEFT JOIN `tabItem Variant Attribute` l1 ON it.name = l1.parent
            AND l1.attribute = 'l1_mm'
        LEFT JOIN `tabItem Variant Attribute` d2 ON it.name = d2.parent
            AND d2.attribute = 'd2_mm'
        LEFT JOIN `tabItem Variant Attribute` l2 ON it.name = l2.parent
            AND l2.attribute = 'l2_mm'
        WHERE ps.docstatus = 1 AND ps.produced_qty < ps.quantity AND ps.status NOT IN
        ('Stopped', 'Completed', 'Short Closed') %s
        ORDER BY ps.priority, bm.attribute_value, tt.attribute_value, spl.attribute_value,
        ser.attribute_value,
        d1.attribute_value, w1.attribute_value, l1.attribute_value, d2.attribute_value,
        l2.attribute_value,
        ps.production_item, ps.sales_order, ps.description""" % conditions_it
    else:
        query = """SELECT ps.name, ps.status, ps.priority, ps.production_item,
        bm.attribute_value AS bm,
        tt.attribute_value AS tt, spl.attribute_value as spl, ser.attribute_value as series,
        d1.attribute_value as d1,
        w1.attribute_value as w1, l1.attribute_value as l1, d2.attribute_value as d2,
        l2.attribute_value as l2,
        ps.quantity, IF(ps.produced_qty=0, NULL,ps.produced_qty) as prod_qty, ps.sales_order,
        ps.sales_order_item,
        IF(ps.short_closed_qty=0, NULL, ps.short_closed_qty) as sc_qty, ps.bom_template,
        ps.description, ps.creation
        FROM `tabProcess Sheet` ps
        LEFT JOIN `tabItem` it ON it.name = ps.production_item
        LEFT JOIN `tabItem Variant Attribute` bm ON it.name = bm.parent
            AND bm.attribute = 'Base Material'
        LEFT JOIN `tabItem Variant Attribute` tt ON it.name = tt.parent
            AND tt.attribute = 'Tool Type'
        LEFT JOIN `tabItem Variant Attribute` spl ON it.name = spl.parent
            AND spl.attribute = 'Special Treatment'
        LEFT JOIN `tabItem Variant Attribute` ser ON it.name = ser.parent
            AND ser.attribute = 'Series'
        LEFT JOIN `tabItem Variant Attribute` d1 ON it.name = d1.parent
            AND d1.attribute = 'd1_mm'
        LEFT JOIN `tabItem Variant Attribute` w1 ON it.name = w1.parent
            AND w1.attribute = 'w1_mm'
        LEFT JOIN `tabItem Variant Attribute` l1 ON it.name = l1.parent
            AND l1.attribute = 'l1_mm'
        LEFT JOIN `tabItem Variant Attribute` d2 ON it.name = d2.parent
            AND d2.attribute = 'd2_mm'
        LEFT JOIN `tabItem Variant Attribute` l2 ON it.name = l2.parent
            AND l2.attribute = 'l2_mm'
        WHERE ps.docstatus < 3 %s %s
        ORDER BY ps.priority, bm.attribute_value, tt.attribute_value, spl.attribute_value,
        ser.attribute_value,
        d1.attribute_value, w1.attribute_value, l1.attribute_value, d2.attribute_value,
        l2.attribute_value,
        ps.production_item, ps.sales_order, ps.description""" % (conditions_ps, conditions_it)
    if filters.get("process_wise") == 1:
        data = frappe.db.sql(query, as_list=1)
    elif filters.get("rm_used") == 1:
        temp_data = frappe.db.sql(query, as_dict=1)
        data = []
        for row in temp_data:
            tmp_row = [
                row.name, row.date, row.rm_item, row.rm_desc, row.calculated_qty, row.qty,
                row.bal_qty, row.source_warehouse, row.production_item, row.prod_desc, row.prod_qty,
                row.produced_qty
            ]
            data.append(tmp_row)
    elif filters.get("pending") == 1:
        data = frappe.db.sql(query, as_list=1)
    else:
        temp_data = frappe.db.sql(query, as_dict=1)
        data = []
        for row in temp_data:
            tmp_row = [
                row.name, row.status, row.priority, row.production_item, row.bm, row.tt,
                row.spl, row.series, row.d1, row.w1, row.l1, row.d2, row.l2, row.quantity,
                row.prod_qty, row.sc_qty, row.bom_template, row.sales_order,
                row.description, row.creation
            ]
            data.append(tmp_row)
    return data


def get_conditions(filters):
    conditions_it = ""
    conditions_ps = ""
    check_box = 0

    if filters.get("pending") == 1:
        check_box += 1

    if filters.get("rm_used") == 1:
        check_box += 1
        if not filters.get("item"):
            frappe.throw(f"Please Select the Item Code to Check its Usage as RM")

    if filters.get("process_wise") == 1:
        check_box += 1
        if not filters.get("item"):
            frappe.throw("Item Code is Mandatory to Get Process Wise Details")
        else:
            conditions_it = " and ps.production_item = '%s'" % filters.get("item")
            return conditions_it, conditions_ps

    if check_box > 1:
        frappe.throw("Maximum 1 Checkbox can be Selected")

    if filters.get("status"):
        conditions_ps += " AND ps.status = '%s'" % filters.get("status")
    else:
        conditions_ps += " AND ps.docstatus < 2 AND ps.status != 'Stopped' "\
            "AND ps.status != 'Completed' AND status != 'Short Closed'"

    if filters.get("bm"):
        conditions_it += " AND bm.attribute_value = '%s'" % filters.get("bm")

    if filters.get("tt"):
        conditions_it += " AND tt.attribute_value = '%s'" % filters.get("tt")

    if filters.get("series"):
        conditions_it += " AND ser.attribute_value = '%s'" % filters.get("series")

    if filters.get("spl"):
        conditions_it += " AND spl.attribute_value = '%s'" % filters.get("spl")

    if filters.get("item"):
        conditions_it += " and it.name = '%s'" % filters.get("item")

    if filters.get("so"):
        conditions_it += " and ps.sales_order = '%s'" % filters.get("so")

    return conditions_it, conditions_ps
