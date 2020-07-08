# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def validate(doc, method):
    if doc.reference_type == 'Communication':
        if doc.reference_name:
            comm_doc = frappe.get_doc('Communication', doc.reference_name)
        else:
            frappe.throw('Reference Name is Mandatory for {} Reference Type'.format(doc.reference_name))
        if comm_doc.follow_up == 1 and doc.status == 'Closed':
            frappe.msgprint("If you don't wish to receive ToDo for this Communication  then Click on Communication "
                            "and uncheck the Follow Up Check Box or Change the next action date to be reminded "
                            "again about this communication {}".format(frappe.get_desk_link("Communication",
                                                                                            doc.reference_name)))
