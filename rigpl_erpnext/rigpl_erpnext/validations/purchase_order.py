#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import nowdate, nowtime, getdate, flt, cint
from frappe.desk.reportview import get_match_cond
from ...manufacturing_rigpl.utils.manufacturing_utils import get_formula_values, calculate_formula_values
from ...utils.item_attribute_utils import chunks, get_attribute_rows
from rohit_common.rohit_common.validations.sales_invoice import check_validated_gstin

from rohit_common.utils.rohit_common_utils import replace_java_chars

JC_DOCTYPE = "Process Job Card RIGPL"
MTO_DOCTYPE = "Made to Order Item Attributes"
JC_FIELDS = ["name", "docstatus", "status", "operation", "production_item", "description", "total_completed_qty"]
ITEM_FIELDS = ["name", "is_job_work", "is_purchase_item", "customs_tariff_number", "description", "stock_uom",
               "variant_of"]


def validate(doc, method):
    template = get_tax_template(doc)
    addresses = get_by_name("Address", [doc.shipping_address, doc.supplier_address, template.from_address],
                            ["name", "state_rigpl", "country", "gstin"])
    update_fields(doc, template)
    data = load_row_data(doc)
    check_subcontracting(doc, data)
    validate_job_cards(doc, data)
    check_gst_rules(doc, template, addresses)
    check_taxes_integrity(doc, template, addresses)
    set_prices_from_attribute_rules(doc, data)
    add_list = [doc.shipping_address, doc.supplier_address]
    for add in add_list:
        check_validated_gstin(add, doc)


def on_submit(doc, method):
    submit_draft_job_cards(doc)


def get_tax_template(doc):
    if not doc.taxes_and_charges:
        frappe.throw(f"Purchase Taxes and Charges Template is Mandatory for PO# {doc.name}")
    return frappe.get_cached_doc("Purchase Taxes and Charges Template", doc.taxes_and_charges)


def get_by_name(doctype, names, fields):
    """Return {name: row} for the given names, in one query per chunk."""
    found = {}
    for chunk in chunks([name for name in names if name]):
        for row in frappe.get_all(doctype, filters={"name": ("in", chunk)}, fields=fields):
            found[row.name] = row
    return found


def load_row_data(doc):
    """Load the Job Cards, Operations and Items of all the PO rows in 3 queries."""
    jc_names = [d.reference_dn for d in doc.items if d.reference_dt == JC_DOCTYPE]
    job_cards = get_by_name(JC_DOCTYPE, jc_names, JC_FIELDS)
    operations = get_by_name("Operation", [jc.operation for jc in job_cards.values()],
                             ["name", "sub_contracting_item_code"])
    item_names = [d.item_code for d in doc.items] + [d.subcontracted_item for d in doc.items] + \
        [op.sub_contracting_item_code for op in operations.values()] + \
        [jc.production_item for jc in job_cards.values()]
    return frappe._dict(job_cards=job_cards, operations=operations,
                        item_map=get_by_name("Item", item_names, ITEM_FIELDS))


def get_item(data, item_name, idx):
    item = data.item_map.get(item_name)
    if not item:
        frappe.throw(f"Item {item_name} in Row# {idx} does not exist")
    return item


def jc_completed_qty(row, stock_uom):
    if row.conversion_factor != 1 or stock_uom != row.uom:
        return row.conversion_factor
    return row.qty


def submit_draft_job_cards(po_doc):
    rows = [d for d in po_doc.items if d.reference_dt == JC_DOCTYPE and d.reference_dn]
    draft_jcs = {jc.name for jc in get_by_name(JC_DOCTYPE, [d.reference_dn for d in rows],
                                               ["name", "docstatus"]).values() if jc.docstatus == 0}
    items = get_by_name("Item", [d.subcontracted_item for d in rows if d.reference_dn in draft_jcs],
                        ["name", "stock_uom"])
    for d in rows:
        if d.reference_dn not in draft_jcs:
            continue
        jc_doc = frappe.get_doc(JC_DOCTYPE, d.reference_dn)
        jc_doc.posting_date = po_doc.transaction_date
        jc_doc.posting_time = nowtime()
        jc_doc.total_completed_qty = jc_completed_qty(d, (items.get(d.subcontracted_item) or {}).get("stock_uom"))
        jc_doc.submit()


