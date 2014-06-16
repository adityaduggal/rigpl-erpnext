# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint, _

def fn_base_metal(doc, base_material):
	return {
		"HSS": 'H',
		"Carbide": 'C',
	}.get(base_material,"")

def fn_is_rm(doc, is_rm):
	return {
		"Yes": 'R',
	}.get(is_rm,"")

def autoname(doc, method=None):
	RM = fn_is_rm(doc, doc.is_rm)
	BM = fn_base_metal(doc, doc.base_material)
	QLT = doc.material
	name_inter = '{0}{1}{2}{3}'.format(RM, BM, "-", QLT)
	doc.name = name_inter
