# Manufacturing (manufacturing_rigpl)

- DocTypes: Process Sheet (+ Process Sheet Items), Process Job Card RIGPL, BOM Template RIGPL, Create Bulk Process Sheet, Made to Order Item Attributes, Workstation Operation.
- Logic: `manufacturing_rigpl/utils/{process_sheet_utils,job_card_utils,manufacturing_utils}.py`.
- Crons in `rigpl_erpnext/scheduled_tasks/`:
  - `process_sheet_update`: batched reads, writes only what changed;
  - `create_new_job_cards`: short closes Job Cards of delivered or closed Sales Orders, and deletes Job Cards without a Sales Order that still have a zero qty. One batched Sales Order read;
  - `update_job_card_status`;
  - `auto_reorder` (ROL).
- Batch read helpers: `utils/stock_utils.get_quantities_for_items`, `utils/sales_utils.get_open_so_lines` and `manufacturing_rigpl/utils/batch_qty_utils.py` (Bins, operations, Job Card rows, pending Process Sheet operations).
- `update_job_card_status` calculates the `validate` fields of all draft Job Cards with these reads and writes only the changes (`bulk_set_fields`). A Job Card gets a full `save()` only when `total_qty`, `for_quantity` or its structure changes. The single-Job-Card functions in `job_card_utils.py` take the same pre-loaded inputs as optional arguments.
- Reports: `manufacturing_rigpl/report/` (bom_templates, items_for_production, items_without_bom_templates, process_sheet_analysis, production_and_planning_report_rigpl).

Work in progress: epic #165, "Manufacturing crons and BOM Templates", a sub-issue of #143.
- Order: #166 → #145 → #160 → (#149, #146, #147) → #161, and #162 → #163 → #164.
- Target design: one 30-minute long-queue pipeline that replaces the `all` and hourly hooks.
- BOM Templates get multi-value rules. Old templates are disabled, never deleted.
