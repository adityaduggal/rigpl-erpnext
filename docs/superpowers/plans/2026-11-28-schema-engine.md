# Schema Engine Implementation Plan (#260)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A website manager makes a schema.org node in Desk, and the page outputs it as JSON-LD with no code change.

**Architecture:** DocType `Schema Template` with child table `Schema Template Property`. A new package `website_rigpl/seo/` evaluates each expression in its own sandbox, builds one `@graph`, and `item_page.update_website_context` appends it to `context.head_include`. The expressions see plain data only.

**Tech Stack:** Frappe 13.58, Jinja2 3.0.3 (`ImmutableSandboxedEnvironment`), Python 3.8.

**Spec:** `docs/superpowers/specs/2026-11-28-website-seo-schema-design.md` (§5.2, §6, §9, D2, D8). Issue #260.

## Global Constraints

- Read `.claude/skills/rigpl-v13/SKILL.md` before code. Python 3.8 typing. Tests subclass `FrappeTestCase`.
- Never run `bench migrate`, `backup` or `run-tests`. The user runs them.
- Never commit without the user's yes. Each "Commit" step means: show the diff and ask.
- Module `Website-RIGPL`. Only the role Website Manager has permissions. Guest has no read.
- The expression sandbox has no `frappe` object and no Document object (D8).
- The output uses `json.dumps`. Do not build JSON with strings.
- Change no Frappe or ERPNext file. No fixtures.
- Test command (run from `~/v12`; the branch must be the checked-out code of the bench app):
  `bench --site dev-rigpl-v12 run-tests --skip-before-tests --skip-test-records --module rigpl_erpnext.tests.test_seo_schema`

## Scope

