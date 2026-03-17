# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from time import time
from datetime import datetime, date
from ...utils.other_utils import round_down
from frappe.utils.background_jobs import enqueue
from ...utils.item_utils import get_item_attributes

'''
This file would run regularly to update the valuation rate of all the items.
1. Ideally it should run every month but since there is always an error on
change of template then it should run every hour
2. It should check for all item templates and if template == selling and then
check if the template percent is set. If the template percent is set then
check items of that template.
3. Now if item of a template is selling then it would check the whether ther is
Price List rate if there is PL rate then it would check if its default or not.
If there is no default PL then it would take the latest selling price list.
4. If an item template is not for selling then it would check if its purchase
5. If its purchase then the valuation rate would be as per the purchase invoice
    - Here things to note, RM which is not purchased ever should be valued at 1
    - If the RM which is not purchased ever does have valuation rate > 1 then dont change anything. This is so that
    we can set them manually.
    - Also for the Cut Pieces in Carbide RM take the price from RM purchased last
    - Also consider the exchange rate for prices in NON INR (Default currency)
6. It should also check for Items Where they are not part of a template for items
like HSP, CSP, JCNO etc and set the valuation rate.


* Now should I keep the valuation rate doctype or should I enter VR in item code
    - Benefits of keeping the VR doctype is that it would give us the history
    - But History is already there in Stock Ledger Entry Table.
    - So Discard the VR Doctype and update it in Item Code only.
'''

_pi_cache = None
_pl_cache = None

def load_pi_cache():
    global _pi_cache
    if _pi_cache is not None:
        return
    raw = frappe.db.sql('''
        SELECT pid.item_code, pid.base_rate, pi.posting_date 
        FROM `tabPurchase Invoice Item` pid 
        JOIN `tabPurchase Invoice` pi ON pid.parent = pi.name 
        WHERE pi.docstatus = 1 
        ORDER BY pi.posting_date ASC
    ''', as_dict=True)
    _pi_cache = {}
    for r in raw:
        _pi_cache[r.item_code] = r

def load_pl_cache():
    global _pl_cache
    if _pl_cache is not None:
        return
    raw = frappe.db.sql('''
        SELECT item_code, price_list, price_list_rate, creation 
        FROM `tabItem Price`
        ORDER BY creation ASC
    ''', as_dict=True)
    _pl_cache = {}
    for r in raw:
        key = (r.item_code, r.price_list)
        _pl_cache[key] = r


def enqueue_set_valuation_rate():
    enqueue(set_valuation_rate_for_all, queue="long", timeout=1500)


def set_valuation_rate_for_all():
    global _pi_cache, _pl_cache
    _pi_cache = None
    _pl_cache = None
    
    st_time = time()
    temp_list = get_templates()
    for template in temp_list:
        temp_doc = frappe.get_cached_doc("Item", template[0])
        set_valuation_rate_for_template(temp_doc)
    tot_time = int(time() - st_time)
    print(f"Total Time Taken = {tot_time} seconds")


def set_valuation_rate_for_template(temp_doc):
    if temp_doc.is_sales_item == 1:
        if temp_doc.valuation_as_percent_of_default_selling_price > 0:
            selling_item_valuation_rate_template(temp_doc)
        else:
            pass
    elif temp_doc.is_purchase_item == 1:
        purchase_item_valuation_rate_template(temp_doc)


def get_templates():
    temp_list = frappe.db.sql("""SELECT it.name, (SELECT count(name) FROM `tabItem`
    WHERE variant_of = it.name) as variants FROM `tabItem` it WHERE it.has_variants = 1
    ORDER BY variants DESC""", as_list=1)
    return temp_list


def selling_item_valuation_rate_template(template_doc):
    variants = frappe.db.sql("""SELECT name, valuation_rate, valuation_rate_date 
    FROM `tabItem` WHERE variant_of = '%s'
    AND disabled = 0""" % template_doc.name, as_dict=1)
    
    def_pl = get_default_price_list(template_doc)
    if def_pl == "Not Possible":
        print(f"No Default PL found for template {template_doc.name}")
        return

    for item in variants:
        selling_rate_details = get_sp_rate(item.name, def_pl)
        if selling_rate_details:
            it_price, date_of_price = selling_rate_details
            
            vrate = get_valuation_rate(template_doc, it_price)
            set_date = item.valuation_rate_date or date(1900, 1, 1)
            date_of_price_d = date_of_price.date()
            days_diff = (date_of_price_d - set_date).days
            
            update_needed = False
            if days_diff >= 0:
                old_vr = item.valuation_rate or 0
                if old_vr > (1.1 * vrate) or old_vr < (0.9 * vrate):
                    update_needed = True
                elif item.valuation_rate_date != date_of_price_d:
                    update_needed = True
                    
            if update_needed:
                item_doc = frappe.get_doc("Item", item.name)
                update_valuation_rate(item_doc, it_price, template_doc, date_of_price_d)
        else:
            print(f"No Default PL found for item {item.name}")


