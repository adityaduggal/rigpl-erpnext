# -*- coding: utf-8 -*-
#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
"""
One scheduled run for the Process Sheet and Job Card jobs (#145, epic #165). The steps write to
the same Process Sheets and Job Cards, so they run one after the other in one long job, and
`enqueue_once` keeps a second copy off the queue while the first one runs.
"""
from __future__ import unicode_literals
import time
import frappe
from rohit_common.utils.background_doc_processing import enqueue_once
from . import create_new_job_cards, process_sheet_update, update_job_card_status

PIPELINE = "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.manufacturing_pipeline.execute"
TIMEOUT = 3600


def enqueue_pipeline():
    enqueue_once(PIPELINE, queue="long", timeout=TIMEOUT)


def get_steps():
    return [
        ("Create Process Sheets", process_sheet_update.create_new_process_sheets),
        ("Consolidate Transfer Operations", process_sheet_update.consolidate_transfer_operations),
        ("Clean up Job Cards", create_new_job_cards.execute),
        ("Update Job Card RM Status", update_job_card_status.update_rm_status_unmodified),
        ("Update Job Card Status", update_job_card_status.execute),
        ("Update Process Sheet Priority", process_sheet_update.update_process_sheet_priority),
    ]


def execute():
    st_time = time.time()
    failed = [title for title, step in get_steps() if not run_step(title, step)]
    print(f"Manufacturing Pipeline done in {int(time.time() - st_time)} seconds. Failed steps: "
          f"{', '.join(failed) or 'None'}")


def run_step(title, step):
    """Run one step and commit it. A failed step is rolled back and logged, and the next step
    still runs. Returns True when the step succeeds."""
    st_time = time.time()
    try:
        step()
        frappe.db.commit()
        ok = True
    except Exception:
        frappe.db.rollback()
        frappe.log_error(title=f"Manufacturing Pipeline: {title} failed")
        ok = False
    print(f"{title}: {'done' if ok else 'FAILED'} in {int(time.time() - st_time)} seconds")
    return ok
