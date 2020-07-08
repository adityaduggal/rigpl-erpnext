# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import nowdate, add_days
from frappe.desk.reportview import get_match_cond


def validate(doc, method):
    update_fields(doc, method)
    check_subcontracting(doc, method)
    check_gst_rules(doc, method)
    check_taxes_integrity(doc, method)


def check_gst_rules(doc, method):
    ship_state = frappe.db.get_value("Address", doc.shipping_address, "state_rigpl")
    template_doc = frappe.get_doc("Purchase Taxes and Charges Template", doc.taxes_and_charges)
    ship_country = frappe.db.get_value("Address", doc.shipping_address, "country")
    supplier_state = frappe.db.get_value("Address", doc.supplier_address, "state_rigpl")
    supplier_country = frappe.db.get_value("Address", doc.supplier_address, "country")

    series_template = frappe.db.get_value("Purchase Taxes and Charges Template", doc.taxes_and_charges, "series")

    # Check series of Tax with the Series Selected for Invoice
    if series_template != doc.naming_series[2:4] and series_template != doc.name[2:4]:
        frappe.throw("Selected Tax Template {0} Not Allowed since Series Selected {1} and PO number {2} don't "
                     "match with the Selected Template".format(doc.taxes_and_charges, doc.naming_series, doc.name))

    if doc.taxes_and_charges != 'OGL':
        # Check if Shipping State is Same as Template State then check if the tax template is LOCAL
        # Else if the States are different then the template should NOT BE LOCAL
        # Compare the Ship State with the Tax Template (since Shipping address is our own address)
        # if Ship State is Same as Supplier State then Local else Central or Import
        if ship_state != template_doc.state:
            frappe.throw("Selected Tax template is not for Selected Shipping Address")

        if template_doc.state == supplier_state:
            if template_doc.is_local_purchase != 1 and template_doc.is_import != 1:
                frappe.throw(("Selected Tax {0} is NOT LOCAL Tax but Supplier Address is in Same State {1}, "
                              "hence either change Supplier Address or Change the "
                              "Selected Tax").format(doc.taxes_and_charges, supplier_state))
        elif supplier_country == 'India' and supplier_state != template_doc.state and template_doc.is_import != 1:
            if template_doc.is_local_purchase == 1:
                frappe.throw(("Selected Tax {0} is LOCAL Tax but Supplier Address is in Different State {1}, "
                              "hence either change Supplier Address or Change the "
                              "Selected Tax").format(doc.taxes_and_charges, supplier_state))
        elif supplier_country != 'India':  # Case of IMPORTS
            if template_doc.is_import != 1:
                frappe.throw(("Selected Tax {0} is for Indian Sales but Supplier Address is in Different Country "
                              "{1}, hence either change Supplier Address or Change the Selected "
                              "Tax").format(doc.taxes_and_charges, supplier_country))


def update_fields(doc, method):
    if doc.is_subcontracting == 1:
        doc.transaction_date = add_days(nowdate(), -1)
    else:
        doc.transaction_date = nowdate()

    letter_head_tax = frappe.db.get_value("Purchase Taxes and Charges Template", doc.taxes_and_charges, "letter_head")
    doc.letter_head = letter_head_tax


def check_taxes_integrity(doc, method):
    template = frappe.get_doc("Purchase Taxes and Charges Template", doc.taxes_and_charges)
    for tax in doc.taxes:
        for temp in template.taxes:
            if tax.idx == temp.idx:
                if tax.charge_type != temp.charge_type or tax.row_id != temp.row_id or \
                        tax.account_head != temp.account_head or tax.included_in_print_rate \
                        != temp.included_in_print_rate or tax.add_deduct_tax != \
                        temp.add_deduct_tax:
                    frappe.throw("Selected Tax {0}'s table does not match with tax table of PO# {1}. Check Row # "
                                 "{2} or reload Taxes".format(doc.taxes_and_charges, doc.name, tax.idx))


def check_subcontracting(doc, method):
    for d in doc.items:
        if doc.is_subcontracting != 1:
            if d.subcontracted_item:
                frappe.throw(("Subcontracted Item only allowed for Sub Contracting PO. Check Row# {0}. "
                              "This PO is Not a Subcontracting PO check the box to make this PO "
                              "as Subcontracting.").format(d.idx))
    for d in doc.items:
        item = frappe.get_doc("Item", d.item_code)
        if doc.is_subcontracting == 1:
            if item.is_job_work != 1:
                frappe.throw(("Only Sub Contracted Items are allowed in Item Code for Sub Contracting PO. "
                              "Check Row # {0}").format(d.idx))
        else:
            if item.is_purchase_item != 1:
                frappe.throw(("Only Purchase Items are allowed in Item Code for Purchase Orders. "
                              "Check Row # {0}").format(d.idx))
        if d.so_detail:
            sod = frappe.get_doc("Sales Order Item", d.so_detail)
            if doc.is_subcontracting != 1:
                d.item_code = sod.item_code
            else:
                d.subcontracted_item = sod.item_code
            d.description = sod.description
        if doc.is_subcontracting == 1:
            sub_item = frappe.get_doc("Item", d.subcontracted_item)
            if d.so_detail:
                pass
            else:
                d.description = sub_item.description
            if d.subcontracted_item is None or d.subcontracted_item == "":
                frappe.throw("Subcontracted Item is Mandatory for Subcontracting Purchase Order "
                             "Check Row #{0}".format(d.idx))
            if d.from_warehouse is None or d.from_warehouse == "":
                frappe.throw("From Warehouse is Mandatory for Subcontracting Purchase Order "
                             "Check Row #{0}".format(d.idx))
            check_warehouse(doc, method, d.from_warehouse)


