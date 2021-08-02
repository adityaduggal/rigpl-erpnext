#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
import frappe
from frappe.utils import flt

def get_income_in_period_cc_wise(frm_dt=None, to_dt=None, company=None):
    # Get the Sales or Income in Period based on the CC defined in Item Master
    income_map = []
    def_cc = frappe.get_value("Company", company, "cost_center")
    inc_acc = frappe.db.sql("""SELECT name, is_group, lft, rgt, report_type, root_type
        FROM `tabAccount` WHERE report_type = 'Profit and Loss' AND root_type = 'Income'
        AND is_group = 0 ORDER BY name""", as_dict=1)
    for acc in inc_acc:
        inc_dt = frappe._dict({})
        inc_dt["account"] = acc.name
        inc_dt["root_type"] = acc.root_type
        query = """SELECT name, posting_date, debit_in_account_currency as debit,
        credit_in_account_currency as credit, voucher_type, voucher_no, cost_center,
        account_currency
        FROM `tabGL Entry` WHERE voucher_type != 'Period Closing Voucher' AND account = '%s'
        AND posting_date BETWEEN '%s' AND '%s' ORDER BY posting_date,
        creation""" % (acc.name, frm_dt, to_dt)
        gl_entry = frappe.db.sql(query, as_dict=1)
        income = 0
        for gl in gl_entry:
            inc_dt["currency"] = gl.account_currency
            income += gl.credit - gl.debit
            if gl.voucher_type == "Sales Invoice":
                sid = frappe.db.sql("""SELECT sid.income_account, SUM(sid.base_net_amount) as total,
                    IFNULL(itd.selling_cost_center, '%s') as cc, sid.item_code, sid.parent
                    FROM `tabSales Invoice Item` sid, `tabItem Default` itd
                    WHERE sid.parent = '%s' AND itd.parent = sid.item_code
                    AND sid.income_account = '%s'
                    GROUP BY sid.item_code""" % (def_cc, gl.voucher_no, acc.name), as_dict=1)
                for d in sid:
                    update_dict_value(dict_map=inc_dt, dict_key=d.cc, value_to_add=d.total)
            elif gl.voucher_type == "Journal Entry":
                value_to_add = gl.credit - gl.debit
                update_dict_value(dict_map=inc_dt, dict_key=gl.cost_center,
                    value_to_add=value_to_add)
            else:
                frappe.throw(f"Unkown Type of Voucher = {gl.voucher_type} for GL Entry \
                    No: {gl.name}")
        inc_dt["total"] = income
        income_map.append(inc_dt.copy())
    return income_map

