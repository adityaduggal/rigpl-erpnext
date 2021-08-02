# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from rigpl_erpnext.utils.item_utils import *
from operator import itemgetter
from time import time
from frappe.utils.background_jobs import enqueue


def enqueue_check_wrong_variants():
    enqueue(check_wrong_variants, queue="long", timeout=7200)


def check_wrong_variants():
    # Total time taken by this function is around 2300 seconds
    st_time = time()
    check_expired_items()
    check_items_as_per_sorting_for_website()
    tot_time = int(time() - st_time)
    print(f"Total Time Taken = {tot_time} seconds")


def check_expired_items():
    it_expired = frappe.db.sql("""SELECT name, disabled, end_of_life FROM `tabItem`
	WHERE end_of_life < CURDATE() and disabled = 0""", as_dict=1)
    for it in it_expired:
        frappe.db.set_value("Item", it.name, "disabled", 1)
        print("Item Code: " + it.name + " is Expired and hence Disabled")
    print("Total Items = " + str(len(it_expired)))
    frappe.db.commit()


def check_items_as_per_sorting_for_website():
    temp_list = frappe.db.sql("""SELECT name, modified FROM `tabItem` WHERE variant_of IS NULL and disabled = 0
	AND IFNULL(end_of_life, '2099-12-31') > CURDATE() AND has_variants = 1 ORDER BY modified DESC""", as_list=1)
    t_count = 0
    all_items = 0
    for temp in temp_list:
        print(str(t_count + 1) + ". Template: " + temp[0] + " Last Modified On: " + str(temp[1]))
        t_count += 1
        attributes = get_temp_attributes(temp[0])
        item_dict = get_sorted_items_for_template(temp[0], attributes)
        v_count = 0
        check = 1
        sno = 0
        for it in item_dict:
            sno += 1
            all_items += 1
            print(f"{sno}. Checking for Item Code {it.name}")
            it_doc = frappe.get_doc("Item", it.name)
            temp_doc = frappe.get_doc("Item", temp[0])
            validate_variants(it_doc, comm_type="backend")
            check += check_and_copy_attributes_to_variant(temp_doc, it_doc)
            if all_items % 100 == 0 and all_items > 0:
                print(f"Committing Changes after making {all_items} Changes")
                frappe.db.commit()


def get_temp_attributes(temp_name):
    att_dict = frappe.db.sql("""SELECT iva.idx, iva.attribute, iva.numeric_values FROM `tabItem Variant Attribute` iva
	WHERE iva.parent = '%s'""" % (temp_name), as_dict=1)
    attributes = sorted(att_dict, key=itemgetter('idx'))
    return attributes


def get_sorted_items_for_template(temp_name, att_dict):
    att_query = ""
    att_sort = ""
    att_join = ""
    for att in att_dict:
        att_trimmed = att.attribute.replace(" ", "")
        if att.numeric_values == 1:
            att_query += """, CAST(%s.attribute_value AS DECIMAL(8,3)) as %s""" % (att_trimmed, att_trimmed)
            att_sort += """CAST(%s.attribute_value AS DECIMAL(8,3)), """ % (att_trimmed)
        else:
            att_query += """, IFNULL(%s.attribute_value, "-") as %s""" % (att_trimmed, att_trimmed)
            att_sort += """%s.attribute_value, """ % (att_trimmed)

        att_join += """ LEFT JOIN `tabItem Variant Attribute` %s ON it.name = %s.parent
			AND %s.attribute = '%s'""" %(att_trimmed,att_trimmed,att_trimmed,att.attribute)
    att_sort = " ORDER BY " + att_sort
    query = """SELECT it.name %s FROM `tabItem` it %s WHERE it.disabled =0
	AND it.variant_of = '%s' %s it.name""" % (att_query, att_join, temp_name, att_sort)
    it_dict = frappe.db.sql(query, as_dict=1)
    return it_dict


def copy_from_template():
    limit_set = int(frappe.db.get_single_value("Stock Settings", "automatic_sync_field_limit"))
    is_sync_allowed = frappe.db.get_single_value("Stock Settings", "automatically_sync_templates_data_to_items")
    if is_sync_allowed == 1:
        templates = frappe.db.sql("""SELECT it.name, (SELECT count(name)
		FROM `tabItem` WHERE variant_of = it.name) as variants FROM `tabItem` it WHERE it.has_variants = 1
		AND it.disabled = 0 AND it.end_of_life >= CURDATE()
		ORDER BY variants DESC""", as_list=1)
        sno = 0
        for t in templates:
            sno += 1
            print(str(sno) + " " + t[0] + " has variants = " + str(t[1]))
        fields_edited = 0
        it_lst = []
        for t in templates:
            print(str(t[0]) + " Has No of Variants = " + str(t[1]))
            if fields_edited <= limit_set:
                temp_doc = frappe.get_doc("Item", t[0])
                variants = frappe.db.sql("""SELECT name FROM `tabItem` WHERE variant_of = '%s'
				ORDER BY name ASC""" % (t[0]), as_list=1)
                # Check all variants' fields are matching with template if
                # not then copy the fields else go to next item
                for item in variants:
                    check = 0
                    print("Checking Item = " + item[0])
                    it_doc = frappe.get_doc("Item", item[0])
                    validate_variants(it_doc, comm_type="backend")
                    check += check_and_copy_attributes_to_variant(temp_doc, it_doc)
                    fields_edited += check
            else:
                print("Limit of " + str(limit_set) + " fields reached. Run again for more updating")
                break
            frappe.db.commit()
