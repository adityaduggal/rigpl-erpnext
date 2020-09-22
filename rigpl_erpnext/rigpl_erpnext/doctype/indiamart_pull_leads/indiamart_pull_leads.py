# -*- coding: utf-8 -*-
# Copyright (c) 2019, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from rigpl_erpnext.rigpl_erpnext.scheduled_tasks.indiamart import get_indiamart_leads
from frappe.model.document import Document


class IndiaMartPullLeads(Document):

    def get_leads(self):
        get_indiamart_leads()