def validate_job_cards(po_doc, data):
    rows = [d for d in po_doc.items if d.reference_dn in data.job_cards and d.reference_dt == JC_DOCTYPE]
    submitted = [d.reference_dn for d in rows if data.job_cards[d.reference_dn].docstatus == 1]
    other_pos = get_other_submitted_pos(submitted, po_doc.name)
    for d in rows:
        jc = data.job_cards[d.reference_dn]
        jc_link = frappe.get_desk_link(JC_DOCTYPE, jc.name)
        if jc.docstatus == 2:
            frappe.throw(f"{jc_link} is {jc.status} for Row#{d.idx}")
        elif jc.docstatus == 1:
            if jc.name in other_pos:
                frappe.throw(f"For Row #{d.idx}: {jc_link} is {jc.status} and is already linked to "
                             f"{frappe.get_desk_link(po_doc.doctype, other_pos[jc.name])}")
            stock_uom = (data.item_map.get(d.subcontracted_item) or {}).get("stock_uom")
            po_qty = flt(jc_completed_qty(d, stock_uom))
            if po_qty != flt(jc.total_completed_qty):
                frappe.throw(f"For Row #{d.idx}: {jc_link} is {jc.status} with Completed Qty "
                             f"{flt(jc.total_completed_qty)} but the PO has {po_qty}. Change the PO Qty "
                             f"from {po_qty} to {flt(jc.total_completed_qty)}")


def get_other_submitted_pos(jc_names, po_name):
    """Return {Job Card: PO} for Job Cards linked to a submitted PO other than `po_name`."""
    poi = frappe.qb.DocType("Purchase Order Item")
    po = frappe.qb.DocType("Purchase Order")
    found = {}
    for chunk in chunks(jc_names):
        query = (
            frappe.qb.from_(poi).join(po).on(poi.parent == po.name)
            .select(poi.reference_dn, po.name)
            .where((po.docstatus == 1) & (poi.reference_dt == JC_DOCTYPE) & (poi.reference_dn.isin(chunk)))
        )
        if po_name:
            query = query.where(po.name != po_name)
        for jc_name, other_po in query.run():
            found.setdefault(jc_name, other_po)
    return found


def check_gst_rules(doc, template_doc, addresses):
    ship_state = (addresses.get(doc.shipping_address) or {}).get("state_rigpl")
    supplier_add = addresses.get(doc.supplier_address) or {}
    supplier_state = supplier_add.get("state_rigpl")
    supplier_country = supplier_add.get("country")

    series_template = template_doc.series

    # Check series of Tax with the Series Selected for Invoice
    if series_template != (doc.naming_series or "")[2:4] and series_template != (doc.name or "")[2:4]:
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


def update_fields(doc, template):
    doc.title = doc.supplier
    if getdate(doc.schedule_date) < getdate(nowdate()):
        doc.schedule_date = getdate(nowdate())
        for d in doc.items:
            if getdate(d.schedule_date) < getdate(nowdate()):
                d.schedule_date = getdate(nowdate())
            if d.expected_delivery_date and getdate(d.expected_delivery_date) < getdate(nowdate()):
                d.expected_delivery_date = getdate(nowdate())

    if getdate(doc.transaction_date) < getdate(nowdate()):
        doc.transaction_date = getdate(nowdate())

    doc.letter_head = template.letter_head


