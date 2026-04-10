# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, getdate

def execute(filters=None):
    if not filters:
        filters = {}
        
    validate_filters(filters)
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def validate_filters(filters):
    no_of_checks = 0
    if filters.get("summary"): no_of_checks += 1
    if filters.get("production_planning"): no_of_checks += 1
    if filters.get("order_wise_summary"): no_of_checks += 1
    if filters.get("op_time_analysis"): no_of_checks += 1
    if filters.get("mach_eff"): no_of_checks += 1
    
    if no_of_checks == 0:
        frappe.throw("One checkbox is needed to be checked")
    elif no_of_checks > 1:
        frappe.throw("Only 1 checkbox should be checked")
        
    if filters.get("op_time_analysis") and not filters.get("operation"):
        frappe.throw("For Operation Time Analysis Operation is Mandatory")
    
    if filters.get("mach_eff") and not filters.get("mach_eff_type"):
        frappe.throw("For Machine Efficiency Select Total or Daily in Type of Report")

def get_columns(filters):
    if filters.get("summary") == 1:
        return [
            "Employee Name::150", "Workstation:Link/Workstation:150", "Item Code:Link/Item:100",
            "Description::300", "Planned Qty:Float:100", "Completed Qty:Float:100",
            "Rejected Qty:Float:100", "Operation::200", "Total Time (mins):Float:80",
            "Time Per Pc:Float:80", "JC#:Link/Process Job Card RIGPL:100",
        ]
    elif filters.get("production_planning") == 1:
        return [
            {"label": "JC#", "fieldname": "name", "fieldtype": "Link", "options": "Process Job Card RIGPL", "width": 100},
            "Status::60", "RM Status:Percent:50", "RM Shortage:Int:80", "SO#:Link/Sales Order:150",
            "Item:Link/Item:120", "Priority:Int:50", "Remarks::100", "BM::60", "TT::60", "SPL::60",
            "Series::60", "D1:Float:50", "W1:Float:50", "L1:Float:50", "D2:Float:50", "L2:Float:50",
            "Description::400", "Operation:Link/Operation:100", "Allocated Machine:Link/Workstation:150",
            "Total Planned:Float:80", "Planned Qty:Float:80", "Qty Avail:Float:80", "Creation:Datetime:120",
        ]
    elif filters.get("order_wise_summary") == 1:
        return [
            "SO#:Link/Sales Order:150", "SO Date:Date:80", "Item:Link/Item:120",
            "Description::450", "Pending:Float:60", "Ordered:Float:60", "JC#:Link/Process Job Card RIGPL:80",
            "PS#::150", "Status::60", "Operation:Link/Operation:100", "Priority:Int:50",
            "Planned Qty:Float:80", "Qty Avail:Float:80", "Remarks::400",
        ]
    elif filters.get("op_time_analysis") == 1:
        return [
            "Posting Date:Date:80", "Employee Name::150", "Workstation:Link/Workstation:150",
            "Item Code:Link/Item:100", "BM::60", "TT::60", "Series::60",
            "D1:Float:50", "W1:Float:50", "L1:Float:50", "D2:Float:50", "L2:Float:50",
            "Planned Qty:Float:100", "Completed Qty:Float:100", "Rejected Qty:Float:100",
            "Operation::200", "Total Time (mins):Float:80", "Time Per Pc:Float:80",
            "Cost Per Pc:Currency:100", "JC#:Link/Process Job Card RIGPL:100", "Description::300",
        ]
    elif filters.get("mach_eff") == 1:
        if filters.get("mach_eff_type") == "Total":
            return [
                "Workstation:Link/Workstation:150", "Total Days:Int:80", "Total Hours:Int:100",
                "Hours Worked:Float:100", "Efficiency:Percent:100", "Disabled:Int:50",
            ]
        else:
            return [
                "Workstation:Link/Workstation:150", "Date:Date:80", "Total Hours:Int:100",
                "Hours Worked:Float:100", "Efficiency:Percent:100", "Disabled:Int:50",
            ]

