# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from datetime import date
from time import time
from typing import Dict, List, Optional, Tuple

import frappe
from frappe.utils import flt
from rohit_common.utils.background_doc_processing import enqueue_once

from ...utils.batch_write_utils import bulk_set_fields
from ...utils.item_attribute_utils import chunks, get_attribute_rows
from ...utils.other_utils import round_down

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



NO_DATE = date(1900, 1, 1)
TEMPLATE_FIELDS = ["name", "is_sales_item", "is_purchase_item",
    "valuation_as_percent_of_default_selling_price"]
VARIANT_FIELDS = ["name", "disabled", "valuation_rate", "valuation_rate_date"]


def enqueue_set_valuation_rate():
    enqueue_once("rigpl_erpnext.rigpl_erpnext.scheduled_tasks.item_valuation_rate.set_valuation_rate_for_all", queue="long", timeout=1500)


def set_valuation_rate_for_all():
    st_time = time()
    templates = frappe.get_all("Item", filters={"has_variants": 1, "disabled": 0},
        fields=TEMPLATE_FIELDS)
    price_lists = get_default_price_lists([t.name for t in templates])
    for template in templates:
        changes = get_template_changes(template, price_lists.get(template.name))
        write_changes(changes)
        frappe.db.commit()
    tot_time = int(time() - st_time)
    print(f"Total Time Taken = {tot_time} seconds")


def get_template_changes(template, def_pl: Optional[str]) -> Dict[str, Tuple]:
    """
    Returns {item: (old values, new values)} for the variants of a template whose valuation
    rate or its date must change, with a fixed number of queries
    """
    if template.is_sales_item == 1:
        if flt(template.valuation_as_percent_of_default_selling_price) > 0:
            return get_selling_changes(template, def_pl)
        return {}
    if template.is_purchase_item == 1:
        return get_purchase_changes(template)
    return {}


def get_variants(template_name):
    return frappe.get_all("Item", filters={"variant_of": template_name}, fields=VARIANT_FIELDS)


def get_selling_changes(template, def_pl):
    variants = [v for v in get_variants(template.name) if not v.disabled]
    if not def_pl:
        for v in variants:
            print(f"No Default PL found for item {v.name}")
        return {}
    prices = get_sp_rates([v.name for v in variants], def_pl)
    changes = {}
    for v in variants:
        if v.name in prices:
            it_price, date_of_price = prices[v.name]
            add_change(changes, v, it_price, template, date_of_price.date())
    return changes


def get_purchase_changes(template):
    variants = get_variants(template.name)
    names = [v.name for v in variants]
    pp_rates = get_pp_rates(names)
    attributes = {
        name: {row.attribute: row.attribute_value for row in rows}
        for name, rows in get_attribute_rows(names).items()
    }
    changes = {}
    for v in variants:
        if v.disabled:
            continue
        if v.name in pp_rates:
            pp_rate, pp_date = pp_rates[v.name]
            add_change(changes, v, pp_rate, template, pp_date)
            continue
        cut_pc = get_cut_pc_rate(v.name, variants, attributes, pp_rates)
        if cut_pc:
            add_change(changes, v, cut_pc[0], template, cut_pc[1])
    return changes


def get_cut_pc_rate(item_name, variants, attributes, pp_rates):
    """
    Returns (rate, purchase date) of a Carbide Round Tool Bit from the latest purchased
    variant of the same template with a longer length and the same or the near diameter
    (8.2 for 8, 8 for 8.2)
    """
    atts = attributes.get(item_name, {})
    if atts.get("Base Material") != "Carbide" or atts.get("Tool Type") != "Round Tool Bits":
        print(f"No Purchase Data found for Item {item_name}")
        return None
    base_len, base_dia = flt(atts.get("l1_mm")), flt(atts.get("d1_mm"))
    if base_dia == int(base_dia):
        base_dia1 = base_dia + 0.2
    elif (base_dia - int(base_dia)) < 0.3:
        base_dia1 = int(base_dia)
    else:
        base_dia1 = int(base_dia) + 0.2
    dias = (round(base_dia, 3), round(base_dia1, 3))
    longer = []
    for v in variants:
        v_atts = attributes.get(v.name, {})
        if "d1_mm" not in v_atts or round(flt(v_atts["d1_mm"]), 3) not in dias:
            continue
        length = flt(v_atts.get("l1_mm"))
        if length > base_len:
            rate, pur_date = pp_rates.get(v.name, (0, NO_DATE))
            longer.append((pur_date, flt(rate), length))
    if not longer:
        print(f"No Purchase Data for Items with Higher Length Found for Item Code: {item_name}")
        return None
    # On the same purchase date, the shortest longer piece is the closest to the cut size
    pur_date, rate, length = max(longer, key=lambda x: (x[0], -x[2]))
    if pur_date <= NO_DATE:
        print(f"No Purchase Data Found for {item_name} or for similar items even")
        return None
    return rate * base_len / length * get_cut_pcs_factor(base_len, length), pur_date


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