def check_taxes_integrity(doc, template, addresses):
    doc.billing_address = template.from_address
    if doc.billing_address not in addresses:
        frappe.throw(f"From Address {template.from_address} of Tax Template {template.name} does not exist")
    doc.company_gstin = addresses[doc.billing_address].gstin
    for tax in doc.taxes:
        for temp in template.taxes:
            if tax.idx == temp.idx:
                if tax.charge_type != temp.charge_type or tax.row_id != temp.row_id or \
                        tax.account_head != temp.account_head or tax.included_in_print_rate \
                        != temp.included_in_print_rate or tax.add_deduct_tax != \
                        temp.add_deduct_tax:
                    frappe.throw("Selected Tax {0}'s table does not match with tax table of PO# {1}. Check Row # "
                                 "{2} or reload Taxes".format(doc.taxes_and_charges, doc.name, tax.idx))


def check_subcontracting(doc, data):
    jc_rows = {}
    for d in doc.items:
        if doc.is_subcontracting == 1:
            set_subcontracting_row(doc, d, data, jc_rows)
        else:
            if d.subcontracted_item:
                frappe.throw(("Subcontracted Item only allowed for Sub Contracting PO. Check Row# {0}. "
                              "This PO is Not a Subcontracting PO check the box to make this PO "
                              "as Subcontracting.").format(d.idx))
            if get_item(data, d.item_code, d.idx).is_purchase_item != 1:
                frappe.throw(("Only Purchase Items are allowed in Item Code for Purchase Orders. "
                              "Check Row # {0}").format(d.idx))
        it_gst = get_item(data, d.item_code, d.idx).customs_tariff_number
        if d.gst_hsn_code != it_gst:
            d.gst_hsn_code = it_gst


