from __future__ import unicode_literals
import frappe

def get_context(context):
    context.homepage_settings = frappe.get_doc('Homepage', 'Homepage')