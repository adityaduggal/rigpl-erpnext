# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from frappe.utils import nowdate, nowtime
from frappe.desk.reportview import get_match_cond
from ...utils.sales_utils import check_validated_gstin
from rigpl_erpnext.utils.manufacturing_utils import *


def validate(doc, method):
    update_fields(doc, method)
    check_subcontracting(doc, method)
    check_gst_rules(doc, method)
    check_taxes_integrity(doc, method)
    get_pricing_rule_based_on_attributes(doc)
    get_qty_for_purchase(doc, reject=0)
    check_validated_gstin(doc.shipping_address)
    check_validated_gstin(doc.supplier_address)


def on_submit(doc, method):
    # Submit the Linked Job Card
    for d in doc.items:
        if d.reference_dt == 'Process Job Card RIGPL':
            jc_doc = frappe.get_doc(d.reference_dt, d.reference_dn)
            if jc_doc.docstatus == 0:
                jc_doc.posting_date = doc.transaction_date
                jc_doc.posting_time = nowtime()
                jc_doc.total_completed_qty = d.qty
                jc_doc.submit()


def on_cancel(doc, method):
    # Need to Check if JC is to be Submitted on PO Submission or after GRN Submission
    # Update the JC start date to PO Date and Time
    pass


def on_update(doc, method):
    # Check what to be done on Update maybe update the JC Start Time
    pass


def get_qty_for_purchase(doc, reject=0):
    if doc.is_subcontracting != 1:
        for it in doc.items:
            it_doc = frappe.get_doc("Item", it.item_code)


def check_gst_rules(doc, method):
    ship_state = frappe.db.get_value("Address", doc.shipping_address, "state_rigpl")
    template_doc = frappe.get_doc("Purchase Taxes and Charges Template", doc.taxes_and_charges)
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
    doc.title = doc.supplier
    if doc.schedule_date < nowdate():
        doc.schedule_date = nowdate()
        for d in doc.items:
            if d.schedule_date < nowdate():
                d.schedule_date = nowdate()
            if d.expected_delivery_date and d.expected_delivery_date < nowdate():
                d.expected_delivery_date = nowdate()

    if doc.transaction_date < nowdate():
        doc.transaction_date = nowdate()

    letter_head_tax = frappe.db.get_value("Purchase Taxes and Charges Template", doc.taxes_and_charges, "letter_head")
    doc.letter_head = letter_head_tax


def check_taxes_integrity(doc, method):
    template = frappe.get_doc("Purchase Taxes and Charges Template", doc.taxes_and_charges)
    doc.billing_address = template.from_address
    add_doc = frappe.get_doc('Address', doc.billing_address)
    doc.company_gstin = add_doc.gstin
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
        it_doc = frappe.get_doc("Item", d.item_code)
        it_gst = frappe.get_value('Item', d.item_code, 'customs_tariff_number')
        if d.gst_hsn_code != it_gst:
            d.gst_hsn_code = it_gst
        if doc.is_subcontracting == 1:
            jc_doc = frappe.get_doc(d.reference_dt, d.reference_dn)
            subcon_it = frappe.get_value("Operation", jc_doc.operation, "sub_contracting_item_code")
            sub_item = frappe.get_doc("Item", d.subcontracted_item)
            if d.item_code != subcon_it:
                d.item_code = subcon_it
            if d.so_detail:
                d.subcontracted_item = jc_doc.production_item
                d.description = jc_doc.description
            else:
                d.description = sub_item.description
            if d.subcontracted_item is None or d.subcontracted_item == "":
                frappe.throw("Subcontracted Item is Mandatory for Subcontracting Purchase Order "
                             "Check Row #{0}".format(d.idx))
            if it_doc.is_job_work != 1:
                frappe.throw(("Only Sub Contracted Items are allowed in Item Code for Sub Contracting PO. "
                              "Check Row # {0}").format(d.idx))
        else:
            if d.subcontracted_item:
                frappe.throw(("Subcontracted Item only allowed for Sub Contracting PO. Check Row# {0}. "
                              "This PO is Not a Subcontracting PO check the box to make this PO "
                              "as Subcontracting.").format(d.idx))
            if it_doc.is_purchase_item != 1:
                frappe.throw(("Only Purchase Items are allowed in Item Code for Purchase Orders. "
                              "Check Row # {0}").format(d.idx))


