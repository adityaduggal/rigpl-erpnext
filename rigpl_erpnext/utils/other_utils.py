# -*- coding: utf-8 -*-
# Copyright (c) 2017, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import re


def get_weighted_average(list_of_data, avg_key, wt_key):
    """
    Returns average weighted days and total quantity for daywise list of dict
    """
    wt_avg, total_wt = 0, 0
    for entry in list_of_data:
        wt_avg += entry.get(avg_key) * entry.get(wt_key)
        total_wt += entry.get(wt_key)
    if total_wt > 0:
        wt_avg = auto_round_up(wt_avg/total_wt)
    else:
        wt_avg = 0
    return wt_avg, total_wt


def remove_html(html_text):
    cleanr = re.compile(r'<(?!br).*?>')
    cleantext = cleanr.sub('', html_text)
    return cleantext


def validate_ifsc_code(ifsc_code):
    if len(ifsc_code) != 11:
        frappe.throw('Invalid IFSC Length')
    p = re.compile("[0-9A-Z]{4}[0]{1}[0-9A-Z]{6}")
    if not p.match(ifsc_code):
        frappe.throw("Invalid IFSC Code")


def validate_brc_no(brc, ifsc):
    if len(brc) != 20:
        frappe.throw('Invalid BRC Length')
    if brc[:11] != ifsc:
        frappe.msgprint(brc[:11])
        frappe.throw("Invalid BRC Number")
    p = re.compile("[0-9A-Z]{11}[0-9]{9}")
    if not p.match(brc):
        frappe.throw("Invalid BRC Number")


def validate_msme_no(msme_no):
    if len(msme_no) != 12:
        frappe.throw("Invalid MSME No {}, it should be 12 Digits".format(msme_no))

    p = re.compile("[A-Z]{2}[0-9]{2}[A-Z]{1}[0-9]{7}")
    if not p.match(msme_no):
        frappe.throw("MSME No {} does not follow the format AB01C2345678".format(msme_no))


def validate_pan(pan):
    if pan:
        p = re.compile("[A-Z]{5}[0-9]{4}[A-Z]{1}")
        if not p.match(pan):
            frappe.throw("Invalid PAN Number {}".format(pan))


def validate_aadhaar(aadhaar):
    if aadhaar:
        p = re.compile("[0-9]{12}")
    if not p.match(aadhaar):
        frappe.throw("Invalid Aadhaar Number")
    aadhaar_check_digit = calcsum(aadhaar[:-1])
    if aadhaar[-1:] != str(aadhaar_check_digit):
        frappe.throw("Invalid Aadhaar Number")


verhoeff_table_d = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0))

verhoeff_table_p = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8))

verhoeff_table_inv = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def calcsum(number):
    """For a given number returns a Verhoeff checksum digit"""
    c = 0
    for i, item in enumerate(reversed(str(number))):
        c = verhoeff_table_d[c][verhoeff_table_p[(i + 1) % 8][int(item)]]
    return verhoeff_table_inv[c]


def round_down(num, divisor):
    return num - (num %divisor)


def round_up(num, divisor):
    return num - (num % divisor) + divisor


def auto_round_down(num):
    if num > 5000:
        return round_down(num, 100)
    elif num > 1000:
        return round_down(num, 50)
    elif num > 500:
        return round_down(num, 25)
    elif num > 100:
        return round_down(num, 10)
    elif num > 50:
        return round_down(num, 5)
    else:
        return round_down(num, 1)


def auto_round_up(num):
    if num > 5000:
        return round_up(num, 100)
    elif num > 1000:
        return round_up(num, 50)
    elif num > 500:
        return round_up(num, 25)
    elif num > 100:
        return round_up(num, 10)
    elif num > 50:
        return round_up(num, 5)
    else:
        return round_up(num, 1)


def get_base_doc(doctype, docname):
    dt = frappe.get_doc(doctype, docname)
    if dt.amended_from:
        return get_base_doc(doctype, dt.amended_from)
    else:
        return docname


def compute_lcm(x,y):
    """
    Returns least common multiple (LCM) of 2 nos
    """
    if x > y:
        greater = x
    else:
        greater = y
    while True:
        if((greater % x == 0) and (greater % y == 0)):
            lcm = greater
            break
        greater += 1
    return lcm