def on_submit(doc, method):
    if doc.is_subcontracting == 1:
        chk_ste = get_existing_ste(doc, method)
        if chk_ste:
            if len(chk_ste) > 1:
                frappe.throw("More than 1 Stock Entry Exists for the Same PO. ERROR!!!")
            else:
                name = chk_ste[0][0]
                ste_exist = frappe.get_doc("Stock Entry", name)
                ste_exist.submit()
                frappe.msgprint('{0}{1}'.format("Submitted STE# ", ste_exist.name))
        else:
            frappe.throw("No Stock Entry Found for this PO")


def on_cancel(doc, method):
    if doc.is_subcontracting == 1:
        chk_ste = get_existing_ste(doc, method)
        if chk_ste:
            if len(chk_ste) > 1:
                frappe.throw("More than 1 Stock Entry Exists for the Same PO. ERROR!!!")
            else:
                name = chk_ste[0][0]
                ste_exist = frappe.get_doc("Stock Entry", name)
                ste_exist.cancel()
                frappe.msgprint('{0}{1}'.format("Cancelled STE# ", ste_exist.name))
        else:
            frappe.msgprint("No Stock Entry Found for this PO")


def on_update(doc, method):
    if doc.is_subcontracting == 1:
        create_ste(doc, method)


def create_ste(doc, method):
    ste_items = get_ste_items(doc, method)
    chk_ste = get_existing_ste(doc, method)
    if chk_ste:
        if len(chk_ste) > 1:
            frappe.throw("More than 1 Stock Entry Exists for the Same PO. ERROR!!!")
        else:
            ste_name = chk_ste[0][0]
            ste_exist = frappe.get_doc("Stock Entry", ste_name)
            ste_exist.items = []
            for i in ste_items:
                ste_exist.append("items", i)
            ste_exist.posting_date = doc.transaction_date
            ste_exist.posting_time = '23:59:59'
            ste_exist.purpose = "Material Transfer"
            ste_exist.purchase_order = doc.name
            ste_exist.remarks = "Material Transfer Entry for PO#" + doc.name
            ste_exist.save()
            frappe.msgprint('{0}{1}'.format("Updated STE# ", ste_exist.name))
    else:
        ste = frappe.get_doc({
            "doctype": "Stock Entry",
            "purpose": "Material Transfer",
            "posting_date": doc.transaction_date,
            "posting_time": '23:59:59',
            "purchase_order": doc.name,
            "remarks": "Material Transfer Entry for PO#" + doc.name,
            "items": ste_items
        })
        ste.insert()
        frappe.msgprint('{0}{1}'.format("Created STE# ", ste.name))


def get_ste_items(doc, method):
    ste_items = []
    target_warehouse = frappe.db.sql("""SELECT name FROM `tabWarehouse` 
    WHERE is_subcontracting_warehouse =1""", as_list=1)
    target_warehouse = target_warehouse[0][0]
    for d in doc.items:
        ste_temp = {}
        ste_temp.setdefault("s_warehouse", d.from_warehouse)
        ste_temp.setdefault("t_warehouse", target_warehouse)
        ste_temp.setdefault("item_code", d.subcontracted_item)
        item = frappe.get_doc("Item", d.subcontracted_item)
        if d.stock_uom == item.stock_uom:
            ste_temp.setdefault("qty", d.qty)
        else:
            ste_temp.setdefault("qty", d.conversion_factor)
        ste_items.append(ste_temp)
    return ste_items


def get_existing_ste(doc, method):
    chk_ste = frappe.db.sql("""SELECT ste.name FROM `tabStock Entry` ste WHERE ste.docstatus != 2 
    AND ste.purchase_order = '%s'""" % doc.name, as_list=1)
    return chk_ste


def check_warehouse(doc, method, wh):
    warehouse = frappe.get_doc("Warehouse", wh)
    if warehouse.is_subcontracting_warehouse == 1:
        frappe.throw("Warehouse {0} is not allowed to be Selected in PO# {1}".format(warehouse.name, doc.name))


def get_pending_prd(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql(f"""SELECT DISTINCT(wo.name), wo.sales_order, wo.production_order_date,wo.item_description
	FROM `tabWork Order` wo, `tabSales Order` so, `tabSales Order Item` soi WHERE wo.docstatus = 1 AND so.docstatus = 1 
	AND soi.parent = so.name AND so.status != "Closed" AND soi.qty > soi.delivered_qty AND wo.sales_order = so.name
	AND (wo.name like %(txt)s or wo.sales_order like %(txt)s) {get_match_cond(doctype)} order by
	if(locate(%(_txt)s, `tabWork Order`.name), locate(%(_txt)s, `tabWork Order`.name), 1)
	limit %(start)s, %(page_len)s""",
                         {'txt': "%%%s%%" % txt, '_txt': txt.replace("%", ""), 'start': start, 'page_len': page_len, })
