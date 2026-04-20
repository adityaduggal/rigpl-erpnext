# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        filters = {}
    
    validate_filters(filters)
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def validate_filters(filters):
    check_box = 0
    if filters.get("pending") == 1: check_box += 1
    if filters.get("rm_used") == 1: check_box += 1
    if filters.get("process_wise") == 1: check_box += 1
    
    if check_box > 1:
        frappe.throw("Maximum 1 Checkbox can be Selected")
    
    if filters.get("rm_used") == 1 and not filters.get("item"):
        frappe.throw("Please Select the Item Code to Check its Usage as RM")
    
    if filters.get("process_wise") == 1 and not filters.get("item"):
        frappe.throw("Item Code is Mandatory to Get Process Wise Details")

def get_columns(filters):
    if filters.get("process_wise") == 1:
        return [
            "Process Sheet:Link/Process Sheet:100", "Status::80", "Priority:Int:50",
            "Item:Link/Item:120", "Operation::120", "Op Plan Qty:Int:50", 
            "Op Comp Qty:Int:50", "Balance:Int:50", "Description::500",
            "OP Status::100", "RM Consume:Int:50", "PS Pending:Int:50", "PS Date:Date:80",
            "BT:Link/BOM Template RIGPL:120", "Source::120", "Target::120"
        ]
    elif filters.get("rm_used") == 1:
        return [
            "PS#:Link/Process Sheet:120", "PS Date:Date:80", "RM:Link/Item:150",
            "RM Description::300", "Calc Qty:Float:100", "Qty Used:Float:100",
            "Balance Needed:Float:100", "From WH:Link/Warehouse:150", 
            "Production Item:Link/Item:150", "Prod Item Desc::300", 
            "For Prod Qty:Float:100", "Qty Produced:Float:100"
        ]
    elif filters.get("pending") == 1:
        return [
            "Process Sheet:Link/Process Sheet:100", "PS Date:Date:90", "Status::80",
            "Priority:Int:50", "Item:Link/Item:120",
            "BM::60", "TT::60", "SPL::60", "Series::40",
            "D1:Float:50", "W1:Float:50", "L1:Float:50", "D2:Float:50", "L2:Float:50", 
            "Qty:Int:50", "Comp Qty:Int:50", "Pending Qty:Int:50", 
            "BT:Link/BOM Template RIGPL:80", "SO#:Link/Sales Order:200", 
            "Description::500", "Created On:Date:150"
        ]
    else:
        return [
            "Process Sheet:Link/Process Sheet:100", "Status::80", "Priority:Int:50",
            "Item:Link/Item:120",
            "BM::60", "TT::60", "SPL::60", "Series::40",
            "D1:Float:50", "W1:Float:50", "L1:Float:50", "D2:Float:50", "L2:Float:50", 
            "Qty:Int:50", "Comp Qty:Int:50", "SC Qty:Int:50", 
            "BT:Link/BOM Template RIGPL:80", "SO#:Link/Sales Order:200", 
            "Description::500", "Created On:Date:150"
        ]

