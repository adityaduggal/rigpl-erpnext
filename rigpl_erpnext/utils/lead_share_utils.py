#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
"""
Shares a Lead and its Quotations, Opportunities and Addresses with the lead owner (#151).
Sales Representatives see these doctypes only if they own them or they are shared, so a Lead
made by someone else for a rep must be shared with the rep. On a shared document only the
lead owner keeps a share: all other shares, also shares with everyone, are removed.
"""
from typing import Dict, List, Optional, Set, Tuple

import frappe
from frappe.share import add

from .item_attribute_utils import chunks

# doctype: query for (name, lead_owner) of the documents made by someone else than the lead owner
WANTED_QUERIES = {
    "Lead": """SELECT l.name, l.lead_owner FROM `tabLead` l
        WHERE l.lead_owner IS NOT NULL AND l.owner != l.lead_owner {lead_cond}""",
    "Quotation": """SELECT q.name, l.lead_owner FROM `tabQuotation` q
        JOIN `tabLead` l ON l.name = q.party_name
        WHERE q.quotation_to = 'Lead' AND q.owner != l.lead_owner {lead_cond}""",
    "Opportunity": """SELECT o.name, l.lead_owner FROM `tabOpportunity` o
        JOIN `tabLead` l ON l.name = o.party_name
        WHERE o.opportunity_from = 'Lead' AND o.owner != l.lead_owner {lead_cond}""",
    "Address": """SELECT DISTINCT a.name, l.lead_owner FROM `tabDynamic Link` dl
        JOIN `tabAddress` a ON a.name = dl.parent
        JOIN `tabLead` l ON l.name = dl.link_name
        WHERE dl.parenttype = 'Address' AND dl.link_doctype = 'Lead' AND a.owner != l.lead_owner {lead_cond}""",
}


def sync_lead_shares(leads: Optional[List[str]] = None):
    """Shares the documents of `leads` (all Leads if None) and writes only the changed shares."""
    if leads is not None and not leads:
        return
    rules = load_share_rules()
    wanted = get_wanted_shares(rules, leads)
    to_add, to_remove = get_changes(wanted, get_existing_shares(wanted))
    for name in to_remove:
        frappe.delete_doc("DocShare", name, ignore_permissions=True)
    for dt, dn in to_add:
        rule = rules[dt]
        add(dt, dn, user=wanted[(dt, dn)], write=rule.write_access, share=rule.share_access,
            flags={"ignore_share_permission": True}, notify=rule.notify_by_email)
    return to_add, to_remove


def load_share_rules() -> Dict[str, frappe._dict]:
    """
    {doctype: rule} for the doctypes above, where rule.users are the enabled users with a role
    of the rule. System Managers see all documents and get no share.
    """
    rows = frappe.db.sql("""SELECT role, document_type, write_access, share_access, notify_by_email
        FROM `tabUser Share Rules` WHERE parent = 'User Share Settings' AND parentfield = 'rules'
        AND apply_to_all_values = 1 AND document_type IN %(doctypes)s""",
        {"doctypes": tuple(WANTED_QUERIES)}, as_dict=1)
    roles_by_user = {}
    for user, role in frappe.db.sql("""SELECT hr.parent, hr.role FROM `tabHas Role` hr
            JOIN `tabUser` u ON u.name = hr.parent
            WHERE hr.parenttype = 'User' AND u.enabled = 1 AND u.name != 'Administrator'"""):
        roles_by_user.setdefault(user, set()).add(role)
    rules = {}
    for row in rows:
        rule = rules.setdefault(row.document_type, frappe._dict(row, users=set()))
        rule.users.update(user for user, roles in roles_by_user.items()
                          if row.role in roles and "System Manager" not in roles)
    return rules


def get_wanted_shares(rules: Dict, leads: Optional[List[str]] = None) -> Dict[Tuple[str, str], str]:
    """{(doctype, name): lead_owner} of the documents that must be shared with the lead owner."""
    wanted = {}
    for dt, rule in rules.items():
        if not rule.users:
            continue
        for chunk in ([None] if leads is None else chunks(leads)):
            lead_cond = "" if chunk is None else "AND l.name IN %(leads)s"
            rows = frappe.db.sql(WANTED_QUERIES[dt].format(lead_cond=lead_cond), {"leads": tuple(chunk or ())})
            wanted.update(((dt, name), owner) for name, owner in rows if owner in rule.users)
    return wanted


def get_existing_shares(wanted: Dict) -> List[frappe._dict]:
    names_by_dt = {}
    for dt, dn in wanted:
        names_by_dt.setdefault(dt, []).append(dn)
    shares = []
    for dt, names in names_by_dt.items():
        for chunk in chunks(names):
            shares += frappe.get_all("DocShare", filters={"share_doctype": dt, "share_name": ["in", chunk]},
                                     fields=["name", "user", "share_doctype", "share_name"])
    return shares


def get_changes(wanted: Dict[Tuple[str, str], str], existing: List) -> Tuple[List[Tuple[str, str]], List[str]]:
    """
    Returns (to_add, to_remove): the (doctype, name) that miss the lead owner's share, and the
    names of the other shares on the wanted documents. Other documents are not changed.
    """
    shared: Set[Tuple[str, str]] = set()
    to_remove = []
    for share in existing:
        key = (share.share_doctype, share.share_name)
        if key not in wanted:
            continue
        if share.user == wanted[key]:
            shared.add(key)
        else:
            to_remove.append(share.name)
    to_add = [key for key in wanted if key not in shared]
    return to_add, to_remove
