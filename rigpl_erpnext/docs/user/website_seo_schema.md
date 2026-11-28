# Schema Templates

A Schema Template makes one schema.org node, or a list of nodes. The website writes the nodes into the page as JSON-LD. Search engines and AI assistants read it. A change needs no code deploy.

Only the role **Website Manager** can open Schema Templates.

## Which templates a page outputs

Each page outputs the enabled templates with **Applies To** = **Site**. A page also outputs the **Page Type** templates that its **SEO Rule** lists. A **Component** template appears only inside another template. The values **Web Template**, **Navigation** and **Breadcrumb** have no effect yet.

## Fields

| Field | Use |
|---|---|
| Template Name | The unique name. |
| Schema Type | The schema.org type, for example `Product` or `Offer`. It becomes `@type`. |
| Enabled | Off: no page outputs the node. |
| Merchant Listing | Also check the properties of a Google merchant listing. |
| Applies To | See above. |
| Web Template | Necessary when Applies To is Web Template. |
| Sample Route | The page that the save check renders. Empty: the home page. |
| ID Expression | The `@id` of the node, for example `{{ page.url }}#webpage`. Nodes with the same `@id` become one node. |
| Condition | An empty or false result: no node. |
| Iterate Over | An expression that gives a list. The template makes one node for each element. The expressions read the element as `row`. |
| Properties | One row for each property. |
| Help | Your notes. |

## Property rows

| Value Type | Value |
|---|---|
| Expression | An expression. |
| Constant | The text as it is. |
| Template | The node of the **Linked Template**. |
| Template List | The nodes of the Linked Template, always as a list. |

A row with a false **Condition** gives no property. An empty value gives no property. The number `0` stays.

Tick **Required** when the save must fail if the property has no value on the Sample Route.

## Expressions

There are two forms:

- One expression, with or without `{{ }}`: `doc.title` or `{{ doc.title }}`. The result keeps its type: a number stays a number and a list stays a list.
- Text with expressions: `{{ page.url }}#webpage`. The result is text.

## Values that you can read

| Name | Content |
|---|---|
| `site.url`, `site.name` | The site address and the app name of Website Settings. |
| `page.route`, `page.url`, `page.title`, `page.h1`, `page.parents` | The page. `page.title` has the title prefix of Website Settings, `page.h1` does not. `page.parents` is the breadcrumb list. |
| `doc` | The fields of the page document. It is empty on a page that has no document. |
| `row` | The element of Iterate Over. |

`item`, `variants`, `common`, `block` and `nav` are empty now.

A name that does not exist is an error. For a field that can be absent, use `doc.get("fieldname")`. For a child table with the name `items`, use `doc.get("items")`.

Expressions cannot read the database and cannot change data.

## Filters

All standard Jinja filters work. There are two more:

- `plain_text` removes HTML and extra spaces: `doc.description | plain_text | truncate(500)`
- `abs_url` makes a full, encoded address: `doc.meta_image | abs_url`

## Errors

A save fails when:

- an expression has a syntax error;
- an enabled template does not have a property that its type needs;
- a **Required** row has no value on the Sample Route.

Other errors on the Sample Route show a warning.

On a live page, an expression with an error removes only its own property. The page still shows. The **Error Log** gets a row with the title `Schema error: <template> <route>`, at most one time each hour for each property and page.

## Preview

Open a saved template and click **Preview**. Type a route. The dialog shows the JSON-LD of this template and its errors. The preview and the save check read the page as a visitor who is not logged in.

## Example: WebPage

| Field | Value |
|---|---|
| Template Name | WebPage |
| Schema Type | WebPage |
| Applies To | Site |
| ID Expression | `{{ page.url }}#webpage` |

| Property | Value Type | Value |
|---|---|---|
| url | Expression | `page.url` |
| name | Expression | `page.h1` |
| dateModified | Expression | `doc.get("modified")` |
