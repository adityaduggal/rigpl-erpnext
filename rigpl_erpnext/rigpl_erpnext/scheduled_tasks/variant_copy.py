# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from datetime import date
from rigpl_erpnext.utils.item_utils import *

#Run this script every hour but to ensure that there is no server overload run it only for 1 template at a time

def check_wrong_variants():
	check_expired_items()
	check_items_last_modified()

def check_expired_items():
	it_expired = frappe.db.sql("""SELECT name, disabled, end_of_life FROM `tabItem` 
		WHERE end_of_life < CURDATE() and disabled = 0""", as_dict=1)
	for it in it_expired:
		frappe.db.set_value("Item", it.name, "disabled", 1)
		print("Item Code: " + it.name + " is Expired and hence Disabled")
	print("Total Items = " + str(len(it_expired)))
	frappe.db.commit()

def check_items_last_modified():
	item_list = frappe.db.sql("""SELECT name FROM `tabItem` 
		WHERE variant_of IS NOT NULL AND disabled = 0 
		AND IFNULL(end_of_life, '2099-12-31') > CURDATE()
		ORDER BY modified ASC""", as_list=1)
	check = 1
	sno = 0
	for item in item_list:
		sno += 1
		print (str(sno) + ". Checking Item = " + item[0])
		it_doc = frappe.get_doc("Item", item[0])
		temp_doc = frappe.get_doc("Item", it_doc.variant_of)
		validate_variants(it_doc, comm_type="backend")
		check += check_and_copy_attributes_to_variant(temp_doc, it_doc)
		
		if sno%100 == 0:
			frappe.db.commit()

def copy_from_template():
	limit_set = int(frappe.db.get_single_value("Stock Settings", "automatic_sync_field_limit"))
	is_sync_allowed = frappe.db.get_single_value("Stock Settings", 
		"automatically_sync_templates_data_to_items")
	if is_sync_allowed == 1:
		templates = frappe.db.sql("""SELECT it.name, (SELECT count(name) 
			FROM `tabItem` WHERE variant_of = it.name) as variants 
			FROM `tabItem` it WHERE it.has_variants = 1 
			AND it.disabled = 0 AND it.end_of_life >= CURDATE()
			ORDER BY variants DESC""", as_list=1)
		sno = 0
		for t in templates:
			sno += 1
			print (str(sno) + " " + t[0] + " has variants = " + str(t[1]))
		fields_edited = 0
		it_lst = []
		for t in templates:
			print (str(t[0]) + " Has No of Variants = " + str(t[1]))
			if fields_edited <= limit_set:
				temp_doc = frappe.get_doc("Item", t[0])
				variants = frappe.db.sql("""SELECT name FROM `tabItem` WHERE variant_of = '%s'
					ORDER BY name ASC"""%(t[0]), as_list=1)
				#Check all variants' fields are matching with template if 
				#not then copy the fields else go to next item
				for item in variants:
					check = 0
					print ("Checking Item = " + item[0])
					it_doc = frappe.get_doc("Item", item[0])
					validate_variants(it_doc, comm_type="backend")
					check += check_and_copy_attributes_to_variant(temp_doc, it_doc)
					fields_edited += check
			else:
				print ("Limit of " + str(limit_set) + " fields reached. Run again for more updating")
				break
			frappe.db.commit()