# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def validate(doc,method):
	#Disable SO only if not Disabled and also only if its for Selling
	if doc.selling != 1:
		if doc.disable_so == 1:
			doc.disable_so = 0
			