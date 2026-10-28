# What rigpl_erpnext uses from rohit_common (v13)

rohit_common is at `../rohit_common` (branch `version-13`). Its own guide is `../rohit_common/CLAUDE.md` plus `docs/claude/*.md`. Read `architecture-hooks.md` there before you add a `doc_events` entry for a DocType that rohit_common already hooks, such as Sales Invoice, Address or Contact.

## Imported today

| Import | Used for |
|---|---|
| `rohit_common.rohit_common.validations.sales_invoice.check_validated_gstin` | GSTIN check on party docs |
| `rohit_common.utils.rohit_common_utils`: `replace_java_chars`, `fn_check_digit`, `fn_next_string`, `check_dynamic_link`, `check_sales_taxes_integrity`, `get_email_id` | text clean-up, check digits, link and tax checks |
| `rohit_common.utils.email_utils.comma_email_validations` | CSV email fields |
| `rohit_common.rohit_common.validations.file.delete_file_dt` | attachment clean-up |
| `rohit_common.rohit_common.validations.docshare`: `get_docshare_from_dt`, `create_docshare` | automated DocShare |
| `rohit_common.utils.address_utils.rigpl_address_query`, `contact_utils.rigpl_contact_query` | link-field search queries |

## Reuse these before you write your own

- `utils/query_guard.assert_max_queries(limit, test_case=self)`: test context manager. It fails when a block runs more SQL than `limit`. Use it to pin batched code against N+1.
- `utils/background_doc_processing.enqueue_once(method, queue, timeout)`: use it for cron jobs that start a long job, because v13 `job_name` does not dedupe.
- `utils/background_doc_processing.unmark_failed_doc`, `short_error`: lets a sweep job skip one failing doc and continue.
- `utils/rohit_common_utils.apply_batched_field_update(doctype, fieldname, updates)`: batched `UPDATE` with `CASE`.
- `utils/rohit_common_utils.rebuild_tree(doctype, parent_field, group_field)`: nested-set rebuild with batched writes.
- `utils/common.update_child_table(doc, table_name, row_list)`.
- `utils/accounts_utils`: batched GST helpers (`get_hsn_summary_for_invoices`, `get_si_taxes_map`, `get_jv_party_map`, `get_party_addresses`).

## DocTypes

rigpl links to State and Transporters. rohit_common also owns Rohit Settings, Rohit GST Settings, Global Emails and eWay Bill. Rohit Settings drives rohit_common's own jobs, such as file and Version clean-up and e-invoicing, which rigpl does not read.

Do not change rohit_common from this repo. Raise the change in its own repo (`erpnext-apps/rohit-common`).
