# Copyright (c) 2013, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from ....utils.lead_time_utils import get_item_lead_time, get_manuf_days_data_for_item
from ....utils.purchase_utils import get_po_data_for_item


def execute(filters=None):
    if not filters:
        filters = {}
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data


def get_columns(filters):
    if filters.get("detail") == 1:
        return [
            "Item:Link/Item:130",
            {
                "label": "Avg Based On",
                "fieldname": "based_on",
                "width": 100
            },
            {
                "label": "Trans #",
                "fieldname": "link_name",
                "fieldtype": "Dynamic Link",
                "options": "based_on",
                "width": 120
            },
            "Trans Date:Date:100",
            "Completed Qty:Float:100", "Min Days:Int:80", "Max Days:Int:80", "Avg Days:Int:80",
            "Trans Weight:Int:80", "Description::450"
        ]
    else:
        return [
                "Item:Link/Item:130", "ROL:Int:60", "Avg Based On::90",
                "# Transactions:Int:80", "Total Qty:Float:80", "Max Days:Int:80",
                "Min Days:Int:80", "Current Lead Time:Int:80", "Calculated Lead Time:Int:80",
                "Lead Time Diff:Int:80",
                "BM::60", "Brand::60", "Quality::60", "TT::130", "SPL::50",
                "D1 MM:Float:50", "W1 MM:Float:50", "L1 MM:Float:60",
                "D2 MM:Float:50", "L2 MM:Float:60",
                "Description::450", "Template:Link/Item:150"
        ]


def get_data(filters):
    data = []
    conditions_it = get_conditions(filters)
    if filters.get("detail") == 1:
        itd = frappe.get_doc("Item", filters.get("item"))
        if itd.include_item_in_manufacturing == 1:
            based_on = "Process Sheet"
            ld_dt = get_manuf_days_data_for_item(itd.name, frm_dt=filters.get("from_date"),
                to_dt=filters.get("to_date"))
        else:
            based_on = "Purchase Order"
            ld_dt = get_po_data_for_item(itd.name, frm_dt=filters.get("from_date"),
                to_dt=filters.get("to_date"))
        for ldt in ld_dt:
            row = [
                itd.name, based_on, ldt.trans_name, ldt.trans_date, ldt.completed_qty, ldt.min_days,
                ldt.max_days, ldt.avg_days, ldt.trans_wt, itd.description
            ]
            data.append(row)
    else:
        query = f"""SELECT it.name,
            IF(ro.warehouse_reorder_level=0,NULL,ro.warehouse_reorder_level) as rol,
            IFNULL(bm.attribute_value, "-") as bm, IFNULL(brand.attribute_value, "-") as brand,
            IFNULL(quality.attribute_value, "-") as qual, IFNULL(tt.attribute_value, "-") as tt,
            IFNULL(spl.attribute_value, "-") as spl, it.lead_time_days as ex_lead,
            CAST(d1.attribute_value AS DECIMAL(8,3)) as d1,
            CAST(w1.attribute_value AS DECIMAL(8,3)) as w1,
            CAST(l1.attribute_value AS DECIMAL(8,3)) as l1,
            CAST(d2.attribute_value AS DECIMAL(8,3)) as d2,
            CAST(l2.attribute_value AS DECIMAL(8,3)) as l2,
            it.description, it.variant_of, it.lead_time_days
            FROM `tabItem` it
            LEFT JOIN `tabItem Reorder` ro ON it.name = ro.parent
            LEFT JOIN `tabItem Variant Attribute` rm ON it.name = rm.parent
                AND rm.attribute = 'Is RM'
            LEFT JOIN `tabItem Variant Attribute` bm ON it.name = bm.parent
                AND bm.attribute = 'Base Material'
            LEFT JOIN `tabItem Variant Attribute` quality ON it.name = quality.parent
                AND quality.attribute = "{filters.get('bm')} Quality"
            LEFT JOIN `tabItem Variant Attribute` brand ON it.name = brand.parent
                AND brand.attribute = 'Brand'
            LEFT JOIN `tabItem Variant Attribute` tt ON it.name = tt.parent
                AND tt.attribute = 'Tool Type'
            LEFT JOIN `tabItem Variant Attribute` spl ON it.name = spl.parent
                AND spl.attribute = 'Special Treatment'
            LEFT JOIN `tabItem Variant Attribute` purpose ON it.name = purpose.parent
                AND purpose.attribute = 'Purpose'
            LEFT JOIN `tabItem Variant Attribute` type ON it.name = type.parent
                AND type.attribute = 'Type Selector'
            LEFT JOIN `tabItem Variant Attribute` mtm ON it.name = mtm.parent
                AND mtm.attribute = 'Material to Machine'
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


            WHERE
                IFNULL(it.end_of_life, '2099-12-31') > CURDATE() {conditions_it}
            ORDER BY
                bm.attribute_value, quality.attribute_value,
                tt.attribute_value, CAST(d1.attribute_value AS DECIMAL(8,3)),
                CAST(w1.attribute_value AS DECIMAL(8,3)),
                CAST(d2.attribute_value AS DECIMAL(8,3)),
                CAST(l2.attribute_value AS DECIMAL(8,3))"""
        it_dict = frappe.db.sql(query, as_dict=1)
        frm_dt = filters.get("from_date")
        to_dt = filters.get("to_date")
        for itm in it_dict:
            calc_dict = get_item_lead_time(item_name=itm.name, frm_dt=frm_dt, to_dt=to_dt)
            itm["no_of_trans"] = calc_dict["no_of_trans"]
            itm["based_on"] = calc_dict["based_on"]
            itm["min_days"] = calc_dict.get("min_days", 0)
            itm["max_days"] = calc_dict.get("max_days", 0)
            itm["total_qty"] = calc_dict.get("total_qty", 0)
            itm["avg_days_wt"] = calc_dict.get("avg_days_wt", 0)
        for row in it_dict:
            row = [
                row.name, row.rol, row.based_on, row.no_of_trans, row.total_qty, row.max_days,
                row.min_days, row.ex_lead,row.avg_days_wt, (row.avg_days_wt - row.ex_lead),
                row.bm, row.brand, row.qual, row.tt,
                row.spl, row.d1, row.w1, row.l1, row.d2, row.l2, row.description, row.variant_of
                   ]
            data.append(row)
    return data


def get_conditions(filters):
    conditions_it = ""

    if filters.get("item"):
        conditions_it += " AND it.name = '%s'" % filters.get("item")

    if filters.get("rm"):
        conditions_it += " AND rm.attribute_value = '%s'" % filters.get("rm")

    if filters.get("bm"):
        conditions_it += " AND bm.attribute_value = '%s'" % filters.get("bm")

    if filters.get("brand"):
        conditions_it += " AND brand.attribute_value = '%s'" % filters.get("brand")

    if filters.get("quality"):
        conditions_it += " AND quality.attribute_value = '%s'" % filters.get("quality")


    if filters.get("tt"):
        conditions_it += " AND tt.attribute_value = '%s'" % filters.get("tt")

    if filters.get("detail") == 1:
        if not filters.get("item"):
            frappe.throw("Please Select Item Code to Get Transaction Wise Details")

    return conditions_it
