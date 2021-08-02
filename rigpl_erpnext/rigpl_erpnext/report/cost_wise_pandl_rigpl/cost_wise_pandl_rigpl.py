# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from erpnext.accounts.report.financial_statements import get_period_list, get_columns, get_data
from ....utils.finance_utils import *

def execute(filters=None):
    data = []
    data_dict = []
    cc_cols = []
    period_list = get_period_list(filters.from_fy, filters.to_fy, filters.periodicity,
        accumulated_values=0, company=filters.company)
    cc_list= frappe.db.sql("""SELECT name FROM `tabCost Center` WHERE is_group=0""", as_dict=1)
    columns = get_columns(filters.periodicity, period_list, company=filters.company)
    for pd in period_list:
        inc_map = get_income_in_period_cc_wise(frm_dt=pd.from_date, to_dt=pd.to_date,
            company=filters.company)
        for d in inc_map:
            data_dict.append(d.copy())
        dexp_map = get_expense_in_period_cc_wise(frm_dt=pd.from_date, to_dt=pd.to_date,
            company=filters.company, exp_type="Direct")
        for d in dexp_map:
            data_dict.append(d.copy())
        iexp_map = get_expense_in_period_cc_wise(frm_dt=pd.from_date, to_dt=pd.to_date,
            company=filters.company, exp_type="Indirect")
        for d in iexp_map:
            data_dict.append(d.copy())
        depexp_map = get_expense_in_period_cc_wise(frm_dt=pd.from_date, to_dt=pd.to_date,
            company=filters.company, exp_type="Depreciation")
        for d in depexp_map:
            data_dict.append(d.copy())
        texp_map = get_expense_in_period_cc_wise(frm_dt=pd.from_date, to_dt=pd.to_date,
            company=filters.company, exp_type="Tax")
        for d in texp_map:
            data_dict.append(d.copy())
        cc_cols = get_cost_center_columns(data_map=inc_map, cc_list=cc_list, cc_cols=cc_cols)
        cc_cols = get_cost_center_columns(data_map=dexp_map, cc_list=cc_list, cc_cols=cc_cols)
        cc_cols = get_cost_center_columns(data_map=iexp_map, cc_list=cc_list, cc_cols=cc_cols)
        cc_cols = get_cost_center_columns(data_map=depexp_map, cc_list=cc_list, cc_cols=cc_cols)
        cc_cols = get_cost_center_columns(data_map=texp_map, cc_list=cc_list, cc_cols=cc_cols)
        for cc in cc_cols:
            for pd in period_list:
                columns.append({
                        "fieldname": pd.key + " " + cc,
                        "label": pd.label + " " + cc,
                        "fieldtype": "Currency",
                        "options": "currency",
                        "width": 150
                        })
    # for typ in pl_types:
    for row in data_dict:
        if int(row.total) != 0:
            d_row = [row.account, row.root_type, row.currency, int(row.total)]
            for cc in cc_cols:
                if row.get(cc, None):
                    d_row.append(int(row[cc]))
                else:
                    d_row.append(0)
            data.append(d_row)
    return columns, data

def get_columns(periodicity, period_list, accumulated_values=0, company=None):
    columns = [{
        "fieldname": "account",
        "label": ("Account"),
        "fieldtype": "Link",
        "options": "Account",
        "width": 300
    },
        {
        "fieldname": "root_type",
        "label": ("Root Type"),
        "width": 120
    }]
    if company:
        columns.append({
            "fieldname": "currency",
            "label": ("Currency"),
            "fieldtype": "Link",
            "options": "Currency",
            "hidden": 1
        })
    for period in period_list:
        columns.append({
            "fieldname": period.key,
            "label": period.label + " Total",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 150
        })
    if periodicity!="Yearly":
        if not accumulated_values:
            columns.append({
                "fieldname": "total",
                "label": "Total",
                "fieldtype": "Currency",
                "width": 150
            })

    return columns


def get_cost_center_columns(data_map, cc_list, cc_cols):
    if data_map:
        for row in data_map:
            for cc in cc_list:
                if row.get(cc.name, None) and cc.name not in cc_cols:
                    cc_cols.append(cc.name)
    return cc_cols