def get_expense_in_period_cc_wise(exp_type, frm_dt=None, to_dt=None, company=None):
    exp_map = []
    allowed_accs = []
    acc_cond = ""
    allowed_exp_types = ["Direct", "Indirect", "Depreciation", "Tax"]
    def_cc = frappe.get_value("Company", company, "cost_center")
    if exp_type == "Direct":
        acc_cond += " AND is_direct_expense = 1 AND is_tax_expense = 0 AND \
        is_depreciation_expense = 0"
    elif exp_type == "Indirect":
        acc_cond += " AND is_direct_expense = 0 AND is_tax_expense = 0 AND \
        is_depreciation_expense = 0"
    elif exp_type == "Tax":
        acc_cond += " AND is_tax_expense = 1 AND is_direct_expense = 0 AND \
        is_depreciation_expense = 0"
    elif exp_type == "Depreciation":
        acc_cond += " AND is_tax_expense = 0 AND is_direct_expense = 0 AND \
        is_depreciation_expense = 1"
    else:
        frappe.throw(f"Expense Type Can only be one of {allowed_exp_types}")

    exp_acc = frappe.db.sql("""SELECT name, is_group, lft, rgt, report_type, root_type
        FROM `tabAccount` WHERE report_type = 'Profit and Loss' AND root_type = 'Expense'
        AND is_group = 0 %s ORDER BY name""" % acc_cond, as_dict=1)
    for acc in exp_acc:
        if allowed_accs and acc.name not in allowed_accs:
            continue
        exp_dt = frappe._dict({})
        exp_dt["account"] = acc.name
        exp_dt["root_type"] = exp_type + " " + acc.root_type
        query = """SELECT name, posting_date, debit_in_account_currency as debit,
        credit_in_account_currency as credit,
        voucher_type, voucher_no, cost_center, account_currency, account
        FROM `tabGL Entry` WHERE voucher_type != 'Period Closing Voucher' AND account = '%s'
        AND posting_date BETWEEN '%s' AND '%s' ORDER BY voucher_type, posting_date,
        creation""" % (acc.name, frm_dt, to_dt)
        gl_entry = frappe.db.sql(query, as_dict=1)
        tot_expense = 0
        for gl in gl_entry:
            exp_dt["currency"] = gl.account_currency
            gl_expense = gl.debit - gl.credit
            bal_exp = gl_expense
            tot_expense += gl_expense
            if gl.debit < 0.1 and gl.credit < 0.1:
                continue
            if gl.voucher_type in ["Purchase Invoice", "Sales Invoice"]:
                pid = frappe.db.sql("""SELECT pid.expense_account,
                    -1 * SUM(sle.stock_value_difference) as total,
                    IFNULL(itd.buying_cost_center, '%s') as cc, pid.item_code, pid.parent
                    FROM `tab%s Item` pid, `tabItem Default` itd, `tabStock Ledger Entry` sle
                    WHERE pid.parent = '%s' AND itd.parent = pid.item_code
                    AND pid.expense_account = '%s' AND sle.voucher_no = pid.parent
                    GROUP BY pid.item_code""" % (def_cc, gl.voucher_type, gl.voucher_no,
                        acc.name), as_dict=1)
                if pid:
                    for d in pid:
                        bal_exp -= d.total
                        update_dict_value(dict_map=exp_dt, dict_key=d.cc, value_to_add=d.total)
                else:
                    if gl.voucher_type == "Purchase Invoice":
                        # Check the Item code in the PO for PI and get the def_cc from there
                        query = f"""SELECT pid.expense_account, pid.base_amount as total,
                        IFNULL(itd.buying_cost_center, '{def_cc}') as cc, pod.subcontracted_item,
                        pid.parent, pid.idx, pid.name
                        FROM `tab{gl.voucher_type} Item` pid LEFT JOIN `tabPurchase Order Item` pod
                            ON pod.parent = pid.purchase_order AND pod.name = pid.po_detail,
                            `tabItem Default` itd
                        WHERE pid.parent = '{gl.voucher_no}' AND pid.expense_account = '{acc.name}'
                        AND itd.parent = pod.subcontracted_item
                        AND pod.subcontracted_item IS NOT NULL"""
                        pod = frappe.db.sql(query, as_dict=1)
                        if pod and pod[0].subcontracted_item:
                            for d in pod:
                                bal_exp -= int(d.total)
                                update_dict_value(dict_map=exp_dt, dict_key=d.cc,
                                    value_to_add=d.total)
                        else:
                            query = f"""SELECT pid.expense_account, SUM(pid.base_amount) as total,
                            IFNULL(itd.buying_cost_center, '{def_cc}') as cc, pid.item_code,
                            pid.parent
                            FROM `tab{gl.voucher_type} Item` pid, `tabItem Default` itd
                            WHERE pid.parent = '{gl.voucher_no}'
                            AND pid.expense_account = '{acc.name}' AND itd.parent = pid.item_code"""
                            pid = frappe.db.sql(query, as_dict=1)
                            if pid[0].expense_account:
                                for d in pid:
                                    bal_exp -= d.total
                                    update_dict_value(dict_map=exp_dt, dict_key=d.cc,
                                        value_to_add=d.total)
                            else:
                                update_dict_value(dict_map=exp_dt, dict_key=gl.cost_center,
                                    value_to_add=bal_exp)
                                bal_exp = 0
                    else:
                        query = f"""SELECT pid.expense_account, SUM(pid.base_amount) as total,
                        IFNULL(itd.buying_cost_center, '{def_cc}') as cc, pid.item_code, pid.parent
                        FROM `tab{gl.voucher_type} Item` pid, `tabItem Default` itd
                        WHERE pid.parent = '{gl.voucher_no}' AND pid.expense_account = '{acc.name}'
                        AND itd.parent = pid.item_code"""
                        pid = frappe.db.sql(query, as_dict=1)
                        if pid[0].expense_account:
                            for d in pid:
                                bal_exp -= d.total
                                update_dict_value(dict_map=exp_dt, dict_key=d.cc,
                                    value_to_add=d.total)
                        else:
                            update_dict_value(dict_map=exp_dt, dict_key=gl.cost_center,
                                value_to_add=bal_exp)
                            bal_exp = 0
            elif gl.voucher_type == "Delivery Note":
                dnd = frappe.db.sql("""SELECT dnd.expense_account,
                -1 * sle.stock_value_difference as st_val,
                IFNULL(itd.selling_cost_center, '%s') as cc, dnd.item_code, dnd.parent, dnd.name,
                dnd.idx
                 FROM `tabDelivery Note Item` dnd, `tabItem Default` itd, `tabStock Ledger Entry` sle
                 WHERE dnd.parent = '%s' AND itd.parent = dnd.item_code
                 AND sle.voucher_no = dnd.parent AND sle.voucher_detail_no = dnd.name
                 AND dnd.expense_account = '%s'
                 ORDER BY dnd.idx""" % (def_cc, gl.voucher_no, acc.name), as_dict=1)
                for dn in dnd:
                    bal_exp -= dn.st_val
                    update_dict_value(dict_map=exp_dt, dict_key=dn.cc, value_to_add=dn.st_val)
            elif gl.voucher_type == "Stock Entry":
                ste_dict = frappe.db.sql("""SELECT sted.expense_account,
                    -1 * SUM(sle.stock_value_difference) as st_val,
                    IFNULL(itd.selling_cost_center, '%s') as cc, sted.item_code, sted.name
                    FROM `tabStock Entry Detail` sted,`tabItem Default` itd,
                    `tabStock Ledger Entry` sle
                    WHERE sted.parent = '%s' AND itd.parent = sted.item_code
                    AND sted.expense_account = '%s' AND sle.item_code = sted.item_code
                    AND sle.voucher_no = sted.parent
                    GROUP BY sted.item_code""" % (def_cc, gl.voucher_no, acc.name), as_dict=1)
                if ste_dict and flt(ste_dict[0].st_val) != 0:
                    for ste in ste_dict:
                        bal_exp -= ste.st_val
                        update_dict_value(dict_map=exp_dt, dict_key=ste.cc, value_to_add=ste.st_val)
            elif gl.voucher_type == "Stock Reconciliation":
                sred = frappe.db.sql("""SELECT sr.expense_account, srd.qty, srd.valuation_rate,
                    srd.current_valuation_rate, sr.difference_amount,
                    IFNULL(itd.buying_cost_center, '%s') as cc, srd.current_qty,srd.item_code,
                    srd.parent, srd.name, srd.warehouse,
                    CONCAT(sr.posting_date, ' ', sr.posting_time) as ptime
                    FROM `tabStock Reconciliation` sr, `tabStock Reconciliation Item` srd,
                    `tabItem Default` itd
                    WHERE srd.parent = sr.name AND itd.parent = srd.item_code AND sr.name = '%s'
                    AND sr.expense_account = '%s'""" % (def_cc, gl.voucher_no, acc.name), as_dict=1)
                for sr in sred:
                    if sr.difference_amount == (gl.credit - gl.debit):
                        # Post as it is else find the correct current val rate and qty
                        cur_val = sr.current_qty * sr.current_valuation_rate
                        new_val = sr.qty * sr.valuation_rate
                        diff_amt = cur_val - new_val
                        update_dict_value(dict_map=exp_dt, dict_key=sr.cc, value_to_add=diff_amt)
                    else:
                        sle = frappe.db.sql("""SELECT sle.valuation_rate as cur_vr,
                            sle.qty_after_transaction as cur_qty, sle.name, sle.item_code,
                            sle.warehouse, CONCAT(sle.posting_date, ' ', sle.posting_time) as ptime
                            FROM `tabStock Ledger Entry` sle WHERE sle.item_code = '%s'
                            AND sle.warehouse = '%s'
                            AND CONCAT(sle.posting_date, ' ', sle.posting_time) < '%s'
                            ORDER BY ptime DESC LIMIT 1""" % (sr.item_code, sr.warehouse,
                                sr.ptime), as_dict=1)
                        if sle:
                            cur_qty = sle[0].cur_qty
                            cur_vr = sle[0].cur_vr
                        else:
                            cur_qty = 0
                        diff_amt = (cur_qty * cur_vr) - (sr.qty * sr.valuation_rate)
                        bal_exp -= diff_amt
                        update_dict_value(dict_map=exp_dt, dict_key=sr.cc, value_to_add=diff_amt)
            elif gl.voucher_type == "Salary Slip":
                emp = frappe.get_value("Salary Slip", gl.voucher_no, "employee")
                emp_status = frappe.get_value("Employee", emp, "status")
                if emp_status == "Active":
                    query = """SELECT ss.name, ss.employee, emp.department,
                    IFNULL(dep.default_cost_center, '%s') as cc, emp.status
                    FROM `tabSalary Slip` ss, `tabEmployee` emp, `tabDepartment` dep
                    WHERE ss.name = '%s' AND emp.name = ss.employee
                    AND dep.name = emp.department""" % (def_cc, gl.voucher_no)
                else:
                    query = """SELECT ss.name, ss.employee, ss.department,
                    IFNULL(dep.default_cost_center, '%s') as cc, emp.status
                    FROM `tabSalary Slip` ss, `tabEmployee` emp, `tabDepartment` dep
                    WHERE ss.name = '%s' AND emp.name = ss.employee
                    AND dep.name = ss.department""" % (def_cc, gl.voucher_no)
                slps = frappe.db.sql(query, as_dict=1)
                for ss in slps:
                    bal_exp = 0
                    value_to_add = gl.debit - gl.credit
                    update_dict_value(dict_map=exp_dt, dict_key=ss.cc, value_to_add=value_to_add)
            elif gl.voucher_type == "Expense Claim":
                emp = frappe.get_value("Expense Claim", gl.voucher_no, "employee")
                emp_status = frappe.get_value("Employee", emp, "status")
                if emp_status == "Active":
                    query = """SELECT ecl.name, ecl.employee, emp.department,
                    IFNULL(dep.default_cost_center, '%s') as cc, emp.status
                    FROM `tabExpense Claim` ecl, `tabEmployee` emp, `tabDepartment` dep
                    WHERE ecl.name = '%s' AND emp.name = ecl.employee
                    AND dep.name = emp.department""" % (def_cc, gl.voucher_no)
                else:
                    query = """SELECT ecl.name, ecl.employee, ecl.department,
                    IFNULL(dep.default_cost_center, '%s') as cc, emp.status
                    FROM `tabExpense Claim` ecl, `tabEmployee` emp, `tabDepartment` dep
                    WHERE ecl.name = '%s' AND emp.name = ecl.employee AND dep.name =
                    ecl.department""" % (def_cc, gl.voucher_no)
                ecls = frappe.db.sql(query, as_dict=1)
                for ecl in ecls:
                    bal_exp = 0
                    value_to_add = gl.debit - gl.credit
                    update_dict_value(dict_map=exp_dt, dict_key=ecl.cc,
                        value_to_add=value_to_add)
            elif gl.voucher_type in ["Journal Entry", "Payment Entry", "Purchase Receipt"]:
                if exp_type == "Depreciation" and gl.voucher_type == "Journal Entry":
                    query = f"""SELECT jvd.name, jvd.account, jvd.reference_type,
                    jvd.reference_name, jvd.debit_in_account_currency as debit,
                    jvd.credit_in_account_currency as credit,
                    IFNULL(ass.asset_cost_center, '{def_cc}') as cc
                    FROM `tabJournal Entry Account` jvd, `tabAsset` ass
                    WHERE jvd.parent = '{gl.voucher_no}' AND jvd.account = '{acc.name}'
                    AND ass.name = jvd.reference_name AND jvd.reference_type = 'Asset'"""
                    jvd_list = frappe.db.sql(query, as_dict=1)
                    for jv in jvd_list:
                        value_to_add = jv.debit - jv.credit
                        update_dict_value(dict_map=exp_dt, dict_key=jv.cc,
                            value_to_add=value_to_add)
                        bal_exp -= value_to_add
                else:
                    bal_exp = 0
                    value_to_add = gl.debit - gl.credit
                    update_dict_value(dict_map=exp_dt, dict_key=gl.cost_center,
                        value_to_add=value_to_add)
            else:
                frappe.throw(f"Unkown Type of Voucher = {gl.voucher_type} for GL Entry \
                    No: {gl.name}")
            if bal_exp != 0:
                update_dict_value(dict_map=exp_dt, dict_key=gl.cost_center, value_to_add=bal_exp)
        exp_dt["total"] = tot_expense
        exp_map.append(exp_dt.copy())
    return exp_map

def update_dict_value(dict_map, dict_key, value_to_add):
    if dict_map.get(dict_key, None):
        dict_map[dict_key] += value_to_add
    else:
        dict_map[dict_key] = value_to_add