def get_data(filters):
    conditions, params = get_conditions(filters)
    
    if filters.get("process_wise") == 1:
        # Mode 1: Process Wise (Simple Operations)
        query = f"""
            SELECT 
                ps.name, ps.status, ps.priority, ps.production_item, pso.operation,
                pso.planned_qty, pso.completed_qty, 
                IF((pso.planned_qty - pso.completed_qty > 0) AND (pso.status NOT IN ('Short Closed', 'Stopped', 'Obsolete')), pso.planned_qty - pso.completed_qty, 0) as balance,
                ps.description, pso.status as op_status, pso.allow_consumption_of_rm,
                IF(ps.quantity - ps.produced_qty > 0, ps.quantity - ps.produced_qty, 0) as ps_pending, 
                ps.date, ps.bom_template, pso.source_warehouse, pso.target_warehouse
            FROM `tabProcess Sheet` ps
            INNER JOIN `tabBOM Operation` pso ON pso.parent = ps.name AND pso.parenttype = 'Process Sheet'
            WHERE ps.docstatus != 2 {conditions}
            ORDER BY ps.name, pso.idx
        """
        return frappe.db.sql(query, params, as_list=1)

    elif filters.get("rm_used") == 1:
        # Mode 2: RM Used (Simple Consumption)
        query = f"""
            SELECT ps.name, ps.date, rm.item_code as rm_item, rm.description as rm_desc,
            rm.calculated_qty, rm.qty, (rm.calculated_qty - rm.qty) as bal_qty,
            rm.source_warehouse, ps.production_item, ps.description as prod_desc, 
            ps.quantity as prod_qty, ps.produced_qty
            FROM `tabProcess Sheet` ps
            INNER JOIN `tabProcess Sheet Items` rm ON rm.parent = ps.name AND rm.parenttype = 'Process Sheet'
            WHERE ps.docstatus = 1 AND ps.status NOT IN ('Short Closed', 'Stopped', 'Completed')
            AND rm.parentfield = 'rm_consumed' AND rm.donot_consider_rm_for_production = 0
            AND rm.qty < rm.calculated_qty AND rm.item_code = %(item)s {conditions}
        """
        # Note: conditions already includes %(item)s check if provided
        return frappe.db.sql(query, params, as_list=1)

    else:
        # Mode 3 & 4 (BIG JOIN Candidates) - Refactored to Bulk Fetch
        select_fields = "ps.name, ps.status, ps.priority, ps.production_item, ps.quantity, ps.produced_qty, ps.bom_template, ps.sales_order, ps.description, ps.creation, ps.date"
        if not filters.get("pending"):
             select_fields += ", ps.sales_order_item, ps.short_closed_qty"
        
        main_conditions = "WHERE ps.docstatus < 3 "
        if filters.get("pending") == 1:
            main_conditions = "WHERE ps.docstatus = 1 AND ps.produced_qty < ps.quantity AND ps.status NOT IN ('Stopped', 'Completed', 'Short Closed') "
        
        query = f"SELECT {select_fields} FROM `tabProcess Sheet` ps {main_conditions} {conditions}"
        ps_data = frappe.db.sql(query, params, as_dict=1)
        
        if not ps_data:
            return []

        item_codes = [d.production_item for d in ps_data]
        
        # Bulk Fetch Attributes
        attributes = ["Base Material", "Tool Type", "Special Treatment", "Series", "d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm"]
        attr_data = frappe.get_all("Item Variant Attribute",
            filters={"parent": ["in", item_codes], "attribute": ["in", attributes]},
            fields=["parent", "attribute", "attribute_value"]
        )
        
        attr_map = {}
        for a in attr_data:
            if a.parent not in attr_map:
                attr_map[a.parent] = {}
            attr_map[a.parent][a.attribute] = a.attribute_value

        # Build Data Rows
        data = []
        for ps in ps_data:
            attrs = attr_map.get(ps.production_item, {})
            
            if filters.get("pending") == 1:
                # Pending View: [PS, Date, Status, Priority, Item, Attrs..., Qty, Comp Qty, Pend Qty, BT, SO#, Desc, Creation]
                row = [
                    ps.name, ps.date, ps.status, ps.priority, ps.production_item,
                    attrs.get("Base Material", "-"), attrs.get("Tool Type", "-"),
                    attrs.get("Special Treatment", "-"), attrs.get("Series", "-"),
                    flt(attrs.get("d1_mm")), flt(attrs.get("w1_mm")), flt(attrs.get("l1_mm")),
                    flt(attrs.get("d2_mm")), flt(attrs.get("l2_mm")),
                    ps.quantity, (ps.produced_qty if ps.produced_qty else None),
                    (ps.quantity - ps.produced_qty), ps.bom_template, ps.sales_order,
                    ps.description, ps.creation
                ]
            else:
                # Default View: [PS, Status, Priority, Item, Attrs..., Qty, Comp Qty, SC Qty, BT, SO#, Desc, Creation]
                row = [
                    ps.name, ps.status, ps.priority, ps.production_item,
                    attrs.get("Base Material", "-"), attrs.get("Tool Type", "-"),
                    attrs.get("Special Treatment", "-"), attrs.get("Series", "-"),
                    flt(attrs.get("d1_mm")), flt(attrs.get("w1_mm")), flt(attrs.get("l1_mm")),
                    flt(attrs.get("d2_mm")), flt(attrs.get("l2_mm")),
                    ps.quantity, (ps.produced_qty if ps.produced_qty else None),
                    (ps.short_closed_qty if ps.short_closed_qty else None),
                    ps.bom_template, ps.sales_order, ps.description, ps.creation
                ]
            data.append(row)

        # Python Sorting with dynamic index offset
        if filters.get("pending") == 1:
            # Shifted by 1 due to Date at index 1
            data.sort(key=lambda r: (
                r[3], # Priority
                str(r[5]), str(r[6]), str(r[7]), str(r[8]), 
                flt(r[9]), flt(r[10]), flt(r[11]), flt(r[12]), flt(r[13]),
                r[4], r[-3]
            ))
        else:
            data.sort(key=lambda r: (
                r[2], # Priority
                str(r[4]), str(r[5]), str(r[6]), str(r[7]), 
                flt(r[8]), flt(r[9]), flt(r[10]), flt(r[11]), flt(r[12]),
                r[3], r[-3]
            ))
        return data

def get_conditions(filters):
    conditions = ""
    params = {}

    if filters.get("process_wise") == 1:
        params["item"] = filters.get("item")
        conditions += " AND ps.production_item = %(item)s "
        return conditions, params

    if filters.get("show_zero_qty") == 1:
        conditions += " AND ps.quantity = 0"
    else:
        conditions += " AND ps.quantity > 0"

    if filters.get("status"):
        conditions += " AND ps.status = %(status)s"
        params["status"] = filters.get("status")
    elif not filters.get("pending"):
        conditions += " AND ps.docstatus < 2 AND ps.status NOT IN ('Stopped', 'Completed', 'Short Closed') "

    # Attribute Filters via EXISTS for performance
    attr_filters = {
        "bm": "Base Material", "tt": "Tool Type", "series": "Series", "spl": "Special Treatment"
    }
    for f_key, attr_name in attr_filters.items():
        if filters.get(f_key):
            p_val = f"f_{f_key}"
            params[f"{p_val}_attr"] = attr_name
            params[f"{p_val}_val"] = filters.get(f_key)
            conditions += f" AND EXISTS (SELECT 1 FROM `tabItem Variant Attribute` WHERE parent = ps.production_item AND attribute = %({p_val}_attr)s AND attribute_value = %({p_val}_val)s)"

    if filters.get("item"):
        conditions += " AND ps.production_item = %(item)s"
        params["item"] = filters.get("item")

    if filters.get("so"):
        conditions += " AND ps.sales_order = %(so)s"
        params["so"] = filters.get("so")

    return conditions, params