def get_pp_rates(item_codes: List[str]) -> Dict[str, Tuple]:
    """
    Returns {item_code: (base_rate, posting_date)} of the latest submitted Purchase Invoice,
    the last created one if more are on the same date
    """
    rates = {}
    for chunk in chunks(item_codes):
        rows = frappe.db.sql("""SELECT pid.item_code, pid.base_rate, pi.posting_date
            FROM `tabPurchase Invoice Item` pid
            JOIN `tabPurchase Invoice` pi ON pi.name = pid.parent
            JOIN (SELECT pid2.item_code, MAX(pi2.posting_date) AS last_date
                FROM `tabPurchase Invoice Item` pid2
                JOIN `tabPurchase Invoice` pi2 ON pi2.name = pid2.parent
                WHERE pid2.item_code IN %(items)s AND pi2.docstatus = 1
                GROUP BY pid2.item_code) last
                ON last.item_code = pid.item_code AND last.last_date = pi.posting_date
            WHERE pi.docstatus = 1
            ORDER BY pi.creation DESC, pid.idx DESC""", {"items": chunk}, as_dict=1)
        for row in rows:
            rates.setdefault(row.item_code, (row.base_rate, row.posting_date))
    return rates


def get_sp_rates(item_codes: List[str], price_list: str) -> Dict[str, Tuple]:
    """
    Returns {item_code: (price_list_rate, creation)} from the Price List
    """
    rates = {}
    for chunk in chunks(item_codes):
        for row in frappe.get_all("Item Price",
                filters={"item_code": ["in", chunk], "price_list": price_list},
                fields=["item_code", "price_list_rate", "creation"], order_by="creation"):
            rates.setdefault(row.item_code, (row.price_list_rate, row.creation))
    return rates


def get_default_price_lists(template_names: List[str]) -> Dict[str, Optional[str]]:
    """
    Returns {template: default price list} for templates with exactly one Item Default row
    """
    rows_by_template = {}
    for chunk in chunks(template_names):
        for row in frappe.get_all("Item Default",
                filters={"parent": ["in", chunk], "parenttype": "Item"},
                fields=["parent", "default_price_list"]):
            rows_by_template.setdefault(row.parent, []).append(row.default_price_list)
    return {name: pls[0] for name, pls in rows_by_template.items() if len(pls) == 1}


def add_change(changes, item, itpr, t_doc, date_of_price):
    new = get_new_valuation(item, itpr, t_doc, date_of_price)
    if new:
        changes[item.name] = (
            {"valuation_rate": item.valuation_rate, "valuation_rate_date": item.valuation_rate_date},
            new,
        )


def get_new_valuation(item, itpr, t_doc, date_of_price) -> Optional[Dict]:
    """
    Returns the new valuation_rate and valuation_rate_date of an item, or None if the price is
    older than the current date or the rate is within 10% and the date is the same
    """
    vrate = get_valuation_rate(t_doc, itpr)
    set_date = item.valuation_rate_date or NO_DATE
    if (date_of_price - set_date).days < 0:
        return None
    if flt(item.valuation_rate) > (1.1 * vrate) or flt(item.valuation_rate) < (0.9 * vrate):
        return {"valuation_rate": vrate, "valuation_rate_date": date_of_price}
    if item.valuation_rate_date != date_of_price:
        return {"valuation_rate": item.valuation_rate, "valuation_rate_date": date_of_price}
    return None


def write_changes(changes: Dict[str, Tuple]):
    bulk_set_fields("Item", {name: new for name, (_old, new) in changes.items()},
        {name: old for name, (old, _new) in changes.items()})
    for name, (old, new) in changes.items():
        if new["valuation_rate"] != old["valuation_rate"]:
            print(f"Saved Item Code: {name} Changed Valuation Rate to {new['valuation_rate']}")
        else:
            print(f"Saved Item Code: {name} Changed Valuation Rate Date to {new['valuation_rate_date']}")


def selling_item_valuation_rate_variant(item_doc, template_doc):
    """
    Updates the valuation rate of one selling variant from its Item Price (Item Price hook)
    """
    def_pl = get_default_price_list(template_doc)
    if not def_pl or def_pl == "Not Possible":
        print(f"No Default PL found for item {item_doc.name}")
        return
    price = get_sp_rates([item_doc.name], def_pl).get(item_doc.name)
    if price:
        changes = {}
        add_change(changes, item_doc, price[0], template_doc, price[1].date())
        write_changes(changes)


def get_default_price_list(template_doc):
    if len(template_doc.item_defaults) == 1:
        return template_doc.item_defaults[0].default_price_list
    return "Not Possible"


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
