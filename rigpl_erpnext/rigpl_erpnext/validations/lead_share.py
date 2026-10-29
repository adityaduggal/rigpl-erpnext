# -*- coding: utf-8 -*-
#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
from rigpl_erpnext.utils.lead_share_utils import sync_lead_shares


def quotation_on_update(doc, method):
    if doc.quotation_to == "Lead" and doc.party_name:
        sync_lead_shares([doc.party_name])


def opportunity_on_update(doc, method):
    if doc.opportunity_from == "Lead" and doc.party_name:
        sync_lead_shares([doc.party_name])


def address_on_update(doc, method):
    sync_lead_shares([link.link_name for link in doc.links if link.link_doctype == "Lead"])
