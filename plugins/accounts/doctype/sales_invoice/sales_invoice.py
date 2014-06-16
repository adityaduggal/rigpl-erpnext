# -*- coding: utf-8 -*-
# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import webnotes
import webnotes.defaults

from webnotes.utils import add_days, cint, cstr, date_diff, flt, getdate, nowdate, \
	get_first_day, get_last_day

from webnotes.utils.email_lib import sendmail
from webnotes.utils import comma_and, get_url
from webnotes.model.doc import make_autoname
from webnotes.model.bean import getlist
from webnotes.model.code import get_obj
from webnotes import _, msgprint

month_map = {'Monthly': 1, 'Quarterly': 3, 'Half-yearly': 6, 'Yearly': 12}

from controllers.selling_controller import SellingController

class DocType(SellingController):
	
	def __init__(self,d,dl):
		self.doc, self.doclist = d, dl
		self.log = []
		self.tname = 'Sales Invoice Item'
		self.fname = 'entries'

	def validate(self):
		if cint(self.doc.update_stock) != 1:
			webnotes.msgprint(self.doc.update_stock)
			self.validate_delivery_note()
	
	def validate_delivery_note(self):
		for d in self.doclist.get({"parentfield": "entries"}):
			if d.delivery_note is None:
				msgprint("""Stock update is Mandatory if there is no Delivery Note""", raise_exception=1)