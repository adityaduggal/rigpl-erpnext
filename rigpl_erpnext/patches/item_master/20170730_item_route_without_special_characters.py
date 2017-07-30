# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import re

def execute():
	items = frappe.db.sql("""SELECT name FROM `tabItem`""", as_list=1)
	for it in items:
		it_doc = frappe.get_doc("Item", it[0])
		route_name = (re.sub('[^A-Za-z0-9]+', ' ', it_doc.item_name))
		acceptable_route = frappe.db.get_value('Item Group', it_doc.item_group, 'route') + '/' + \
		it_doc.scrub(route_name)

		if it_doc.route != acceptable_route:
			it_doc.route_name = acceptable_route
			print ("Item Code: " + it[0] + " Route Changed")