def get_data(filters):
    cond_jc, params = get_conditions(filters)
    
    if filters.get("summary") == 1:
        query = f"""
            SELECT jc.employee_name, jc.workstation, jc.production_item, jc.description,
            jc.for_quantity, jc.total_completed_qty, jc.total_rejected_qty, jc.operation, jc.total_time_in_mins,
            ROUND((jc.total_time_in_mins/ (jc.total_completed_qty + jc.total_rejected_qty)),2), jc.name
            FROM `tabProcess Job Card RIGPL` jc WHERE jc.docstatus = 1 {cond_jc}
            ORDER BY jc.workstation, jc.production_item
        """
        return frappe.db.sql(query, params, as_list=1)

    elif filters.get("production_planning") == 1:
        query = f"""
            SELECT jc.name, jc.status, jc.rm_status, jc.rm_shortage, jc.sales_order,
            jc.production_item as item, jc.priority, jc.remarks, jc.description, jc.operation,
            jc.workstation, jc.total_qty, jc.for_quantity, jc.qty_available,
            jc.sales_order_item, jc.creation, jc.operation_serial_no
            FROM `tabProcess Job Card RIGPL` jc
            WHERE jc.docstatus = 0 AND jc.status NOT IN ('Completed', 'Cancelled') {cond_jc}
        """
        jc_data = frappe.db.sql(query, params, as_dict=1)
        if not jc_data: return []
        
        # Bulk Fetch Attributes
        attr_map = get_attribute_map([d.item for d in jc_data])
        
        # Sort the dictionary list FIRST before flattening into the final array
        # This avoids lambda scoping issues and ensures stable sort across all attributes
        jc_data.sort(key=lambda d: (
            d.priority or 9999, 
            d.operation_serial_no or 0, 
            attr_map.get(d.item, {}).get("Base Material", "-"),
            attr_map.get(d.item, {}).get("Tool Type", "-"),
            attr_map.get(d.item, {}).get("Special Treatment", "-"),
            attr_map.get(d.item, {}).get("Series", "-"),
            flt(attr_map.get(d.item, {}).get("d1_mm")),
            flt(attr_map.get(d.item, {}).get("w1_mm")),
            flt(attr_map.get(d.item, {}).get("l1_mm"))
        ))
        
        data = []
        for d in jc_data:
            attrs = attr_map.get(d.item, {})
            data.append([
                d.name, d.status, d.rm_status, d.rm_shortage, (d.sales_order or "X"),
                d.item, (d.priority or None), (d.remarks or "X"),
                attrs.get("Base Material", "-"), attrs.get("Tool Type", "-"), 
                attrs.get("Special Treatment", "-"), attrs.get("Series", "-"),
                flt(attrs.get("d1_mm")), flt(attrs.get("w1_mm")), flt(attrs.get("l1_mm")),
                flt(attrs.get("d2_mm")), flt(attrs.get("l2_mm")),
                d.description, d.operation, d.workstation, d.total_qty, d.for_quantity,
                (d.qty_available if d.qty_available != 0 else None), d.creation
            ])
        
        return data

    elif filters.get("order_wise_summary") == 1:
        query = f"""
            SELECT so.name, so.transaction_date, soi.item_code, soi.description,
            (soi.qty - ifnull(soi.delivered_qty, 0)) as pend_qty, soi.qty, soi.name as so_item
            FROM `tabSales Order` so
            INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
            INNER JOIN `tabItem` it ON it.name = soi.item_code
            WHERE so.docstatus = 1 AND (soi.qty - ifnull(soi.delivered_qty, 0)) > 0
            AND so.status != "Closed" AND it.made_to_order = 1 {cond_jc}
            ORDER BY so.transaction_date, so.name, soi.item_code
        """
        # Note: cond_jc here maps to Sales Order conditions
        so_data = frappe.db.sql(query, params, as_dict=1)
        if not so_data: return []
        
        return get_optimized_so_summary(so_data)

    elif filters.get("op_time_analysis") == 1:
        query = f"""
            SELECT jc.posting_date, jc.employee_name, jc.workstation, jc.production_item,
            jc.for_quantity, jc.total_completed_qty, jc.total_rejected_qty, jc.operation, jc.total_time_in_mins,
            ROUND((jc.total_time_in_mins/ (jc.total_completed_qty + jc.total_rejected_qty)),2) as time_per_pc,
            ROUND((jc.total_time_in_mins/ (jc.total_completed_qty + jc.total_rejected_qty) * ws.hour_rate / 60), 2) as cost_per_pc,
            jc.name, jc.description
            FROM `tabProcess Job Card RIGPL` jc
            INNER JOIN `tabWorkstation` ws ON ws.name = jc.workstation
            INNER JOIN `tabJob Card Time Log` tlog ON tlog.parent = jc.name AND tlog.parenttype = 'Process Job Card RIGPL'
            WHERE jc.docstatus = 1 AND tlog.from_time IS NOT NULL AND tlog.to_time IS NOT NULL {cond_jc}
            GROUP BY jc.name
        """
        jc_data = frappe.db.sql(query, params, as_dict=1)
        if not jc_data: return []
        
        attr_map = get_attribute_map([d.production_item for d in jc_data])
        
        data = []
        for d in jc_data:
            attrs = attr_map.get(d.production_item, {})
            data.append([
                d.posting_date, d.employee_name, d.workstation, d.production_item,
                attrs.get("Base Material", "-"), attrs.get("Tool Type", "-"), attrs.get("Series", "-"),
                flt(attrs.get("d1_mm")), flt(attrs.get("w1_mm")), flt(attrs.get("l1_mm")),
                flt(attrs.get("d2_mm")), flt(attrs.get("l2_mm")),
                d.for_quantity, d.total_completed_qty, d.total_rejected_qty, d.operation,
                d.total_time_in_mins, d.time_per_pc, d.cost_per_pc, d.name, d.description
            ])
        data.sort(key=lambda x: (x[0], x[2], x[3]))
        return data

    elif filters.get("mach_eff") == 1:
        return get_optimized_mach_eff(filters, cond_jc, params)

