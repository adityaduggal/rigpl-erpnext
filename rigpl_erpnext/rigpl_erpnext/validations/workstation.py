# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from six import iteritems


def validate(doc, method):
    # Operation Table should have atleast one Operation
    allowed_ops = []
    if not doc.workstation_operation:
        frappe.throw(f"Atleast One Operation is Mandatory for the Workstation")
    else:
        for d in doc.workstation_operation:
            if d.allowed_operation not in allowed_ops:
                allowed_ops.append(d.allowed_operation)
            else:
                frappe.throw(f"For Row# {d.idx} and Operation: {d.allowed_operation} is Repeated")


@frappe.whitelist()
def get_workstation_for_operation(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
    from frappe.desk.reportview import get_match_cond

    operation = filters.pop('operation')

    condition = ""
    meta = frappe.get_meta("Workstation")
    for fieldname, value in iteritems(filters):
        if meta.get_field(fieldname) or fieldname in frappe.db.DEFAULT_COLUMNS:
            condition += " and {field}={value}".format(
                field=fieldname,
                value=frappe.db.escape(value))

    searchfields = meta.get_search_fields()

    if searchfield and (meta.get_field(searchfield)
                or searchfield in frappe.db.DEFAULT_COLUMNS):
        searchfields.append(searchfield)

    search_condition = ''
    for field in searchfields:
        if search_condition == '':
            search_condition += '`tabWorkstation`.`{field}` LIKE %(txt)s'.format(field=field)
        else:
            search_condition += ' OR `tabWorkstation`.`{field}` like %(txt)s'.format(field=field)

    return frappe.db.sql("""SELECT
            `tabWorkstation`.name
        FROM
            `tabWorkstation`, `tabWorkstation Operation`
        WHERE
            `tabWorkstation Operation`.parent = `tabWorkstation`.name AND
            `tabWorkstation Operation`.parenttype = 'Workstation' AND
            `tabWorkstation Operation`.allowed_operation = %(operation)s AND
            `tabWorkstation`.disabled = 0 AND
            ({search_condition})
            {mcond} {condition}
        ORDER BY
            if(locate(%(_txt)s, `tabWorkstation`.name), locate(%(_txt)s, `tabWorkstation`.name), 99999),
            `tabWorkstation`.name
        LIMIT %(start)s, %(page_len)s """.format(
            mcond=get_match_cond(doctype),
            key=searchfield,
            search_condition = search_condition,
            condition=condition or ""), {
            'txt': '%' + txt + '%',
            '_txt': txt.replace("%", ""),
            'start': start,
            'page_len': page_len,
            'operation': operation
    })
