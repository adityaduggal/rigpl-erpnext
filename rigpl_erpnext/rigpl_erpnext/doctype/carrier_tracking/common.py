# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Ltd. and contributors
# For license information, please see license.txt


from __future__ import unicode_literals
import frappe
import math
from frappe.utils import flt


def get_shipment_cost(rate_list, tot_wt):
    cost = 0
    min_applicable = 1
    rate_list = sorted(rate_list, key=lambda i:i['min_wt'])
    tot_wt = flt(tot_wt)
    bal_wt = tot_wt
    if rate_list:
        for rate in rate_list:
            min_wt = rate.get('min_wt')
            max_wt = rate.get('max_wt')
            price = rate.get('price')
            wt_ct = rate.get('weight_ct')
            if tot_wt > min_wt:
                min_applicable = 0
                if tot_wt <= max_wt:
                    if max_wt/wt_ct == 1:
                        cost += math.ceil(max_wt/ wt_ct) * price
                        bal_wt = tot_wt - max_wt
                    else:
                        cost += math.ceil(bal_wt / wt_ct) * price
                        bal_wt = 0
                else:
                    bal_wt = tot_wt - max_wt
                    cost += math.ceil(max_wt/wt_ct) * price
            elif tot_wt == min_wt and tot_wt != 0:
                cost += math.ceil(bal_wt/wt_ct) * price
                frappe.msgprint(str(cost) + "TOT == MIN ")
                bal_wt = tot_wt - min_wt
            else:
                if min_applicable == 1:
                    if min_wt != 0:
                        cost += math.ceil(min_wt/wt_ct) * price
                    else:
                        cost += price
                    min_applicable = 0
        return round(cost,2)
    else:
        return cost


def get_rate_list_for_shipment(ct_doc):
    to_add_doc = frappe.get_doc('Address', ct_doc.to_address)
    tpt_doc = frappe.get_doc('Transporters', ct_doc.carrier_name)
    rate_list = []
    if tpt_doc.calculate_cost_from_quote == 1:
        rate_dict = {}
        to_city = to_add_doc.city
        to_state = to_add_doc.state
        to_country = to_add_doc.country
        city = 0
        state = 0
        for row in tpt_doc.quote:
            found = 0
            if row.city:
                if row.city == to_city:
                    city = 1
                    state = 1
                    found = 1
                    rate_dict = get_rate_dict(row)
            elif row.state and not row.city and city == 0:
                if row.state == to_state:
                    state = 1
                    found = 1
                    rate_dict = get_rate_dict(row)
            elif row.country and not row.state and state == 0:
                if row.country == to_country:
                    found = 1
                    rate_dict = get_rate_dict(row)
            if found == 1:
                rate_list.append(rate_dict.copy())
    return rate_list


def get_rate_dict(row_dict):
    rate_dict = {}
    rate_dict["min_wt"] = row_dict.from_weight
    rate_dict["max_wt"] = row_dict.to_weight
    rate_dict["price"] = row_dict.price_per_weight
    rate_dict["weight_ct"] = row_dict.weight_count
    return rate_dict