def get_attribute_map(item_codes):
    if not item_codes: return {}
    attributes = ["Base Material", "Tool Type", "Special Treatment", "Series", "d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm"]
    attr_data = frappe.get_all("Item Variant Attribute",
        filters={"parent": ["in", list(set(item_codes))], "attribute": ["in", attributes]},
        fields=["parent", "attribute", "attribute_value"]
    )
    res = {}
    for a in attr_data:
        if a.parent not in res: res[a.parent] = {}
        res[a.parent][a.attribute] = a.attribute_value
    return res

def get_optimized_so_summary(so_data):
    so_item_ids = [d.so_item for d in so_data]
    
    # 1. Bulk Fetch Process Sheets
    ps_data = frappe.get_all("Process Sheet",
        filters={"sales_order_item": ["in", so_item_ids], "docstatus": ["!=", 2]},
        fields=["name", "sales_order_item"],
        order_by="creation"
    )
    ps_map = {}
    for p in ps_data:
        if p.sales_order_item not in ps_map: ps_map[p.sales_order_item] = []
        ps_map[p.sales_order_item].append(p.name)
    
    # 2. Bulk Fetch ALL Job Cards with BOM Operation IDX
    jc_data = frappe.db.sql("""
        SELECT jc.name, jc.status, jc.operation, jc.priority, jc.for_quantity, jc.qty_available,
        jc.docstatus, jc.process_sheet, bmop.idx, jc.total_completed_qty, jc.sales_order_item,
        jc.remarks as jc_remarks
        FROM `tabProcess Job Card RIGPL` jc
        INNER JOIN `tabBOM Operation` bmop ON bmop.parent = jc.process_sheet AND bmop.operation = jc.operation
        WHERE jc.docstatus < 2 AND jc.sales_order_item IN %s
    """, (tuple(so_item_ids),), as_dict=1)
    
    # Group and sort Job Cards per SO Item
    jc_group = {}
    all_jc_names = []
    for jc in jc_data:
        soi = jc.sales_order_item
        if soi not in jc_group: jc_group[soi] = []
        jc_group[soi].append(jc)
        all_jc_names.append(jc.name)
        
    for soi in jc_group:
        jc_group[soi].sort(key=lambda x: x.idx or 0)

    # 3. Bulk Fetch Subcontracting Operations
    subcon_ops = frappe.get_all("Operation", filters={"is_subcontracting": 1}, pluck="name")

    # 4. Bulk Fetch PO Details for potential Subcontracting Job Cards
    po_map = {}
    if all_jc_names:
        po_details = frappe.db.sql("""
            SELECT po.name, po.transaction_date, poi.stock_qty, poi.received_qty, poi.reference_dn
            FROM `tabPurchase Order` po
            INNER JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
            WHERE po.docstatus = 1 AND poi.reference_dt = 'Process Job Card RIGPL'
            AND poi.reference_dn IN %s
        """, (tuple(all_jc_names),), as_dict=1)
        for po in po_details:
            if po.reference_dn not in po_map: po_map[po.reference_dn] = []
            po_map[po.reference_dn].append(po)

    # 5. Assemble Data using Original Python Logic
    data = []
    for so in so_data:
        ps_names = ps_map.get(so.so_item, [])
        ps_links = "\n".join([f'<a href="#Form/Process Sheet/{n}" target="_blank">{n}</a>' for n in ps_names])
        
        # Replicating get_last_jc_for_so logic sequentially in memory
        jc_list = jc_group.get(so.so_item, [])
        final_jc = frappe._dict()
        final_remarks = "Not in Production"
        
        if jc_list:
            for i in range(len(jc_list)):
                current_jc = jc_list[i]
                current_jc.remarks = ""
                
                if current_jc.docstatus == 1:
                    if i == len(jc_list) - 1:
                        current_jc.remarks += f" All Operations Completed {current_jc.total_completed_qty} Qty Ready for Dispatch"
                        final_jc = current_jc
                        final_remarks = current_jc.remarks
                    else:
                        # Subcontracting PO check
                        if current_jc.operation in subcon_ops:
                            linked_pos = po_map.get(current_jc.name, [])
                            po_found_and_pending = False
                            for po in linked_pos:
                                if po.stock_qty > po.received_qty:
                                    po_link = f'<a href="#Form/Purchase Order/{po.name}" target="_blank">{po.name}</a>'
                                    current_jc.remarks += f" PO# {po_link} Pending Qty= {po.stock_qty - po.received_qty} PO Date: {po.transaction_date}"
                                    final_jc = current_jc
                                    final_remarks = current_jc.remarks
                                    po_found_and_pending = True
                                    break
                            if po_found_and_pending:
                                break # Returns this JC immediately
                        final_jc = current_jc
                        # Fallback to the original Job Card's remarks if no logic override applies
                        final_remarks = current_jc.jc_remarks if current_jc.jc_remarks else ""
                else:
                    if i == 0:
                        current_jc.remarks += "Taken into Production but First Process is Pending"
                    else:
                        current_jc.remarks += f" {current_jc.operation} Pending and {jc_list[i - 1].operation} Completed"
                    final_jc = current_jc
                    final_remarks = current_jc.remarks
                    break # Returns this JC immediately

        data.append([
            so.name, so.transaction_date, so.item_code, so.description,
            so.pend_qty, so.qty, (final_jc.get("name", "")), ps_links, (final_jc.get("status", "NO JC")),
            (final_jc.get("operation", "")), (final_jc.get("priority", 0)), (final_jc.get("for_quantity", 0)),
            (final_jc.get("qty_available", 0)), final_remarks
        ])
    return data