def purchase_item_valuation_rate_template(temp_doc):
    variants = frappe.db.sql("""SELECT name, valuation_rate, valuation_rate_date 
    FROM `tabItem` WHERE variant_of = '%s'
    AND disabled = 0""" % (temp_doc.name), as_dict=1)
    
    for item in variants:
        pp_rate, pp_date, pinvoice = get_pp_rate_item(item.name)
        if pinvoice == 'Found':
            vrate = get_valuation_rate(temp_doc, pp_rate)
            set_date = item.valuation_rate_date or date(1900, 1, 1)
            days_diff = (pp_date - set_date).days
            
            update_needed = False
            if days_diff >= 0:
                old_vr = item.valuation_rate or 0
                if old_vr > (1.1 * vrate) or old_vr < (0.9 * vrate):
                    update_needed = True
                elif item.valuation_rate_date != pp_date:
                    update_needed = True
            
            if update_needed:
                it_doc = frappe.get_doc("Item", item.name)
                update_valuation_rate(it_doc, pp_rate, temp_doc, pp_date)
        else:
            it_doc = frappe.get_doc("Item", item.name)
            get_sim_variants(it_doc)


def get_sim_variants(it_doc):
    # Find all round Carbide Item Code with diff lengths and Radius 8.2 would
    # also search for items with 8mm dia
    template_doc = frappe.get_cached_doc("Item", it_doc.variant_of)
    attributes = get_item_attributes(it_doc.name)
    check = 0
    base_len = 0
    base_dia = 0
    for att in attributes:
        if att.attribute == 'Base Material' and att.attribute_value == 'Carbide':
            check += 1
        if att.attribute == 'Tool Type' and att.attribute_value == 'Round Tool Bits':
            check += 1
        if check == 2 and att.attribute == 'l1_mm':
            base_len = att.attribute_value
        if check == 2 and att.attribute == 'd1_mm':
            base_dia = att.attribute_value
    if check == 2 and base_dia and base_len:
        if float(base_dia) == int(float(base_dia)):
            base_dia1 = float(base_dia) + 0.2
        elif (float(base_dia) - int(float(base_dia))) < 0.3:
            base_dia1 = int(float(base_dia))
        else:
            base_dia1 = int(float(base_dia)) + 0.2
        similar_variants = []
        for d in [float(base_dia), float(base_dia1)]:
            sim_variants = frappe.db.sql("""SELECT it.name FROM `tabItem` it, `tabItem Variant Attribute` iva
            WHERE it.variant_of = '%s' AND iva.attribute = 'd1_mm' AND iva.attribute_value = %s
            AND iva.parent = it.name""" % (it_doc.variant_of, d), as_list=1)
            similar_variants.extend(sim_variants)
        pp_similar = [{"item_code": it_doc.name, "length": float(base_len),
                       "purchase_rate": 0, "purchase_date": conv_str_to_date('1900-01-01')}]
        for items in similar_variants:
            att_dict = get_item_attributes(items[0])
            att_len = get_specific_attribute(att_dict, "l1_mm")
            att_pp_rate, att_pp_date, pi_found = get_pp_rate_item(items[0])
            pp_similar_dict = {"item_code": items[0], "length": float(att_len), "purchase_rate": float(att_pp_rate),
                               "purchase_date": att_pp_date}

            pp_similar.append(pp_similar_dict.copy())

        if [x for x in pp_similar if x['length'] > float(base_len)]:
            latest_rate_details = max([x for x in pp_similar if x['length'] > float(base_len)],
                                      key=lambda x: x['purchase_date'])
        else:
            latest_rate_details = []
        if latest_rate_details:
            if latest_rate_details.get("purchase_date") > conv_str_to_date('1900-01-01'):
                pur_date = latest_rate_details.get("purchase_date")
                val_rate_cut_pc = latest_rate_details.get("purchase_rate") * float(base_len) / latest_rate_details.get(
                    "length")
                factor = get_cut_pcs_factor(base_len, latest_rate_details.get("length"))
                val_rate_cut_pc = val_rate_cut_pc * factor
                update_valuation_rate(it_doc, val_rate_cut_pc, template_doc, pur_date)
            else:
                print(f"No Purchase Data Found for {it_doc.name} or for similar items even")
        else:
            print(f"No Purchase Data for Items with Higher Length Found for Item Code: {it_doc.name}")
    else:
        print(f"No Purchase Data found for Item {it_doc.name}")


