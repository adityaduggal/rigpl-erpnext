# Testing

- Tests are in `rigpl_erpnext/tests/test_*.py` (plus a few next to their DocTypes).
- All tests subclass `frappe.tests.utils.FrappeTestCase`. Do not use `unittest.TestCase`. v13 has no `IntegrationTestCase`.
- What the v13 `FrappeTestCase` does: `setUpClass` commits, and `tearDownClass` rolls back. It does not roll back between test methods. If a test must not see data from the one before it, call `frappe.db.rollback()` in `tearDown`. If you override `setUpClass` or `tearDownClass`, call `super()`. Use `_Test RIGPL ...` names.
- A test that inserts a User with `get_doc(...).insert()` commits. In tests `User.on_update` makes a Contact at once, and the ERPNext Contact hook `call_log.link_existing_conversations` calls `frappe.db.commit()`. Insert the User and its `Has Role` rows with `db_insert` (`raw()` in `tests/test_selling_reports.py`), then call `frappe.clear_cache(user=...)`. See `tests/test_report_permissions.py` (#206).
- If `setUp` fails, `tearDown` does not run, so nothing rolls back. Give each test module its own `_Test RIGPL ...` branch or names, so rows left by one module do not change another.
- Helpers in `frappe.tests.utils`:
  - `change_settings(doctype, {...})`: a context manager or decorator that sets a single's fields and restores them afterwards (e.g. RIGPL Settings);
  - `timeout(seconds)`: fails a slow test.
- Fixtures: `tests/test_variant_table.py` has `insert_item(name, variant_of=None, disabled=0, attributes=None)` and `insert_item_price(...)`. Reuse them.
- Query count: wrap batched functions in `rohit_common.utils.query_guard.assert_max_queries(n, test_case=self)`. Base `n` on the number of distinct queries, not on the number of rows.
- `tests/test_whitelisted_js_calls.py` checks that every method called from JS is whitelisted. Run it after you add a `frm.call` or `method:`.
- For a report rewrite, snapshot the output before and after the change and compare (see the MYSQL-Performance issues).

```python
import frappe
from frappe.tests.utils import FrappeTestCase, change_settings


class TestThing(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	@change_settings("RIGPL Settings", {"some_field": 1})
	def test_thing(self):
		...
```

The AI does not run tests. Give the user the command to run from `~/v12`:

```
bench --site dev-rigpl-v12 run-tests --skip-before-tests --app rigpl_erpnext
bench --site dev-rigpl-v12 run-tests --skip-before-tests --module rigpl_erpnext.tests.test_report_utils
```

Use `--module`, not `--doctype`: `--doctype` makes and commits the test records of all linked DocTypes (roles, email accounts and more) and then fails on `test@example.com`, because `mobile_no` is mandatory on this site.

Always use `--skip-before-tests` on dev-rigpl-v12. The ERPNext `before_tests` hook (`erpnext/setup/utils.py`) deletes all rows in Item Price, Leave Allocation, Leave Application and Salary Slip, and commits. A test rollback does not undo it.
