import frappe


def execute():
    """
    The FG to RM map of BOM Template RIGPL is now the field fg_rm_map (was fg_rm_grade_map, #163).
    Moves the rows. Idempotent.
    """
    if not frappe.db.table_exists("FG RM Grade Map"):
        return
    gm = frappe.qb.DocType("FG RM Grade Map")
    condition = (gm.parenttype == "BOM Template RIGPL") & (gm.parentfield == "fg_rm_grade_map")
    count = len(frappe.qb.from_(gm).select(gm.name).where(condition).run())
    if count:
        frappe.qb.update(gm).set(gm.parentfield, "fg_rm_map").where(condition).run()
        print(f"FG RM Grade Map: {count} rows moved to fg_rm_map.")
