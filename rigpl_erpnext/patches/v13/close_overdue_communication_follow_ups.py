import frappe
from frappe.utils import now

from rigpl_erpnext.utils.follow_up_utils import end_follow_ups
from rigpl_erpnext.utils.item_attribute_utils import chunks


def execute():
    """
    The old hourly job opened each closed follow-up ToDo again, so thousands stayed open (#150).
    Ends all overdue follow-ups and closes all Open ToDos of Communications that have no
    follow-up. Follow-ups that are not due yet are kept.
    """
    overdue = frappe.db.sql_list("""SELECT name FROM `tabCommunication`
        WHERE communication_type = 'Communication' AND follow_up = 1 AND next_action_date <= %s""", now())
    end_follow_ups(overdue)

    orphans = frappe.db.sql_list("""SELECT t.name FROM `tabToDo` t
        LEFT JOIN `tabCommunication` c ON c.name = t.reference_name
        WHERE t.reference_type = 'Communication' AND t.status = 'Open' AND IFNULL(c.follow_up, 0) = 0""")
    todo = frappe.qb.DocType("ToDo")
    for chunk in chunks(orphans):
        frappe.qb.update(todo).set(todo.status, "Closed").set(todo.modified, now()).where(
            todo.name.isin(chunk)).run()
    print(f"Ended {len(overdue)} overdue follow-ups and closed {len(orphans)} more follow-up ToDos.")
