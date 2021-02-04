# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt
from frappe.model.document import Document


class RIGPLSettings(Document):
    def validate(self):
        """
        ROL Value percentages Checks. Percentage cannot be greater than 100 and lowest Value should be Equal to Min ROL
        ROL Qty percent Checks. Last 0 should have value and 1 should have value besides 100% check
        """
        qty_txt = self.rol_qty_percentages
        qty_txt = qty_txt.split(",")
        zero_qty = 0
        one_qty = 0
        for d in qty_txt:
            d = d.split(":")
            if flt(d[1]) > 100:
                frappe.throw(f"Percentage mentioned in {self.rol_qty_percentages} is Greater than 100%")
            if flt(d[0]) == 0:
                zero_qty = 1
            elif flt(d[0]) == 1:
                one_qty = 1
        if zero_qty == 0:
            frappe.throw(f"Zero Quantity Rule Should be Mentioned in {self.rol_qty_percentages}")
        if one_qty == 0:
            frappe.throw(f"Quantity 1 Rule Should be Mentioned in {self.rol_qty_percentages}")

        val_txt = self.rol_value_percentages
        val_txt = val_txt.split(",")
        min_value = 0
        min_rol_change = 0
        for d in val_txt:
            d = d.split(":")
            if min_rol_change < flt(d[0]) * flt(d[1]) / 100:
                min_rol_change = flt(d[0]) * flt(d[1]) / 100
            if flt(d[1]) > 100:
                frappe.throw(f"Percentage mentioned in {self.rol_value_percentages} is Greater than 100%")
            if flt(d[0]) == self.minimum_rol_value:
                min_value = 1
        if min_value == 0:
            frappe.throw(f"Min ROL Value {self.minimum_rol_value} Rule Should be Mentioned "
                         f"in {self.rol_value_percentages}")
        if min_rol_change > self.max_rol_fluctuation:
            frappe.throw(f"Min ROL Change = {min_rol_change} As per ROL Value Percentages. But Max ROL Change Set is "
                         f"{self.max_rol_fluctuation}. Kindly correct this ambiguity")

        weightage = self.sales_weightage + self.payment_weightage + self.age_weightage
        if weightage != 100:
            frappe.throw("Total Weightage Should be 100")
