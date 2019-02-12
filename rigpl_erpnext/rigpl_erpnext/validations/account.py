# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint
from rigpl_erpnext.utils.rigpl_perm import *

def validate(doc,method):
	if doc.get("__islocal") != 1:
		copy_users_to_child_accounts(doc)
		check_account_perm(doc)