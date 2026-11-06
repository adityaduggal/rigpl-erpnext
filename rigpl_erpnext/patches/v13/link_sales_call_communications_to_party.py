import frappe
from frappe.utils import now

from rigpl_erpnext.utils.batch_write_utils import bulk_insert_rows, bulk_update_rows
from rigpl_erpnext.utils.follow_up_utils import end_follow_ups


def execute():
    """
    The old Daily Call made a Customer call against the Contact and set the v12 timeline fields,
    so v13 did not show it on the Customer. Points these Communications to the DCR party and adds
    the Contact as a timeline link. Then ends the follow-ups that a newer call to the same party
    replaced. Safe to run again: it only changes rows that still point to a Contact.
    """
    # Same name as the search_index that the schema sync adds later
    frappe.db.add_index("Daily Call Details", ["communication"], index_name="communication_index")
    rows = frappe.db.sql("""SELECT c.name, c.reference_name AS contact, d.document, d.document_name
        FROM `tabDaily Call Details` d JOIN `tabCommunication` c ON c.name = d.communication
        WHERE c.reference_doctype = 'Contact' AND IFNULL(d.document_name, '') != ''""", as_dict=1)
    linked = set(frappe.db.sql("""SELECT l.parent, l.link_name FROM `tabCommunication Link` l
        JOIN `tabDaily Call Details` d ON d.communication = l.parent
        WHERE l.link_doctype = 'Contact'"""))

    bulk_update_rows("Communication", {row.name: {"reference_doctype": row.document,
        "reference_name": row.document_name} for row in rows})
    timestamp, user = now(), frappe.session.user
    bulk_insert_rows("Communication Link",
        ["name", "parent", "parenttype", "parentfield", "idx", "link_doctype", "link_name", "creation",
         "modified", "owner", "modified_by", "docstatus"],
        [(frappe.generate_hash(length=10), row.name, "Communication", "timeline_links", 1, "Contact",
          row.contact, timestamp, timestamp, user, user, 0)
         for row in rows if row.contact and (row.name, row.contact) not in linked])

    replaced = end_replaced_follow_ups()
    print(f"Linked {len(rows)} Sales Call Communications to their party and ended {replaced} replaced "
          f"follow-ups.")


def end_replaced_follow_ups() -> int:
    """Keeps only the latest follow-up of each party."""
    latest, older = {}, []
    for comm in frappe.get_all("Communication", filters={"communication_type": "Communication", "follow_up": 1},
            fields=["name", "reference_doctype", "reference_name"], order_by="communication_date desc"):
        key = (comm.reference_doctype, comm.reference_name)
        if not (key[0] and key[1]):
            continue
        if key in latest:
            older.append(comm.name)
        else:
            latest[key] = comm.name
    end_follow_ups(older)
    return len(older)