def get_optimized_mach_eff(filters, cond_jc, params):
    days = (getdate(filters.get("to_date")) - getdate(filters.get("from_date"))).days + 1
    tot_hrs = days * 24
    
    group_by = "" if filters.get("mach_eff_type") == "Total" else ", jc.posting_date"
    
    # Bulk Fetch Machines
    machines = frappe.get_all("Workstation", fields=["name", "disabled"])
    
    # Bulk Fetch Worked Minutes
    query = f"""
        SELECT jc.workstation, SUM(jc.total_time_in_mins) as tot_mins, jc.posting_date
        FROM `tabProcess Job Card RIGPL` jc
        WHERE jc.docstatus = 1 AND jc.total_time_in_mins > 0 {cond_jc}
        GROUP BY jc.workstation {group_by}
        ORDER BY jc.workstation
    """
    dt = frappe.db.sql(query, params, as_dict=1)
    
    # Map for O(1) matching
    worked_map = {}
    for d in dt:
        if d.workstation not in worked_map: worked_map[d.workstation] = []
        worked_map[d.workstation].append(d)
        
    data = []
    daily_mode = filters.get("mach_eff_type") != "Total"
    
    for mc in machines:
        worked_entries = worked_map.get(mc.name, [])
        if not worked_entries:
            if not daily_mode:
                data.append([mc.name, days, tot_hrs, 0, 0, mc.disabled])
            else:
                 data.append([mc.name, filters.get("to_date"), 24, 0, 0, mc.disabled])
            continue
            
        for d in worked_entries:
            worked_hrs = d.tot_mins / 60
            if not daily_mode:
                data.append([d.workstation, days, tot_hrs, worked_hrs, (worked_hrs / tot_hrs * 100), mc.disabled])
            else:
                data.append([d.workstation, d.posting_date, 24, worked_hrs, (worked_hrs / 24 * 100), mc.disabled])
                
    return data

