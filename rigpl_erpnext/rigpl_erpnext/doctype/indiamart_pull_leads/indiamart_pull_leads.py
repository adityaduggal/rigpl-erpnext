# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from rigpl_erpnext.rigpl_erpnext.scheduled_tasks.indiamart import execute
from frappe.model.document import Document


class IndiaMartPullLeads(Document):

    def get_leads(self):
        execute()
