import frappe


def execute():
    """
    The hourly follow-up job (#150) finds due follow-ups by `communication_type`, `follow_up` and
    `next_action_date`. `add_index` skips an index that exists.
    """
    frappe.db.add_index("Communication", ["communication_type", "follow_up", "next_action_date"],
        "idx_comm_follow_up")
    print("Communication follow-up index is in place.")