def get_cut_pcs_factor(base_len, higher_length):
    ratio = float(base_len) / float(higher_length)
    if ratio > 0.9:
        factor = 1
    elif ratio > 0.5:
        factor = 0.9
    elif ratio > 0.3:
        factor = 0.8
    else:
        factor = 0.7
    return factor


def conv_str_to_date(string_date):
    if isinstance(string_date, str):
        return datetime.strptime(string_date, "%Y-%m-%d").date()
    # It might already be a date object
    return string_date


def get_pp_rate_item(item_code):
    global _pi_cache
    if _pi_cache is None:
        load_pi_cache()
    
    val = _pi_cache.get(item_code)
    if val:
        return val.base_rate, val.posting_date, 'Found'
    return 0, conv_str_to_date('1900-01-01'), 'Not Found'


def get_specific_attribute(attributes_dict, att_name):
    for att in attributes_dict:
        if att.attribute == att_name:
            return att.attribute_value
    return 0


def update_valuation_rate(it_doc, itpr, t_doc, date_of_price):
    vrate = get_valuation_rate(t_doc, itpr)
    if it_doc.valuation_rate_date:
        set_date = it_doc.valuation_rate_date
    else:
        set_date = date(1900, 1, 1)
    days_diff = (date_of_price - set_date).days
    if days_diff >= 0:
        old_vr = it_doc.valuation_rate or 0
        if old_vr > (1.1 * vrate) or old_vr < (0.9 * vrate):
            it_doc.valuation_rate = vrate
            it_doc.valuation_rate_date = date_of_price
            it_doc.save()
            frappe.db.commit()
            print("Saved Item Code: " + it_doc.name +
                  " Changed Valuation Rate to " + str(it_doc.valuation_rate))
        elif it_doc.valuation_rate_date != date_of_price:
            it_doc.valuation_rate_date = date_of_price
            it_doc.save()
            frappe.db.commit()
            print("Saved Item Code: " + it_doc.name +
                  " Changed Valuation Rate Date to " + str(date_of_price))


def update_std_valuation_rate(it_doc):
    old_vr = it_doc.valuation_rate or 0
    if old_vr > 1:
        pass
    else:
        it_doc.valuation_rate = 1
        it_doc.save()
        frappe.db.commit()
        print("Saved Item Code: " + it_doc.name +
              " Changed Valuation Rate to 1")


def get_default_price_list(template_doc):
    def_pl = ""
    if len(template_doc.item_defaults) == 1:
        for item_def_table in template_doc.item_defaults:
            def_pl = item_def_table.default_price_list
    else:
        def_pl = "Not Possible"
    return def_pl


def get_sp_rate(item, price_list):
    global _pl_cache
    if _pl_cache is None:
        load_pl_cache()
    val = _pl_cache.get((item, price_list))
    if val:
        return val.price_list_rate, val.creation
    return None


def get_valuation_rate(t_doc, itpr):
    if t_doc.is_sales_item == 1:
        calc_rate = t_doc.valuation_as_percent_of_default_selling_price * itpr * 0.01
    elif t_doc.is_purchase_item == 1:
        calc_rate = itpr
    else:
        calc_rate = 0

    if calc_rate < 100:
        val_rate = round_down(calc_rate, 1)
    elif calc_rate < 500:
        val_rate = round_down(calc_rate, 5)
    elif calc_rate < 1000:
        val_rate = round_down(calc_rate, 10)
    elif calc_rate < 5000:
        val_rate = round_down(calc_rate, 50)
    else:
        val_rate = round_down(calc_rate, 100)
    return val_rate
