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
- Order: #166 → #145 → #160 → (#149, #146, #147) → #161, and #162 → #183 → #163 → #164 → #185. #184 after #162 and #183. #186 in parallel.
- #183 RM rows must pass the template RM rules. #184 RM rows ranked by Adjusted RM Cost (stock age discount in RIGPL Settings); a submit with a lower-rank RM sets `best_rm_bypassed` and adds a comment (no block). #163 process-based model: rule rows of the same text attribute are OR, different attributes and numeric rules AND (`group_text_rules`, used by the FG matcher `get_fg_failures` and RM/WIP `get_items_for_rules`); `value_source` Same as FG / Same as RM (WIP only); `fg_rm_map` (child `FG RM Grade Map`) defines RM values; BOM Operation condition (`operation_applies`, in `get_routing`); `explain_bom_template_match` for the Process Sheet dialog. #164 merge tools in `utils/bom_template_merge_utils.py` (work/process signatures, merge check, Disable Similar Templates, `merged_into`), reports BOM Template Overlaps, RM Wastage Analysis, RM Cost of Items Made (`utils/rm_cost_utils.py`, SLE cost by Job Card); scrap estimate from the operation row (`scrap_item/scrap_qty_formula/scrap_warehouse`) posted in the Job Card Stock Entry; RM excess by value (`get_rm_excess`, RIGPL Settings `min_rm_excess_value`, `rm_excess_percent`) replaces the % length check. #185 merge message on Process Sheet submit (`get_merge_hint` > pure `merge_hint_html`): pass 1 groups by `work_signature`; pass 2 groups the rest without operations and suggests an Operation Condition (`suggest_operation_condition`). #186 BOM Template guide as a Help Article.
- Target design: one 30-minute long-queue pipeline that replaces the `all` and hourly hooks.
- BOM Templates get multi-value rules. Old templates are disabled, never deleted.
- User guides: `rigpl_erpnext/docs/user/{bom_templates,process_sheet}.md`, shown in a desk dialog by `utils/guide_utils.get_user_guide` (login only, not a web page). Update them with each change to the BOM Template or Process Sheet flow (#186).
