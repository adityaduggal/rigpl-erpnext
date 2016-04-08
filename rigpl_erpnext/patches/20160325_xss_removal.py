from __future__ import unicode_literals
import frappe
from frappe import msgprint

from HTMLParser import HTMLParser

def execute():
	
	h = HTMLParser()
	
	for name, rule in  frappe.db.sql("""SELECT name, rule FROM `tabItem Variant Restrictions` WHERE rule is not null""", as_list=1):
		frappe.db.set_value("Item Variant Restrictions", name, 'rule', h.unescape(rule))
		
	