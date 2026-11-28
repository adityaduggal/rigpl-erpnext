# Schema Templates

A Schema Template makes one schema.org node, or a list of nodes. The website writes the nodes into the page as JSON-LD. Search engines and AI assistants read it. A change needs no code deploy.

Only the role **Website Manager** can open Schema Templates.

## Which templates a page outputs

Each page outputs the enabled templates with **Applies To** = **Site**. A page also outputs the **Page Type** templates that its **SEO Rule** lists. A **Web Template** template makes its nodes for each visible Web Page block of that Web Template. A **Component** template appears only inside another template. Each page also outputs the **Navigation** and **Breadcrumb** templates.

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
| `site.brand` | The title prefix of Website Settings, else the company name. |
| `site.organization` | `legal_name`, `email`, `telephone`, `founding_date`, `logo`, `same_as` and `address` (`street`, `city`, `state`, `pincode`, `country_code`). See **Where the company data comes from**. |
| `page.route`, `page.url`, `page.title`, `page.h1`, `page.parents` | The page. `page.title` has the title prefix of Website Settings, `page.h1` does not. `page.parents` is the breadcrumb list. |
| `page.crumbs` | The items of the visible breadcrumb: `position`, `name`, `url`. It is empty on a page that shows no breadcrumb. |
| `nav.top_bar` | The rows of the top bar that have a link: `position`, `name`, `url`. |
| `doc` | The fields of the page document. It is empty on a page that has no document. |
| `row` | The element of Iterate Over. |

### Product values

| Name | Content |
|---|---|
| `item` | The product of a product page: `is_template`, `id`, `url`, `name`, `code`, `image`, `description`, `category`, `properties`, `varies_by`, `parent`, `offer`. Empty on other pages. |
| `variants` | On a template page, one element for each row of the variant table: `id`, `sku`, `url`, `full`, `name`, `size`, `image`, `properties`, `offer`. |
| `common` | On a template page, the specifications that all variants share: `name`, `value`. |
| `listing` | On a category page, the first page of products, else the sub-categories: `position`, `name`, `url`. |

An `offer` has `price`, `currency`, `availability`, `condition`, `url`, `valid_until` and `shipping`. There is no offer when a visitor who is not logged in sees no price.

## Prices, shipping and returns

| Value | Change it here |
|---|---|
| Price and currency | **Item Price** of the price list of **E Commerce Settings** |
| Show the price | **E Commerce Settings**: **Show Price** and **Hide Price for Guest** |
| Availability | `InStock` when the website warehouse has stock, else `BackOrder` |
| Destinations and charges | Enabled **Shipping Rules** of type Selling that have countries. A rule by weight is not used. |
| Handling and transit days, price valid days, variant limit | **SEO Settings** > Products and Offers |
| Return policy | **SEO Settings** > Return Policy |

### Block values

A **Web Template** template, and each Component template that it links to, reads `block`:

| Name | Content |
|---|---|
| `block.idx` | The row number of the block on the page. Use it in the `@id`. |
| `block.<fieldname>` | The value of a field of the Web Template. An empty field can be absent: use `block.get("fieldname")`. |
| `block.products` | The published Website Items that the block links to: `position`, `name`, `item_code`, `title`, `url`, `image`. |
| `block.slides` | The slides of the linked Website Slideshow: `idx`, `image`, `heading`, `description`, `url`. |
| `block.posts` | For a Web Template with the field `blog_count`, the latest blog posts: `position`, `title`, `url`, `author`, `description`, `published_on`, `image`. |

An image in a private file is empty.

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

## Default templates

The system creates these templates one time after `migrate`. The button **Create Missing Records** in **SEO Settings** creates the ones that do not exist. A template that exists is never changed: delete it and click the button to get the default again.

Each value reads the database. When you change the source record, the pages change.

| Template | Applies To | Output |
|---|---|---|
| `Company` | Site | `Organization` of the website, with `Company Address`. |
| `WebSite` | Site | `WebSite`, with the publisher `Company Ref`. |
| `WebPage` | Site | `WebPage` with the address and the H1 of the page. |
| `Product Group` | Page Type | `ProductGroup` on a template product page, with one `Product` for each variant. |
| `Product` | Page Type | `Product` on a variant page, with its `Offer`. |
| `Collection Page` | Page Type | `CollectionPage` on an Item Group page. |
| `Blog Posting` | Page Type | `BlogPosting` on a blog post. |
| `Breadcrumbs` | Breadcrumb | `BreadcrumbList` of the visible breadcrumb. The last item has the text that the page shows. |
| `Top Bar` | Navigation | `SiteNavigationElement` for each link of the top bar. |
| `Slideshow Images` | Web Template | `ImageObject` for each slide. |
| `Item Card Group List`, `Item Cards List` | Web Template | `ItemList` of the products of the block. |
| `Latest Blogs List` | Web Template | `ItemList` of `BlogPosting`. |
| `Social Video` | Web Template | `VideoObject`. It needs **Video Title** and **Video Upload Date** in the block. |
| `Contact Strip` | Web Template | `contactPoint` of the website `Organization`. |
| `Company Address`, `Company Ref`, `Product List Item`, `Blog List Item`, `Block Blog Post`, `Block Blog Author`, `Block Contact Point`, `Breadcrumb Item`, `Return Policy`, `Product Brand`, `Property Value`, `Product Offer`, `Variant Product`, `Parent Product Group`, `Shipping Details`, `Shipping Region`, `Shipping Charge`, `Delivery Time`, `Handling Time`, `Transit Time`, `Category Listing`, `Listing Item` | Component | Parts of the templates above. |

On `/contact`, the Frappe page shows its own title in the breadcrumb. The last item of `BreadcrumbList` has the title of the browser tab.

A block template is created only if the site has its Web Template. The block **RIGPL Homepage Section** has no template.

The rule **Home page** is created for the home page of **Website Settings**. The **Meta Title** and **Meta Description** of the Web Page replace the values of the rule.

To see the property rows of a template, open it. Click **Preview** and type the route of a page to see the result.

## Where the company data comes from

| Value | Change it here |
|---|---|
| Company | **SEO Settings** > Company. Empty: the default company of Global Defaults. |
| Legal name, email, phone, founding date | **Company** |
| Address | **SEO Settings** > Address. Empty: the primary company address of the Company. |
| Brand | **Website Settings** > Title Prefix |
| Logo | **Website Settings** > Banner Image. A private file is not used. |
| Social profiles | **Website Settings** > footer items under the label `Social`. WhatsApp links are not used. |

The email and phone of the Company are public on the website.

## Switch on the Page Type templates

A **Page Type** template shows on a page only when the **SEO Rule** of the page lists it in **Schema Templates**. The default rules do this.

## Check the result

1. Open the template and click **Preview**. Type a route.
2. Open the page on the website and view its source. Search for `application/ld+json`.