def set_subcontracting_row(doc, d, data, jc_rows):
    """Set the item, subcontracted item and description of row `d` from its Job Card and check them.
    `jc_rows` is {Job Card: row idx} of the rows checked before."""
    if d.reference_dt != JC_DOCTYPE or not d.reference_dn:
        frappe.throw(f"For Row# {d.idx} in PO# {doc.name} NO Job Card is Selected")
    if d.reference_dn in jc_rows:
        frappe.throw(f"{d.reference_dn} is Selected in Row# {jc_rows[d.reference_dn]} and Row# {d.idx}")
    jc_rows[d.reference_dn] = d.idx
    jc = data.job_cards.get(d.reference_dn)
    if not jc:
        frappe.throw(f"Job Card {d.reference_dn} in Row# {d.idx} does not exist")
    subcon_it = (data.operations.get(jc.operation) or {}).get("sub_contracting_item_code")
    if not subcon_it:
        frappe.throw(f"Operation {jc.operation} of {frappe.get_desk_link(JC_DOCTYPE, jc.name)} has no Sub "
                     f"Contracting Item Code. Check Row# {d.idx}")
    d.item_code = subcon_it
    if d.so_detail:
        d.subcontracted_item = jc.production_item
        d.description = jc.description
    if not d.subcontracted_item:
        frappe.throw("Subcontracted Item is Mandatory for Subcontracting Purchase Order "
                     "Check Row #{0}".format(d.idx))
    if not d.so_detail:
        d.description = get_item(data, d.subcontracted_item, d.idx).description
    if get_item(data, d.item_code, d.idx).is_job_work != 1:
        frappe.throw(("Only Sub Contracted Items are allowed in Item Code for Sub Contracting PO. "
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


def set_prices_from_attribute_rules(doc, data):
    """Set `price_list_rate` of each subcontracting row from the first attribute Pricing Rule of the
    supplier that matches the attributes of its subcontracted item."""
    if not doc.supplier:
        frappe.throw("Please Select Supplier First in {}".format(doc.name))
    if doc.is_subcontracting != 1:
        return
    rules = get_supplier_attribute_rules(doc.supplier)
    if not rules:
        return
    row_attributes = get_row_attributes(doc, data.item_map)
    rates = {}
    for d in doc.items:
        key = (d.subcontracted_item, d.so_detail or None)
        if key not in rates:
            rates[key] = find_rule_rate(rules, row_attributes[key])
        if rates[key] is not None and d.price_list_rate != rates[key]:
            d.price_list_rate = rates[key]


def find_rule_rate(rules, item_rows):
    for prule in rules:
        if rule_matches(prule.attributes, item_rows):
            return prule.rate
    return None


def rule_matches(rule_rows, item_rows):
    """A rule matches when each of its rows matches: a text row needs the same attribute value, a
    numeric row needs its formula to give 1. A rule with no rows does not match."""
    if not rule_rows:
        return False
    values = {att.attribute: att.attribute_value for att in item_rows}
    for prule_att in rule_rows:
        if prule_att.is_numeric == 1:
            formula_values = get_formula_values(item_rows, prule_att.formula)
            if not formula_values or calculate_formula_values(prule_att.formula, formula_values) != 1:
                return False
        elif prule_att.attribute not in values or values[prule_att.attribute] != prule_att.allowed_values:
            return False
    return True


def get_supplier_attribute_rules(supplier):
    """Return the active buying attribute Pricing Rules of the supplier with their attribute rows,
    highest priority first, in 2 queries."""
    today = nowdate()
    pr = frappe.qb.DocType("Pricing Rule")
    rules = (
        frappe.qb.from_(pr)
        .select(pr.name, pr.rate, pr.priority)
        .where((pr.apply_on == "Attributes") & (pr.buying == 1) & (pr.applicable_for == "Supplier"))
        .where((pr.supplier == supplier) & (pr.disable == 0) & (pr.valid_from <= today))
        .where(pr.valid_upto.isnull() | (pr.valid_upto >= today))
        .run(as_dict=True)
    )
    rules.sort(key=lambda prule: (-cint(prule.priority), prule.name))
    by_name = {}
    for prule in rules:
        prule.attributes = []
        by_name[prule.name] = prule
    ivr = frappe.qb.DocType("Item Variant Restrictions")
    for chunk in chunks(by_name):
        rows = (
            frappe.qb.from_(ivr)
            .select(ivr.parent, ivr.attribute, ivr.is_numeric, ivr.rule, ivr.allowed_values)
            .where((ivr.parent.isin(chunk)) & (ivr.parenttype == "Pricing Rule") & (ivr.parentfield == "attributes"))
            .orderby(ivr.parent)
            .orderby(ivr.idx)
            .run(as_dict=True)
        )
        for row in rows:
            if row.is_numeric == 1:
                row.formula = replace_java_chars(row.rule or "")
            by_name[row.pop("parent")].attributes.append(row)
    return rules


def get_row_attributes(doc, items):
    """Return {(subcontracted item, so_detail): attribute rows} for the PO rows. A row with a Sales Order
    item uses its submitted Made to Order Item Attributes, or the Item attributes for a variant."""
    so_details = [d.so_detail for d in doc.items if d.so_detail]
    mta = frappe.qb.DocType(MTO_DOCTYPE)
    mto = {}
    for chunk in chunks(so_details):
        rows = (
            frappe.qb.from_(mta)
            .select(mta.name, mta.item_code, mta.sales_order_item)
            .where((mta.sales_order_item.isin(chunk)) & (mta.docstatus == 1))
            .orderby(mta.creation)
            .run()
        )
        for name, item_code, so_item in rows:
            mto.setdefault((item_code, so_item), name)
    mto_rows = get_attribute_rows(mto.values(), parenttype=MTO_DOCTYPE)
    item_rows = get_attribute_rows([d.subcontracted_item for d in doc.items
                                    if (d.subcontracted_item, d.so_detail) not in mto])
    row_attributes = {}
    for d in doc.items:
        mto_name = mto.get((d.subcontracted_item, d.so_detail))
        if mto_name:
            row_attributes[(d.subcontracted_item, d.so_detail)] = mto_rows.get(mto_name, [])
            continue
        if d.so_detail and not (items.get(d.subcontracted_item) or {}).get("variant_of"):
            frappe.throw(f"For Row# {d.idx}: no Submitted {MTO_DOCTYPE} for Item {d.subcontracted_item}. "
                         f"Submit the {MTO_DOCTYPE} of the Sales Order Item and try again")
        row_attributes[(d.subcontracted_item, d.so_detail or None)] = item_rows.get(d.subcontracted_item, [])
    return row_attributes
