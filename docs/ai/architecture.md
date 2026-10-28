# Architecture

All wiring is in `rigpl_erpnext/hooks.py`. Read it first when you trace behaviour.

## hooks.py map

- `required_apps = ["erpnext", "rohit_common"]`: rohit_common owns the State DocType and other links. See `rohit-common.md`.
- `before_migrate`: patches that must run before the schema sync (`patches/v13/fix_long_item_names`, `fix_duplicate_renamed_doctype_tables`).
- `after_migrate`: the website import notice and `utils/role_permission_policy.enforce_role_permission_policy`.
- `before_request` / `before_job`: `overrides/pricing_rule_utils.apply_overrides`. This is a v13 backport of the v14 pricing rule "Has Priority". Remove it at the v14 upgrade.
- `doc_events`: one module per DocType in `rigpl_erpnext/rigpl_erpnext/validations/<doctype>.py` (Item, Sales Order, Sales Invoice, Salary Slip, Stock Entry and more). Manufacturing validations are in `manufacturing_rigpl/validations/`.
- `scheduler_events` (`cron`, `all`, `hourly`, `daily`, `monthly`): jobs in `rigpl_erpnext/rigpl_erpnext/scheduled_tasks/*.py`. Most of them are `enqueue_*` wrappers that start a long job.
- `doctype_js`: desk scripts for standard DocTypes in `public/js/` (Bank Account, Item, Leave Allocation). `app_include_js` loads `public/js/report_formatter.js`.
- Website: `website_generators` (Carrier Tracking), `update_website_context`, `jenv` and `override_whitelisted_methods` point into `website_rigpl/`.

## Modules (`modules.txt`)

| Folder | Contents |
|---|---|
| `rigpl_erpnext/rigpl_erpnext/` | core module: doctype, report, validations, scheduled_tasks, print_format, custom (fixtures JSON) |
| `manufacturing_rigpl/` | Process Sheet, Process Job Card RIGPL, BOM Template RIGPL. See `manufacturing.md` |
| `accounts_rigpl/`, `hr_rigpl/`, `selling_rigpl/`, `stock_rigpl/`, `management_rigpl/` | reports and DocTypes by domain |
| `website_rigpl/` | Frappe website catalog and SEO. See `website.md` |
| `utils/` | shared helpers: `batch_write_utils`, `item_attribute_utils` (`chunks`, attribute pivots), `stock_utils`, `sales_utils`, `report_utils` |
| `overrides/` | ERPNext monkey patches applied per request or job |
| `patches/` | old patches by date, plus `patches/v13/` for new ones |
| `tests/` | app tests. See `testing.md` |

## Configuration

Runtime config is in the RIGPL Settings single (`rigpl_erpnext/rigpl_erpnext/doctype/rigpl_settings`) Check it, and the ERPNext settings, before you hard-code a value.
