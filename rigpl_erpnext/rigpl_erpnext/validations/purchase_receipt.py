# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from ...utils.sales_utils import check_validated_gstin
from ...utils.job_card_utils import get_next_job_card


def validate(doc, method):
    check_validated_gstin(doc.shipping_address)
    check_validated_gstin(doc.supplier_address)
    update_warehouses_for_job_card_items(doc)

    for d in doc.items:
        wh = frappe.get_doc("Warehouse", d.warehouse)
        if wh.warehouse_type == 'Subcontracting':
            frappe.throw("Subcontracted Warehouse is Not Allowed Check Row# {0}".format(d.idx))


def on_submit(doc, method):
    chk = check_subpo(doc, method)
    if chk == 1:
        chk_ste = get_existing_ste(doc, method)
        if chk_ste:
            if len(chk_ste) > 1:
                frappe.throw("More than 1 Stock Entry Exists for the Same GRN. ERROR!!!")
            else:
                name = chk_ste[0][0]
                ste_exist = frappe.get_doc("Stock Entry", name)
                ste_exist.submit()
                frappe.msgprint('Submitted {}'.format(frappe.get_desk_link(ste_exist.doctype, ste_exist.name)))
        else:
            frappe.throw("No Stock Entry Found for this GRN")


def on_cancel(doc, method):
    chk = check_subpo(doc, method)
    if chk == 1:
        chk_ste = get_existing_ste(doc, method)
        if chk_ste:
            if len(chk_ste) > 1:
                frappe.throw("More than 1 Stock Entry Exists for the Same GRN. ERROR!!!")
            else:
                name = chk_ste[0][0]
                ste_exist = frappe.get_doc("Stock Entry", name)
                ste_exist.cancel()
                frappe.msgprint('{0}{1}'.format("Cancelled STE# ", ste_exist.name))
        else:
            frappe.msgprint("No Stock Entry Found for this PO")


def on_update(doc, method):
    chk = check_subpo(doc, method)
    if chk == 1:
        create_ste(doc, method)


def create_ste(doc, method):
    ste_items = get_ste_items(doc, method)
    chk_ste = get_existing_ste(doc, method)
    if chk_ste:
        if len(chk_ste) > 1:
            frappe.throw("More than 1 Stock Entry Exists for the Same GRN. ERROR!!!")
        else:
            ste_name = chk_ste[0][0]
            ste_exist = frappe.get_doc("Stock Entry", ste_name)
            ste_exist.items = []
            for i in ste_items:
                ste_exist.append("items", i)
            ste_exist.posting_date = doc.posting_date
            ste_exist.posting_time = doc.posting_time
            ste_exist.stock_entry_type = "Material Transfer"
            ste_exist.purchase_receipt_no = doc.name
            ste_exist.difference_account = "Stock Adjustment - RIGPL"
            ste_exist.remarks = "Material Transfer Entry for GRN#" + doc.name
            ste_exist.save()
            frappe.msgprint('Updated {}'.format(frappe.get_desk_link(ste_exist.doctype, ste_exist.name)))
    else:
        ste = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Transfer",
            "posting_date": doc.posting_date,
            "posting_time": doc.posting_time,
            "purchase_receipt_no": doc.name,
            "difference_account": "Stock Adjustment - RIGPL",
            "remarks": "Material Transfer Entry for GRN#" + doc.name,
            "items": ste_items
        })
        ste.insert()
        frappe.msgprint('Created {}'.format(frappe.get_desk_link(ste.doctype, ste.name)))


def get_ste_items(doc, method):
    ste_items = []
    source_warehouse = frappe.db.sql("""SELECT name FROM `tabWarehouse` 
    WHERE is_subcontracting_warehouse =1""", as_list=1)
    source_warehouse = source_warehouse[0][0]
    for d in doc.items:
        ste_temp = {}
        po = frappe.get_doc("Purchase Order", d.purchase_order)
        if po.is_subcontracting == 1:
            pod = frappe.get_doc("Purchase Order Item", d.purchase_order_item)
            ste_temp.setdefault("s_warehouse", source_warehouse)
            ste_temp.setdefault("t_warehouse", d.warehouse)
            ste_temp.setdefault("item_code", pod.subcontracted_item)
            item = frappe.get_doc("Item", pod.subcontracted_item)
            if d.stock_uom == item.stock_uom:
                ste_temp.setdefault("qty", d.qty)
            else:
                ste_temp.setdefault("qty", d.conversion_factor)
            ste_items.append(ste_temp)
    return ste_items


def get_existing_ste(doc, method):
    chk_ste = frappe.db.sql("""SELECT ste.name FROM `tabStock Entry` ste WHERE ste.docstatus != 2 
    AND ste.purchase_receipt_no = '%s'""" % doc.name, as_list=1)
    return chk_ste


def update_warehouses_for_job_card_items(doc):
    jc_list = []
    for d in doc.items:
        jc_dict = {}
        if d.purchase_order_item:
            poi = frappe.get_doc("Purchase Order Item", d.purchase_order_item)
            if poi.reference_dt == "Process Job Card RIGPL":
                nxt_jc_list = get_next_job_card(poi.reference_dn)
                if nxt_jc_list:
                    nxt_jc_doc = frappe.get_doc("Process Job Card RIGPL", nxt_jc_list[0][0])
                    if nxt_jc_doc.s_warehouse and d.warehouse != nxt_jc_doc.s_warehouse:
                        d.warehouse = nxt_jc_doc.s_warehouse
        else:
            frappe.throw("PO is Mandatory for Row# {} in {}".format(d.idx, frappe.get_desk_link(doc.doctype, doc.name)))
    return jc_list


def check_subpo(doc, method):
    #Old Sub Contracting PO are based on Work Orders chk=1
    #New Sub Contracting PO are based on Process Job Card RIGPL chk=2
    chk = 0
    for d in doc.items:
        po = frappe.get_doc("Purchase Order", d.purchase_order)
        if po.is_subcontracting == 1:
            chk = 1
    return chk
