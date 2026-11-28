# Design: SEO, GEO and schema.org JSON-LD from the database

Date: 2026-11-28. Status: design approved, no code. Branch: `feat/website-seo-schema` (from `version-13`).

## 1. Intent

The public website rigpl.com runs on the Frappe/ERPNext v13 website (`rigpl_erpnext/website_rigpl/`, epic #93). The SEO audit of 2026-10-16 (#91) found these faults on a template page:

- The title is the internal item name after the brand.
- The meta description is the item name (27 characters).
- `og:site_name` is `ERPNext`.
- There is no JSON-LD. The microdata `Product` has no `offers`, so Google marks it invalid.
- The last breadcrumb is not the same as the H1. The page has no H2.

The goal is SEO that equals a WordPress SEO plugin, inside ERPNext. Website managers edit all SEO data in Desk. A change needs no code deploy.

## 2. Decisions

| # | Decision | Source |
|---|---|---|
| D1 | ERPNext is the CMS. The WordPress + WooCommerce plan (project SEO-ECOMM, #91) is retired. #91 is rewritten for Frappe. | user, 2026-11-28 |
| D2 | A schema is a set of mapping rows. A row value is a short Jinja expression with an optional condition. A row can link to another schema. Python builds one `@graph` per page with `json.dumps`, so the output is always valid JSON. | user |
| D3 | "GEO" means two things: Generative Engine Optimization (AI answers and citations), and geographic/local search. | user |
| D4 | Use only vanilla extension points. Do not override or copy a Frappe or ERPNext template. Our own templates extend `templates/web.html` (#82). | user + #82 |
| D5 | Seed the default records one time from `after_migrate`, as `website_data/importer.py` does. Do not use fixtures, because `sync_fixtures` overwrites manager edits (#211). | my call |
| D6 | Website Route Meta (vanilla) is the override for one route. It wins over the rule defaults. | my call |
| D7 | No meta keywords. FAQPage and HowTo are allowed types. The seed does not turn them on, because Google limits the FAQ rich result and deprecated HowTo. FAQ markup stays opt-in for GEO. | my call |
| D8 | Expressions run in a separate sandbox that sees only the SEO context. A Website Manager gets no database write access from an expression. | my call (builder check) |
| D9 | The JSON-LD price is the guest price: E Commerce Settings `price_list` (`PL56` on dev, guests see prices). Google crawls as a guest. A logged-in customer can see a different price on the same URL. | my call (builder check) |
| D10 | Variant and Item Group pages use our own templates in `rigpl_erpnext/templates/generators/`. They extend `templates/web.html`. The `update_website_context` hook selects them: it returns `{"template": ...}`, as `item_page.website_item_context` already does for template items. Item Group joins `PAGE_HANDLERS`. The templates use ERPNext's JS (cart, product listing) and macros. They have no microdata, an H1 from the SEO Rule, and a breadcrumb include of our own with no microdata. We change no Frappe or ERPNext file. We do not shadow a core template path through the Jinja loader, because that is a copy of core (#82). | user, 2026-11-28 |

Why ERPNext and not WordPress:

- ERPNext holds the live data: 2,983 published variants, the capped stock, the customer price lists, and the cart that makes a Quotation.
- `website_rigpl` already has the routes, the 301 redirects, the v12 URL lookup, the sales rank and the theme in the database.
- WordPress needs a permanent sync from ERPNext, a B2B price-list plugin, a customer login map and an order sync back. The SEO work in ERPNext is a one-time cost.

## 3. Goals, non-goals, anti-goals

Goals:

- Each page and each page component has schema.org JSON-LD.
- Each value in the markup comes from the database. The code has no literal values.
- Meta tags, image alt text, H1 text, breadcrumbs and navigation markup are rules in the database.
- The site passes Google Rich Results Test for "Product snippets" and "Merchant listings" with 0 errors.
- Each section has a user guide page in Desk.
- The same code runs on v13 and on the later v14, v15 and v16 branches. Only the context adapter (section 6) changes.

Non-goals:

- WordPress or WooCommerce.
- A second language and hreflang. The site has one language now.
- Rich result, ranking or AI citation guarantees.

Anti-goals (failure even if the code works):

- A core template is overridden or copied.
- A manager edit is lost on the next `bench migrate`.
- One bad expression in the database breaks a live page.
- A page has two sources of product markup (for example JSON-LD and microdata).

## 4. Vanilla extension points

| Point | Use |
|---|---|
| `update_website_context` hook, now `website_rigpl/item_page.update_website_context` with `PAGE_HANDLERS` (`item_page.py:51`) | The one entry point. It writes `context.head_include`, `context.metatags`, `context.title` and `context.canonical`. It runs after `add_metatags` (`frappe/website/context.py:125` vs `:137-141`). |
| `frappe/website/context.py:add_metatags` | Adds `og:*` and `twitter:*`, then applies Website Route Meta. It runs before our hook, so our engine derives the `og:*` and `twitter:*` tags again and applies Website Route Meta again, last (D6). |
| `frappe/templates/base.html` block `meta_block`, block `head_include`, and `<link rel="canonical" href="{{ canonical }}">` (`base.html:23`) | Read the context. Not changed. |
| Website Route Meta + Website Meta Tag | Per-route override (D6). |
| Website Settings `robots_txt`, `head_html`, Top Bar Items, Footer Items | Robots rules, verification tags, navigation data. |
| `frappe/www/sitemap.py` | Lists pages with `sitemap` set. |
| Website Item `website_image_alt` | Read from `doc.website_image_alt` by `erpnext/templates/generators/item/item_image.html:27`. The rule sets it on the in-memory `context.doc`. It is not saved. |
| Web Page `context_script`, `javascript` | Page scripts in the database (vanilla, `safe_exec`). |
| Website Theme + Color | The theme in the database (`rigpl-v12`). |
| `frappe/utils/jinja.py:get_jenv` | Not used for SEO expressions. Its globals (`get_safe_globals`) give `frappe.db.set_value`, `commit` and `get_doc` (`utils/safe_exec.py:170-242`). See D8. |

Existing code to reuse:

- `catalog.get_variant_table()`: common specs, columns, rows and shop data.
- `compat.get_ecommerce()`: the e-commerce paths for v13 and webshop.
- `item_page.add_template_breadcrumb`: the variant-to-template breadcrumb.
- `routes.py`: the route rules.
- `carrier_tracking.py:28,152`: the `metatags` and `sitemap = 0` pattern.
- `public/js/user_guide.js` + `docs/user/*.md`: help in Desk.

## 5. New DocTypes

All are in module Website-RIGPL. Only Website Manager can write them.

### 5.1 SEO Settings (Single)

The site entity and the defaults:

- Organization: link to Company, logo, brand, `@id` base URL, `sameAs` (child table), contact points (child table).
- WebSite: name, and the site search URL template for `SearchAction`.
- Meta defaults: title template, description template, title limit (60), description limit (160).
- Merchant defaults: currency, the return policy at organization level (`hasMerchantReturnPolicy`), shipping rows (`OfferShippingDetails`: destination, rate, handling days, transit days), the `priceValidUntil` rule, the variant limit (200).
- GEO-AI: `llms.txt` on/off and its Jinja body. AI crawler rows (user agent, allow or deny) that write into Website Settings `robots_txt`.
- GEO-local: LocalBusiness type, one row per location (Address link, geo coordinates, opening hours, `areaServed`).

### 5.2 Schema Template

One schema.org node, or a list of nodes.

| Field | Use |
|---|---|
| `schema_type` | For example `Product`, `Offer`, `BreadcrumbList`. |
| `enabled` | Off: the node is not output. |
| `applies_to` | Site, Page Type, Web Template, Navigation, Breadcrumb or Component. |
| `web_template` | The Web Template whose blocks use this schema (when `applies_to` = Web Template). |
| `id_expression` | Jinja for `@id`, for example `{{ page.url }}#product`. |
| `condition` | Jinja. An empty or false result: no node. |
| `iterate_over` | Jinja that gives a list. The template makes one node per element. |
| `help` | Notes for managers. |

Child table Schema Template Property:

| Field | Use |
|---|---|
| `property` | The schema.org property, for example `sku`. |
| `value_type` | Expression, Constant, Template or Template List. |
| `value` | Jinja (Code field). |
| `linked_template` | The nested Schema Template (Template, Template List). |
| `condition` | Jinja. False: the property is not output. |
| `required` | A missing value is an error in the save check and in the audit. |

On save:

1. Render the template against a sample route.
2. Check the required properties for these types: Product, Offer, merchant listing, BreadcrumbList, Organization, Article, LocalBusiness, VideoObject.
3. Clear the website cache.

A **Preview** button shows the JSON-LD for a route that the manager types.

At page render, an expression that raises an error drops only its own property. The page still renders. The error goes to the Error Log with the template name and the route.

### 5.3 SEO Rule

The meta settings for one page type:

- Match: `reference_doctype` (Web Page, Website Item, Item Group, Blog Post, Blog Category, Web Form and others) and/or `route_pattern`, with `priority`. The highest matching priority wins.
- Jinja templates for: title, meta description, canonical, robots, `og:type`, twitter card, image, image alt text, H1.
- Child table: the Schema Templates that the page outputs.

The order of precedence, last wins:

1. SEO Settings defaults.
2. SEO Rule.
3. The fields on the document: `meta_title`, `meta_description`, `meta_image`, `website_image_alt`.
4. Website Route Meta.

### 5.4 SEO Audit Log and report

A scheduled job renders each sitemap route and records these checks, as a WordPress SEO plugin does:

- title and description length;
- the H1 count and the heading order;
- images that have no alt text;
- JSON-LD that does not parse, and missing required properties;
- a canonical URL that is not the route;
- noindex on a route that is in the sitemap;
- a last breadcrumb that is not the same as the H1.

## 6. The SEO context contract

The expressions read a stable context. An adapter in `website_rigpl` builds it. The adapter is the only code that reads ERPNext or webshop field paths, because those paths move at v15.

| Key | Content |
|---|---|
| `site` | SEO Settings and the Company. |
| `page` | Route, absolute URL, title, `parents`, H1. |
| `doc` | The page document. |
| `item`, `variants`, `common` | From `catalog.get_variant_table` and `compat.get_ecommerce`. |
| `block` | The values of one Web Page block. |
| `nav` | Top Bar Items and Footer Items. |

At an upgrade, only the adapter changes. The templates in the database stay the same.

## 7. Coverage of each page component

| Component | Markup |
|---|---|
| Every page | `WebSite`, `Organization` or `LocalBusiness`, `WebPage` (or `CollectionPage`, `ItemPage`, `ContactPage`, `AboutPage`). |
| Top bar | `SiteNavigationElement` from `nav.top_bar`. |
| Breadcrumbs | `BreadcrumbList` from `page.parents` and the variant-to-template crumb. The last crumb is the same as the H1. |
| Slideshow block | `ImageObject` per slide. |
| Item Card Group block | `ItemList`. |
| RIGPL Latest Blogs block | `ItemList` of `BlogPosting`. |
| RIGPL Social Feeds block | `VideoObject` for the YouTube video. |
| RIGPL Contact Strip block | `ContactPoint`. |
| Template page | `ProductGroup` with `hasVariant`, `variesBy`, `productGroupID`, `additionalProperty`. Each variant is a `Product` with `Offer`. Above the variant limit, a variant has only `@id`, `sku` and `url`. |
| Variant page | `Product` with `isVariantOf` and `Offer`. |
| Item Group page | `CollectionPage` with `ItemList`. |
| Blog post | `BlogPosting` with `Person` author, `datePublished`, `dateModified`. |
| FAQ block (opt-in) | `FAQPage`. |

All nodes join by `@id` in one `@graph`. The template page loses its microdata (`rigpl_item_template.html:16-21`).

Merchant listing `Offer`: `price`, `priceCurrency`, `availability` (`InStock`, or `BackOrder` at 0 stock), `itemCondition`, `url`, `priceValidUntil`, `shippingDetails`, `hasMerchantReturnPolicy`. The `Product` has `mpn` (item code), `brand` and `image`. The page outputs `offers` only when it shows the price.

## 8. Other parts

- **Images.** The SEO Rule alt template sets `website_image_alt` on the in-memory `context.doc`, which ERPNext reads in `item_image.html:27`. The RIGPL web templates get an `image_alt` field. Image URLs are absolute and URL-encoded.
- **Headings.** The SEO Rule H1 template gives one H1. The template page gets an H2 above the specs and an H2 above the variants. The RIGPL web templates get a `heading_level` field.
- **GEO-AI.** `llms.txt`, AI crawler rules, the same `@id` and `sameAs` on every page, and `dateModified`.
- **GEO-local.** LocalBusiness per location with `geo`, `openingHoursSpecification` and `areaServed`.
- **Sitemap and robots.** `lastmod` from `modified`. Routes with noindex are not in the sitemap (#86).
- **Settings in the database.** Move these constants into RIGPL Settings: `catalog.py:20-22`, `routes.py:20-28`, `sales_rank.py:29-31`, and the variant sort order for each template (#90).
- **Theme.** Website Theme + Color stay. The `theme-color` meta comes from the theme primary color. The SCSS variables (README §6.2) are documented as theme components.
- **Pages.** All pages are Web Pages in the database. Close #94 (16 unpublished pages).
- **Help.** One `docs/user/website_seo_*.md` page per section, shown by `user_guide.js`. A description on each new field.

## 9. Security and performance

- Expressions render in a separate Jinja2 `SandboxedEnvironment` (D8). Its globals are only the SEO context (section 6) and a short list of filters. It has no `frappe` object.
- Descriptions lose their HTML and get the length limit.
- Schema Templates and SEO Rules are read with `get_cached_doc` and cached lists. A save clears the cache.
- Variant data is batched in one query, as in `catalog.py`. Each page type has a query-count test guard.
- The Frappe page cache keeps the rendered head of most pages. Website Item pages set `no_cache=1` (`website_item.py:35`), so the engine caches the graph in Redis by route and document `modified`. Blog Post, Item, Schema Template, SEO Rule and SEO Settings changes clear both caches.

## 10. Builder-check answers (my calls)

- `og:site_name` is hard-coded to `ERPNext` at `erpnext/e_commerce/doctype/website_item/website_item.py:311`. The engine overwrites it from SEO Settings.
- `robots_txt`: the engine owns only a marked section, from `# BEGIN RIGPL SEO` to `# END RIGPL SEO`. A manager edit outside the section stays.
- Seed updates: each seed record has a fixed name. A later release inserts the missing records and properties only. It never changes a record that exists.
- Precedence step 3 applies only where the document has the field (Web Page, Blog Post, and `website_image_alt` on Website Item). Other pages use Website Route Meta for a per-page override. No new meta custom fields.
- Web Pages and Blog Posts keep the core `breadcrumbs.html` microdata `BreadcrumbList`. It has the same items as our JSON-LD `BreadcrumbList`, so the two do not conflict.
- Sitemap: no override of `frappe/www/sitemap.py`. The audit reports a noindex route that the sitemap lists. E14 decides the fix for each page type.

## 11. Left to the builder

- Field names and labels, except where this document names them.
- The adapter code layout inside `website_rigpl`.
- The structure of the seed data files.
- The audit job schedule and its queue.

## 12. Verification (the user runs the tests)

- `bench --site dev-rigpl-v12 run-tests --module rigpl_erpnext.tests.test_seo_<area> --skip-before-tests --skip-test-records`. These are real-site tests with a query-count guard.
- Run Google Rich Results Test and the Schema.org validator on these pages: the home page, a template page, a variant, an Item Group, a blog post and Contact.
- Change a Schema Template in Desk, then run `bench --site <site> clear-website-cache`. The JSON-LD changes with no deploy.
- Each page has one `@graph` script and no microdata `Product`.
- The SEO Audit report shows: no title over 60 characters, no description over 160, one H1 per page, no image without alt text.

## 13. Image alt text and image check (#267, user, 2026-11-28)

Approaches for the custom alt text, with no new custom field:

- A (chosen): a comment on the File that starts with `Alt:`. No URL change, edit history.
- B: the `file_name` field. It also changes the download name and the File Attachment Rule check.
- C: only the alt text of each place. The text repeats at each use.

Order, first found wins: the alt text of the place, the File comment (by `file_url`), a file name of two or more words, the SEO Rule `image_alt_template`, the H1.

The website hook fills `alt` at page render, only where an image has none. Nothing is saved. This covers the core Slideshow block, which writes no `alt`. It replaces "The RIGPL web templates get an `image_alt` field" of section 8: those templates write no image.

The check: a save blocks a new image that has no alt text from the first three sources, and warns for an image that the document had before (chosen over "block all" and "warn only"). A migrate, an import, a patch and a save that ignores permissions only warn. Files are not renamed.

Code: `website_rigpl/seo/images.py`.

## 14. Headings (#268, user, 2026-11-28)

- `templates/rigpl_base.html`, set by the `base_template` hook, extends Frappe's base template and changes only the title tag to `seo_title`. `title` is the H1 and the last breadcrumb.
- A Web Page with no H1 gets a hidden (`sr-only`) H1. Chosen over a visible H1 and over manual page edits.
- `templates/includes/rigpl_item_details.html` is ERPNext's `item_details.html` with the name as H1 and no microdata. Compare at each upgrade. Chosen over a hidden H1.
