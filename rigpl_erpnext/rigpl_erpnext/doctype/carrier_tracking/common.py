# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Ltd. and contributors
# For license information, please see license.txt


from __future__ import unicode_literals
import frappe
from frappe.utils import flt


def get_shipment_cost(rate_list, tot_wt):
    cost = 0
    if rate_list:
        for rate in rate_list:
            if flt(tot_wt) <= rate.get('min_wt'):
                cost += (rate.get('min_wt') * rate.get('price') / rate.get('weight_ct'))
            elif flt(tot_wt) <= rate.get('max_wt'):
                cost += (flt(tot_wt) * rate.get('price') / rate.get('weight_ct'))
            else:
                net_wt = (rate.get('max_wt') - rate.get('min_wt'))
                tot_wt = flt(tot_wt) - net_wt
                cost += (net_wt * rate.get('price') / rate.get('weight_ct'))
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
                    found = 1
                    rate_dict = get_rate_dict(row)
            elif row.state and city == 0:
                if row.state == to_state:
                    state = 1
                    found = 1
                    rate_dict = get_rate_dict(row)
            elif row.country and state == 0:
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
