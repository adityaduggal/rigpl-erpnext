---
name: rigpl-v13
description: House rules for code in rigpl_erpnext (Frappe/ERPNext v13, Python 3.8). Use before you write or change a DocType, controller, validation, report, patch, hooks.py entry, scheduled task, query, test or desk JS in this repo. Overrides frappe-app-dev where they conflict.
---

# rigpl-v13

The stack is Frappe 13.58, ERPNext 13.55 and Python 3.8, with `rohit_common` as a required app.
The bench is at `~/v12` and the dev site is `dev-rigpl-v12`.

## v13 deltas (these override frappe-app-dev, which targets v15+)

- Tests: new tests subclass `frappe.tests.utils.FrappeTestCase`, not `unittest.TestCase`. v13 has no `IntegrationTestCase`. See `docs/ai/testing.md`.
- API: there is no `/api/v2`. Use `/api/method/<dotted.path>` and `/api/resource`.
- `@frappe.whitelist()` does not validate type hints. Cast and check arguments yourself (`cint`, `flt`, `frappe.parse_json`).
- Desk JS that a form or list calls must be whitelisted. v13 refuses non-whitelisted methods (#166).
- Python 3.8: use `typing.List/Dict/Optional`. Do not use `list[int]`, `X | None` or `match`.
- `frappe.qb` (pypika) exists. Use it for grouped and `IN` queries. There is no `frappe.qb.get_query`.
- `frappe.get_cached_doc` uses the cache only with 2 args:
  `frappe.get_cached_doc("RIGPL Settings", "RIGPL Settings")` or `frappe.get_cached_value(...)`.
- `frappe.db.bulk_insert` drops the last row. Use `bulk_insert_rows` (see below).
- `job_name` does not dedupe in v13. Long cron jobs use `enqueue_once` from rohit_common.
- JS is plain desk scripts in `public/js/`, loaded by `doctype_js` / `app_include_js` in `hooks.py`. Do not add bundles.
- Website Theme SCSS compiles with node-sass, which needs Node 14 (`~/.nvm/versions/node/v14.21.3`). Node 22 fails and deletes the theme CSS.

## House rules

1. **Reuse first.** Find the ERPNext/Frappe function that already does the job, then check rohit_common (`docs/ai/rohit-common.md`). Call it or wrap it (hooks, `override_whitelisted_methods`, context changes after `get_context`). Copy ERPNext's formula only when a direct call is not possible, such as batching, and cite the source file and lines.
2. **No N+1 reads or writes.**
   - Read with grouped `frappe.qb` / `frappe.get_all(... ["name", "in", names])` per chunk (`chunks()` in `utils/item_attribute_utils.py`), and look up rows in a dict.
   - Write long lists with `utils/batch_write_utils.py`: `bulk_set_values`, `bulk_insert_rows`, `bulk_insert_versions` (keeps Version history), `clear_document_cache`.
   - Keep single-item functions as thin wrappers over the batch ones.
   - `frappe.get_doc` per row is fine only when the row must run hooks (save, submit, cancel).
   - Guard batch functions in tests with `assert_max_queries`.
3. **Settings** go in the RIGPL Settings single (`rigpl_erpnext/doctype/rigpl_settings`), one collapsible Section Break per area. Do not add new settings DocTypes. Read what ERPNext settings already hold. Give empty fields defaults in code so no patch is needed.
4. **Reports**: show 0 as an empty cell. Do both:
   - server side, wrap each row in `blank_zeros(row)` (`utils/report_utils.py`);
   - JS side, set `"formatter": rigpl_erpnext.report.blank_zero_formatter`.
5. **SQL**: pass values as parameters (`frappe.db.sql(q, {"k": v})`). Interpolate only fixed table or column names.
6. **Patches**: add them under `patches/v13/` and append the dotted path to `patches.txt`. Patches that must run before the schema sync go in `before_migrate` in `hooks.py`.
7. **Style**: match the file you edit. Indent is tabs in some files and 4 spaces in others, so do not reformat. Keep the comment density low. No linter is installed in `env`.
8. **Bench**: never run `bench migrate`, `backup` or `run-tests`. Give the user the commands. Read-only `bench --site dev-rigpl-v12 mariadb` SELECT/SHOW and `console` reads are fine.

## Skills to use with this one

- Plan or design: `superpowers:brainstorming`, then `superpowers:writing-plans`.
- Write code: `superpowers:test-driven-development` and `code-style`. Use `frappe-app-dev` only for API shapes, and apply the v13 deltas above.
- Review: `frappe-code-review`.
- Commits, PRs and docs: `technical-writing`. Use conventional prefixes (`feat:`, `fix:`, `perf:`) and reference the issue number.

## Topic notes (read only the one you need)

- `docs/ai/architecture.md`: hooks.py map, modules, where validations and crons live.
- `docs/ai/rohit-common.md`: what this app uses from rohit_common and which of its helpers to reuse.
- `docs/ai/testing.md`: test layout, fixtures, query guard, test commands for the user.
- `docs/ai/manufacturing.md`: Process Sheet / Job Card pipeline and BOM Templates.
- `docs/ai/website.md`: website module and which section of its README to open.
- `docs/ai/github.md`: epics, projects and labels.