def get_conditions(filters):
    cond_jc = ""
    params = {}
    
    if filters.get("from_date") and (filters.get("summary") or filters.get("op_time_analysis") or filters.get("mach_eff")):
        cond_jc += " AND jc.posting_date >= %(from_date)s"
        params["from_date"] = filters.get("from_date")
    if filters.get("to_date") and (filters.get("summary") or filters.get("op_time_analysis") or filters.get("mach_eff")):
        cond_jc += " AND jc.posting_date <= %(to_date)s"
        params["to_date"] = filters.get("to_date")

    if filters.get("sales_order"):
        cond_jc += " AND jc.sales_order = %(sales_order)s"
        params["sales_order"] = filters.get("sales_order")
        
    if filters.get("jc_status") and not filters.get("op_time_analysis") and not filters.get("mach_eff"):
        cond_jc += " AND jc.status = %(jc_status)s"
        params["jc_status"] = filters.get("jc_status")
        
    if filters.get("operation") and not filters.get("mach_eff"):
        cond_jc += " AND jc.operation = %(operation)s"
        params["operation"] = filters.get("operation")
        
    if filters.get("item"):
        cond_jc += " AND jc.production_item = %(item)s"
        params["item"] = filters.get("item")

    # Secure attribute filtering via EXISTS
    attr_filters = {"bm": "Base Material", "tt": "Tool Type", "spl": "Special Treatment", "series": "Series"}
    for f_key, attr_name in attr_filters.items():
        if filters.get(f_key):
            p_val = f"f_{f_key}"
            params[f"{p_val}_attr"] = attr_name
            params[f"{p_val}_val"] = filters.get(f_key)
            # Find items matching attribute
            cond_jc += f" AND EXISTS (SELECT 1 FROM `tabItem Variant Attribute` WHERE parent = jc.production_item AND attribute = %({p_val}_attr)s AND attribute_value = %({p_val}_val)s)"

    return cond_jc, params