- This issue outputs the templates with `applies_to` = `Site` on every page. SEO Rule (#261), navigation (#264) and page blocks (#269) select the other values.
- The context has `site`, `page` and `doc`. `item` is `{}`, `variants` is `[]`, `common` is `[]`, `block` is `{}`, `nav` is `{}`. Later issues fill them (#262, #264, #265, #277).
- No Redis graph cache (design §9). It belongs to #265.
- No seed records (#263).

## Review Focus

1. A value that contains `</script>` (item name, page title): the script tag must not close early.
2. A linked template that links back to itself: the page renders, one Error Log row, no recursion error.
3. A typo in an expression (`doc.web_item_nme`): the property drops and logs. It must not output an empty string.
4. A bad property on a `no_cache` page (Website Item) that many visitors open: one Error Log row per hour, not one per view.
5. A failure outside one expression (broken child row, import error): the page still renders.

## File Structure

All paths are below `rigpl_erpnext/`.

| File | Responsibility |
|---|---|
| `website_rigpl/doctype/__init__.py` | Package. |
| `website_rigpl/doctype/schema_template/{__init__.py,schema_template.json,schema_template.py,schema_template.js}` | DocType, save checks, Preview button. |
| `website_rigpl/doctype/schema_template_property/{__init__.py,schema_template_property.json,schema_template_property.py}` | Child table. |
| `website_rigpl/seo/__init__.py` | Package. |
| `website_rigpl/seo/sandbox.py` | Evaluate one Jinja source. Syntax check. |
| `website_rigpl/seo/builder.py` | Templates to nodes, `@graph`, script tag, error log. |
| `website_rigpl/seo/context.py` | Website context to the SEO context. Route to website context. |
| `website_rigpl/seo/required.py` | Required properties per type. |
| `website_rigpl/item_page.py` | Wiring. |
| `hooks.py` | `website_clear_cache`. |
| `tests/test_seo_schema.py` | All tests. |
| `docs/user/website_seo_schema.md` | User guide (the folder is `rigpl_erpnext/docs/user/`). |
| `utils/guide_utils.py` | Register the guide. |

---

### Task 1: Expression sandbox

**Files:**
- Create: `website_rigpl/seo/__init__.py`, `website_rigpl/seo/sandbox.py`
- Test: `tests/test_seo_schema.py`

**Interfaces:**
- Produces:
  - `evaluate(source: str, variables: dict) -> Any`
  - `check_syntax(source: str) -> None` (raises `jinja2.TemplateSyntaxError`)

**Rules of `evaluate`:**
- Empty or blank source: `None`.
- One `{{ x }}` that is the whole stripped source, or a source with no `{{` and no `{%`: compile `x` with `compile_expression(x, undefined_to_none=False)` and return the native value.
- Any other source: render it and return the stripped string.
- The environment is `ImmutableSandboxedEnvironment(undefined=StrictUndefined)`. It has no loader. Remove the globals `range`, `lipsum`, `cycler`, `joiner`, `namespace`, `dict` and add none.
- An `Undefined` result raises `UndefinedError`.
- Filters: the Jinja built-ins, plus `plain_text` (`frappe.utils.strip_html_tags`, then collapse white space) and `abs_url` (`frappe.utils.get_url` for a relative path, URL-encoded with `urllib.parse.quote(url, safe=":/?&=#%")`).

- [ ] **Step 1: Write the failing tests** (class `TestSandbox`)

```python
def test_single_expression_returns_native_value(self):
    self.assertEqual(evaluate("{{ doc.qty }}", {"doc": {"qty": 5}}), 5)
    self.assertEqual(evaluate("doc.tags", {"doc": {"tags": ["a", "b"]}}), ["a", "b"])
    self.assertEqual(evaluate("{{ doc.sku }}", {"doc": {"sku": "0012"}}), "0012")

def test_mixed_source_returns_string(self):
    self.assertEqual(evaluate("{{ page.url }}#product", {"page": {"url": "http://x/a"}}), "http://x/a#product")
    self.assertEqual(evaluate("{{ 1 }}-{{ 2 }}", {}), "1-2")

def test_undefined_name_raises(self):
    for source in ("{{ doc.web_item_nme }}", "x {{ doc.web_item_nme }}", "nothing"):
        with self.assertRaises(UndefinedError):
            evaluate(source, {"doc": {}})

def test_sandbox_has_no_frappe_and_no_writes(self):
    with self.assertRaises(UndefinedError):
        evaluate("frappe.db", {})
    for source in ("doc.update({'a': 1})", "doc.__class__.__mro__"):
        with self.assertRaises((SecurityError, UndefinedError)):
            evaluate(source, {"doc": {}})

def test_check_syntax(self):
    check_syntax("{{ page.url }}#x")
    check_syntax("doc.name if doc else ''")
    for source in ("{{ page.url ", "doc.name if"):
        with self.assertRaises(TemplateSyntaxError):
            check_syntax(source)
```

- [ ] **Step 2: Ask the user to run the test command.** Expected: FAIL, `ModuleNotFoundError: rigpl_erpnext.website_rigpl.seo`.
- [ ] **Step 3: Implement `sandbox.py`.** Use `env.parse(source)` for the syntax check of mixed sources and `compile_expression` for expressions.
- [ ] **Step 4: Ask the user to run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: SEO expression sandbox (#260)`

---

### Task 2: DocTypes and permissions

**Files:**
- Create: the files of `website_rigpl/doctype/` in File Structure (not the `.js`; controller classes are empty here)
- Test: `tests/test_seo_schema.py`

**Interfaces:**
- Produces: DocType `Schema Template`, autoname `field:template_name`, and child `Schema Template Property`.

`Schema Template` fields, in this order:

| fieldname | type | options / default |
|---|---|---|
| `template_name` | Data | reqd, unique |
| `schema_type` | Data | reqd |
| `enabled` | Check | default 1 |
| `merchant_listing` | Check | `depends_on`: `schema_type` is Product or Offer |
| `applies_to` | Select | `Site`, `Page Type`, `Web Template`, `Navigation`, `Breadcrumb`, `Component`; default `Component`; reqd |
| `web_template` | Link Web Template | shown and mandatory when `applies_to` = `Web Template` |
| `sample_route` | Data | empty: the home page |
| `id_expression` | Code (Jinja) | |
| `condition` | Code (Jinja) | |
| `iterate_over` | Code (Jinja) | |
| `properties` | Table | Schema Template Property |
| `help` | Small Text | |

`Schema Template Property` fields: `property` (Data, reqd, in list), `value_type` (Select `Expression`, `Constant`, `Template`, `Template List`; default `Expression`; reqd, in list), `value` (Code, Jinja, in list), `linked_template` (Link Schema Template, shown and mandatory for `Template` and `Template List`), `condition` (Code, Jinja), `required` (Check, in list).

Permissions: one row, role `Website Manager`, read, write, create, delete, report, export. Every field has a description. `track_changes` = 1.

- [ ] **Step 1: Write the failing test** (class `TestPermissions`)

```python
def test_only_website_manager_has_permissions(self):
    meta = frappe.get_meta("Schema Template")
    self.assertEqual({p.role for p in meta.permissions}, {"Website Manager"})
    self.assertFalse(frappe.has_permission("Schema Template", "read", user="Guest"))
```

- [ ] **Step 2: Write the DocType files.** Match the JSON layout of `rigpl_erpnext/doctype/daily_call_details/`.
- [ ] **Step 3: Ask the user to run** `bench --site dev-rigpl-v12 migrate`, then the tests. Expected: PASS.
- [ ] **Step 4: Commit** `feat: Schema Template DocTypes (#260)`

---

### Task 3: Graph builder

**Files:**
- Create: `website_rigpl/seo/builder.py`
- Modify: `hooks.py` (add `website_clear_cache = "rigpl_erpnext.website_rigpl.seo.builder.clear_template_cache"`)
- Test: `tests/test_seo_schema.py`

**Interfaces:**
- Consumes: `sandbox.evaluate`.
- Produces:
  - `get_template_names(applies_to: str) -> List[str]`: enabled names, ordered by name, cached in the Redis hash `rigpl_schema_templates` (field = `applies_to`).
  - `clear_template_cache(path=None) -> None`
  - `build_nodes(templates: List[Document], variables: dict, errors: List[BuildError]) -> List[dict]`
  - `build_graph(templates, variables, errors) -> Optional[dict]`: `{"@context": "https://schema.org", "@graph": [...]}`, or `None` with no nodes.
  - `to_script(graph: dict) -> str`
  - `BuildError = namedtuple("BuildError", "template property message")`
  - `log_errors(errors: List[BuildError], route: str) -> None`

The builder does not log. It appends to `errors`. `log_errors` writes.

Rules:
- Template: a disabled template gives no node. `iterate_over` gives one node per element, with `row` in the variables. A value that is not a list or tuple is an error (`property` = `iterate_over`). `condition` false: no node.
- Node: `@type` = `schema_type`, `@id` from `id_expression` when it has a value. A node with no property and no `@id` is dropped.
- Property: `condition` false: skip. `Constant`: the literal `value`. `Expression`: `evaluate`. `Template`: the nodes of `linked_template` (one node: the object; more: the list). `Template List`: always a list. Linked nodes see the `row` of the parent unless they iterate. A linked node with only `@id` stays (a reference).
- Drop `None`, `""`, `[]`, `{}`. Keep `0` and `False`.
- Two rows with the same property name: the later value that is not empty wins.
- An exception in a property drops that property only. An exception in `condition`, `iterate_over` or `id_expression` appends an error; the first two drop the node, `id_expression` drops only the `@id`.
- A linked template that is already in the current chain is an error and is skipped.
- Top-level nodes with the same `@id` merge into the first one. The first value of each key wins.
- `to_script`: `json.dumps(graph, ensure_ascii=False, default=...)`; date and datetime use `isoformat()`, `Decimal` uses `float`, other types raise. Replace `<`, `>`, `&` with `<`, `>`, `&`. Wrap in `<script type="application/ld+json">`. A value that does not serialise must not stop the page: check each property value when it is built, and report it as a property error.
- `log_errors`: for each error, skip it when the Redis key `rigpl_schema_error|template|property|route` exists; else `frappe.log_error(message, title)` with title `Schema error: {template} {route}` cut to 140 characters, set the key for 3600 s, and set `frappe.local.flags.commit = True` (a GET request does not commit without it, `frappe/app.py:313`).
- Load templates with `frappe.get_cached_doc("Schema Template", name)`.

- [ ] **Step 1: Write the failing tests** (class `TestBuilder`). Add the helper that later tasks use:

```python
def make_template(name, properties, **values):
    """Raw rows: skips the save checks, so a test can store a bad expression."""
```

It builds `frappe.get_doc({... "template_name": "_Test RIGPL " + name, "schema_type": "Thing", "applies_to": "Component", ...})`, calls `db_insert` on the doc and each child, clears both caches, and returns the doc. `properties` is a list of `(property, value_type, value, extra_dict)`.

Tests and their assertions:

- `test_bad_property_drops_only_itself`: properties `name` = `{{ doc.title }}`, `sku` = `{{ doc.nope }}` → node is `{"@type": "Thing", "name": "T"}`; `errors[0].property == "sku"`.
- `test_output_parses_and_cannot_close_the_script`: title `a</script><b>&` → the script has one `</script>`; `json.loads` of the body returns the same title.
- `test_empty_values_dropped_zero_kept`: `price` = `{{ 0 }}` stays; `""` and `[]` go.
- `test_iterate_over_and_condition`: three rows, condition `row.n > 1` on the property list → expected nodes; a template `condition` of `false` → `[]`; `iterate_over` = `{{ 5 }}` → `[]` and one error.
- `test_linked_template_and_list`: `Template` gives an object, `Template List` with one row gives a list of one.
- `test_cycle_is_an_error_not_a_crash`: A links B, B links A → A node returns, one error that names the cycle.
- `test_same_id_merges`: two templates with `@id` `x#a` → one node with both properties.
- `test_unserialisable_value_drops_property`: `value` = `{{ doc.items }}` with a plain dict `doc` (a method) → property dropped, one error.
- `test_log_errors_once_per_hour`: call `log_errors` twice with the same error and route → Error Log count rises by 1; the row text has the template name; the route is in `method`.
- `test_cached_build_runs_no_query`: warm with one `get_template_names("Site")` + `build_graph`, then inside `assert_max_queries(0, test_case=self)` run both again.

- [ ] **Step 2: Ask the user to run the tests.** Expected: FAIL, import error.
- [ ] **Step 3: Implement `builder.py` and the hook line.**
- [ ] **Step 4: Ask the user to run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: schema graph builder (#260)`

---

### Task 4: SEO context and page output

**Files:**
- Create: `website_rigpl/seo/context.py`
- Modify: `website_rigpl/item_page.py` (`update_website_context`)
- Test: `tests/test_seo_schema.py`

**Interfaces:**
- Consumes: `builder.get_template_names`, `build_graph`, `to_script`, `log_errors`.
- Produces:
  - `context.build_variables(web_context: dict) -> dict`
  - `context.get_route_context(route: str) -> dict`: the website context of a published route; throws `frappe.PageDoesNotExistError` for an unknown route.
  - `item_page.add_schema_graph(context, values: dict) -> None`

`build_variables`:

```python
{
    "site": {"url": get_url(), "name": context.get("app_name") or ""},
    "page": {"route": route, "url": get_url(route), "title": context.get("title") or "",
             "parents": plain(parents), "h1": context.get("title") or ""},
    "doc": plain(doc.as_dict()) if doc else {},
    "item": {}, "variants": [], "common": [], "block": {}, "nav": {},
}
```

`plain` copies dicts and lists recursively and turns each Document into a plain dict, so no object with a write method reaches the sandbox. `route` is `context["route"]` without the leading `/`.

Wiring: `update_website_context` runs the page handler as now, then `add_schema_graph`. `add_schema_graph` reads the `Site` template names first and returns at once when there are none. It uses `values.get("parents", context.get("parents"))`, and sets `values["head_include"]` = existing `head_include` + script. It returns at once when `frappe.flags.rigpl_seo_preview` is set. A `try` around the whole body logs with `log_errors([BuildError("", "", traceback)], route)` and leaves the page as it was.

`get_route_context`: save `frappe.local.request` (it may not exist), `frappe.utils.set_request(method="GET", path="/" + route)`, set `frappe.flags.rigpl_seo_preview`, call `frappe.website.context.get_context(route)`, and restore both in `finally`. Resolve an empty route with `frappe.website.utils.get_home_page()`. Set `frappe.local.no_cache` for the call and restore it, so a preview does not fill the page cache.

- [ ] **Step 1: Write the failing tests** (class `TestPageOutput`, with a published `_Test RIGPL` Web Page made in `setUp`, `frappe.db.rollback()` and `clear_template_cache()` in `tearDown`)

- `test_site_template_is_in_the_page`: a `Site` template `name` = `{{ page.title }}`; `frappe.utils.get_html_for_route(route)` has one `application/ld+json` script whose graph has the title.
- `test_bad_property_page_still_renders`: the page returns 200, the good property is there, an Error Log row exists with the template name.
- `test_template_change_shows_after_cache_clear`: render, change the value with `frappe.db.set_value` on the child row, run `frappe.clear_cache()` and `frappe.website.render.clear_cache()`, render → new value.
- `test_engine_failure_keeps_the_page`: patch `builder.build_graph` to raise → the page returns 200 with no script.
- `test_context_has_no_document_objects`: `build_variables({"doc": web_page, "route": r})["doc"]` is a dict, and no nested value is a `Document`.
- `test_item_page_values_are_kept`: with `head_include` = `<meta name="x">` in the context, the result has both the meta and the script.

- [ ] **Step 2: Ask the user to run the tests.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Ask the user to run the tests, and** `--module rigpl_erpnext.tests.test_variant_table`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: output the schema graph on website pages (#260)`

---

### Task 5: Save checks and required properties

**Files:**
- Create: `website_rigpl/seo/required.py`
- Modify: `website_rigpl/doctype/schema_template/schema_template.py`
- Test: `tests/test_seo_schema.py`

**Interfaces:**
- Consumes: `sandbox.check_syntax`, `context.get_route_context`, `context.build_variables`, `builder.build_nodes`.
- Produces:
  - `required.required_groups(schema_type: str, merchant_listing: bool) -> List[Tuple[str, ...]]`: each tuple is "one of".
  - `required.missing(groups, properties: Iterable[str]) -> List[str]`: labels such as `offers or review or aggregateRating`.
  - `SchemaTemplate.render_route(route: str) -> Tuple[Optional[dict], List[BuildError]]`

Groups:

| Type | Groups |
|---|---|
| Product, ProductGroup | `name`; one of `offers`, `review`, `aggregateRating` |
| Product, ProductGroup with merchant listing | `name`; `image`; `offers` |
| Offer | one of `price`, `priceSpecification` |
| Offer with merchant listing | one of `price`, `priceSpecification`; one of `priceCurrency`, `priceSpecification` |
| BreadcrumbList | `itemListElement` |
| Organization | `name`; `url` |
| Article, BlogPosting, NewsArticle | `headline` |
| LocalBusiness | `name`; `address` |
| VideoObject | `name`; `thumbnailUrl`; `uploadDate` |

`ProductGroup` without merchant listing needs only `name`: its offers are on the variants. Other types: no groups.

`validate` of the controller, in order:
1. Strip `property`. Reject a name that starts with `@`.
2. `check_syntax` on `id_expression`, `condition`, `iterate_over`, each `condition`, and each `value` of type `Expression`. A syntax error throws, with the field or the row number. This runs for disabled templates too.
3. When enabled: a missing type group throws.
4. When enabled: render the sample route (`render_route(self.sample_route or "")`). A row marked `required` whose value is missing from every node of this template throws, and the message has the build error of that row if there is one. Other build errors show as an orange `msgprint`. No node (the condition is false for this route): a `msgprint` says that the required values were not checked. An unknown `sample_route` throws.

`render_route` builds from `self` (the unsaved document), not from the cache, and also when `self.enabled` is 0. It does not call `log_errors`.

`on_update` and `on_trash`: `clear_template_cache()` and `frappe.website.render.clear_cache()`.

- [ ] **Step 1: Write the failing tests** (class `TestSaveChecks`, real `doc.insert()`)

- `test_syntax_error_blocks_save`
- `test_missing_type_property_blocks_save`: Offer with only `url` → `ValidationError` that has `price`.
- `test_product_needs_one_of_offers_review_rating`: with `name` and `review` → saves.
- `test_merchant_listing_needs_image`
- `test_required_row_empty_on_sample_route_blocks_save`
- `test_bad_optional_property_saves_with_warning`: saved; `frappe.get_message_log()` names the property.
- `test_disabled_template_saves_incomplete`
- `test_save_clears_template_cache`: warm `get_template_names("Site")`, insert a `Site` template, the new name is in the list.

- [ ] **Step 2: Ask the user to run the tests.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Ask the user to run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: Schema Template save checks (#260)`

---

### Task 6: Preview button and user guide

**Files:**
- Create: `website_rigpl/doctype/schema_template/schema_template.js`, `docs/user/website_seo_schema.md`
- Modify: `website_rigpl/doctype/schema_template/schema_template.py`, `utils/guide_utils.py`
- Test: `tests/test_seo_schema.py`

**Interfaces:**
- Consumes: `SchemaTemplate.render_route`, `rigpl_erpnext.show_user_guide(guide, title)`.
- Produces: whitelisted `preview(name: str, route: str = None) -> dict` → `{"json": str, "errors": [{"template": str, "property": str, "message": str}]}`.

`preview` calls `frappe.has_permission("Schema Template", "write", throw=True)`. `json` is the graph with `indent=2`, or `""` with no node. It previews the saved document.

Desk: on a saved form, button **Preview** → `frappe.prompt` for `route` (default `frm.doc.sample_route`) → a dialog with the JSON in `<pre>` and the errors, both escaped with `frappe.utils.escape_html`. Button **Help** → `rigpl_erpnext.show_user_guide("website_seo_schema", __("Schema Templates"))`. Add `"website_seo_schema": "Schema Template"` to `GUIDES` in `utils/guide_utils.py`.

The guide covers: what a Schema Template does, each field, the two expression forms, the context keys of this issue, the filters `plain_text` and `abs_url`, `row`, errors and the Error Log, Preview, `doc.get("items")` for a child table named `items`, and one complete `WebPage` example.

- [ ] **Step 1: Write the failing tests** (class `TestPreview`)

- `test_preview_returns_graph_and_errors`
- `test_preview_needs_write_permission`: `frappe.set_user("Guest")` → `frappe.PermissionError`; reset the user in `finally`.
- `test_preview_unknown_route_throws`

- [ ] **Step 2: Ask the user to run the tests.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Ask the user to run the tests, and** `--module rigpl_erpnext.tests.test_whitelisted_js_calls`. Expected: PASS.
- [ ] **Step 5: Desk check by the user:** `bench --site dev-rigpl-v12 clear-cache`, make a `Site` template, press Preview, open a page.
- [ ] **Step 6: Commit** `feat: Schema Template preview and user guide (#260)`
