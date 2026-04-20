# -*- coding: utf-8 -*-

import frappe

# avoid importing erpnext unless tables exist
try:
    import erpnext
except Exception:
    erpnext = None

def execute():
    # Don't run heavy ORM logic if the DB/schema isn't ready
    run_unwanted_patches()

def run_unwanted_patches():
    # keep existing behavior (import inside function to avoid imports at module load)
    try:
        from rigpl_erpnext.patches.run_unwanted_patches import run_unwanted_patches as _rup
        _rup()
    except Exception as e:
        # If patch runner can't be imported/run at this stage, log and continue.
        print("run_unwanted_patches() skipped (not available at this stage):", e)