@frappe.whitelist()
def get_pending_jc(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql(f"""SELECT DISTINCT(jc.name), ps.sales_order, jc.posting_date,jc.description, 
    it.stock_uom as uom, jc.sales_order_item, jc.s_warehouse, jc.qty_available
    FROM `tabProcess Job Card RIGPL` jc, `tabProcess Sheet` ps, `tabItem` it, `tabOperation` op
    WHERE jc.docstatus = 0 AND jc.status = 'Work In Progress' AND it.name = jc.production_item
    AND jc.operation = op.name AND op.is_subcontracting = 1
    AND jc.process_sheet = ps.name AND (jc.name LIKE %(txt)s or ps.sales_order LIKE %(txt)s) 
    {get_match_cond(doctype)} ORDER BY IF(locate(%(_txt)s, jc.name), 
    locate(%(_txt)s, jc.name), 1) LIMIT %(start)s, %(page_len)s""",
                         {'txt': "%%%s%%" % txt, '_txt': txt.replace("%", ""), 'start': start, 'page_len': page_len, })


@frappe.whitelist()
def get_pending_prd(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""SELECT DISTINCT(wo.name), wo.sales_order, wo.production_order_date,
	wo.item_description FROM `tabWork Order` wo, `tabSales Order` so, `tabSales Order Item` soi 
	WHERE wo.docstatus = 1 AND so.docstatus = 1 AND soi.parent = so.name AND so.status != "Closed" 
	AND soi.qty > soi.delivered_qty AND wo.sales_order = so.name AND (wo.name LIKE %(txt)s OR 
	wo.sales_order LIKE %(txt)s) {mcond} ORDER BY IF(locate(%(_txt)s, wo.name), locate(%(_txt)s, wo.name), 1)
	LIMIT %(start)s, %(page_len)s""".format(**{
		'key': searchfield,
		'mcond': get_match_cond(doctype)
	}), {
		'txt': "%%%s%%" % txt,
		'_txt': txt.replace("%", ""),
		'start': start,
		'page_len': page_len,
	})


def get_pricing_rule_based_on_attributes(doc):
    if not doc.supplier:
        frappe.throw("Please Select Supplier First in {}".format(doc.name))
    supp_prule_dict = get_supplier_pricing_rule(doc.supplier)
    if doc.is_subcontracting == 1:
        for d in doc.items:
            if d.so_detail:
                if d.reference_dt == "Process Job Card RIGPL":
                    ps_dict = frappe.db.sql("""SELECT name FROM `tabProcess Sheet` 
                        WHERE sales_order_item = '%s'"""% d.so_detail, as_dict=1)
                    ps_doc = frappe.get_doc("Process Sheet", ps_dict[0].name)
                    special_item_attr_doc = get_special_item_attribute_doc(d.subcontracted_item, ps_doc.sales_order_item,
                                                                           docstatus=1)
                    item_att_dict = get_special_item_attributes(d.subcontracted_item, special_item_attr_doc[0].name)
            else:
                item_att_dict = get_attributes(d.subcontracted_item)
            if supp_prule_dict:
                for prule in supp_prule_dict:
                    prule_doc = frappe.get_doc("Pricing Rule", prule.name)
                    found = check_prule_for_it_att(prule_doc, item_att_dict)
                    if found == 1:
                        if d.price_list_rate != prule_doc.rate:
                            d.price_list_rate = prule_doc.rate
                            break


def check_prule_for_it_att(prule_doc, it_att_dict):
    found = 0
    total_score = len(prule_doc.attributes)
    match_score = 0
    exit_prule = 0
    for prule_att in prule_doc.attributes:
        if exit_prule == 0:
            if prule_att.is_numeric != 1:
                for att in it_att_dict:
                    if prule_att.attribute == att.attribute:
                        if prule_att.allowed_values == att.attribute_value:
                            match_score += 1
                            break
                        else:
                            exit_prule = 1
            else:
                formula = replace_java_chars(prule_att.rule)
                formula_values = get_formula_values(it_att_dict, formula)
                dont_calculate_formula = 0
                for key in list(formula_values):
                    if key not in formula:
                        dont_calculate_formula = 1
                        break
                    if dont_calculate_formula == 0:
                        calculated_value = calculate_formula_values(formula, formula_values)
                    else:
                        break
                    if calculated_value == 1:
                        match_score += 1
                        break
        if match_score == total_score:
            found = 1
            return found


def get_supplier_pricing_rule(supplier):
    prule_dict = frappe.db.sql("""SELECT name FROM `tabPricing Rule` WHERE apply_on = 'Attributes' AND buying = 1 
    AND applicable_for = 'Supplier' AND supplier = '%s'""" % supplier, as_dict=1)
    return prule_dict
