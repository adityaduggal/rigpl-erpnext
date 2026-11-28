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

## Examples for the pages of this website

Make the templates in this order. A template that links to another template needs that template first. Leave **Condition** and **Iterate Over** empty unless the example gives them.

Replace each text between `<` and `>` with the real company data.

## Example 1. Company address

Template Name `Company Address`, Schema Type `PostalAddress`, Applies To `Component`.

| Property | Value Type | Value |
|---|---|---|
| `streetAddress` | Constant | `<plot number, street, area>` |
| `addressLocality` | Constant | `<city>` |
| `addressRegion` | Constant | `<state>` |
| `postalCode` | Constant | `<PIN code>` |
| `addressCountry` | Constant | `IN` |

## Example 2. Company, on every page

Template Name `Company`, Schema Type `Organization`, Applies To `Site`, ID Expression `{{ site.url }}/#organization`.

| Property | Value Type | Value | Required |
|---|---|---|---|
| `name` | Constant | `Rohit Cutting Tools` | yes |
| `url` | Expression | `site.url` | yes |
| `logo` | Expression | `'/files/rohit_cutting_tools_logo_192x192.png' \| abs_url` | |
| `address` | Template | Linked Template `Company Address` | |

## Example 3. Web page, on every page

Template Name `WebPage`, Schema Type `WebPage`, Applies To `Site`, ID Expression `{{ page.url }}#webpage`.

| Property | Value Type | Value |
|---|---|---|
| `url` | Expression | `page.url` |
| `name` | Expression | `page.h1` |

## Example 4. Template product page

For a page such as `/hss/square-tool-bits/t42-square-hss-tool-bits-bsw`.

Template Name `Product Group`, Schema Type `ProductGroup`, Applies To `Page Type`, ID Expression `{{ page.url }}#productgroup`, Condition `doc.get('has_variants')`, Sample Route `hss/square-tool-bits/t42-square-hss-tool-bits-bsw`.

| Property | Value Type | Value |
|---|---|---|
| `name` | Expression | `doc.web_item_name` |
| `productGroupID` | Expression | `doc.item_code` |
| `url` | Expression | `page.url` |
| `image` | Expression | `doc.get('website_image') \| abs_url` |
| `category` | Expression | `doc.item_group` |
| `description` | Expression | `(doc.get('web_long_description') or doc.get('description') or '') \| replace('><', '> <') \| striptags \| truncate(500)` |

The condition gives no node on a variant page. A variant `Product` needs a price (`offers`), and the expressions cannot read prices yet (#265).

## Example 5. Item Group page

For a page such as `/carbide/ball-nose`.

Template Name `Collection Page`, Schema Type `CollectionPage`, Applies To `Page Type`, ID Expression `{{ page.url }}#collection`, Sample Route `carbide/ball-nose`.

| Property | Value Type | Value |
|---|---|---|
| `name` | Expression | `doc.name` |
| `url` | Expression | `page.url` |
| `image` | Expression | `doc.get('image') \| abs_url` |
| `description` | Expression | `(doc.get('description') or '') \| replace('><', '> <') \| striptags \| truncate(300)` |

## Example 6. Blog post

First make the short publisher: Template Name `Company Ref`, Schema Type `Organization`, Applies To `Component`, ID Expression `{{ site.url }}/#organization`, with the properties `name` (Constant `Rohit Cutting Tools`) and `url` (Expression `site.url`).

Then: Template Name `Blog Posting`, Schema Type `BlogPosting`, Applies To `Page Type`, ID Expression `{{ page.url }}#article`, Sample Route `blog/general/a-comprehensive-guide-to-cnc-machining-principles-applications-and-benefits`.

| Property | Value Type | Value |
|---|---|---|
| `headline` | Expression | `doc.title` |
| `url` | Expression | `page.url` |
| `datePublished` | Expression | `doc.published_on` |
| `dateModified` | Expression | `doc.modified` |
| `description` | Expression | `(doc.get('blog_intro') or '') \| striptags` |
| `image` | Expression | `doc.get('meta_image') \| abs_url` |
| `publisher` | Template | Linked Template `Company Ref` |

## Switch on the Page Type templates

Examples 4 to 6 show on a page only when an **SEO Rule** lists them in **Schema Templates**. See the **Help** of SEO Rule.

## Check the result

1. Open the template and click **Preview**. Type the Sample Route.
2. Open the page on the website and view its source. Search for `application/ld+json`.
