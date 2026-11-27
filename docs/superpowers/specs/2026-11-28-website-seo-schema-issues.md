# Issue drafts: SEO, GEO and schema.org from the database

Drafts for `gh issue create -R adityaduggal/rigpl-erpnext`. Do not create them until the user says go. The design is `2026-11-28-website-seo-schema-design.md` (called "the design" below). Each issue gets the labels `website` and `seo`, and is a sub-issue of the epic E0. Each issue adds its user guide page (design §8, Help).

---

## E0. Epic: Website SEO, GEO and schema.org from the database

Labels: `website`, `seo`, `epic`. Sub-issue of #93.

### Goal
SEO that equals a WordPress SEO plugin, inside ERPNext. Every page and every component has schema.org JSON-LD. All values and rules are in the database, so a change needs no code deploy.

### Context
- Decision of 2026-11-28: ERPNext is the CMS. The SEO-ECOMM project (WordPress + WooCommerce) is retired. #91 is rewritten for Frappe.
- Design: `docs/superpowers/specs/2026-11-28-website-seo-schema-design.md`.
- Rules: no core template override (#82), seed data one time on `after_migrate` (#211), and Website Route Meta wins over the rules.

### Requirements
- [ ] E1 Schema engine
- [ ] E2 SEO Rule and meta tags
- [ ] E3 SEO Settings and the site graph
- [ ] E4 Seed the default records
- [ ] E5 Navigation and breadcrumbs
- [ ] E6 Catalog markup (replaces #91)
- [ ] E7 Merchant listing
- [ ] E8 Image alt text and image URLs
- [ ] E9 Headings
- [ ] E10 Page block markup
- [ ] E11 Blog and content pages
- [ ] E12 GEO-AI
- [ ] E13 GEO-local
- [ ] E14 Sitemap and robots (with #86)
- [ ] E15 Website constants into RIGPL Settings (with #90)
- [ ] E16 Theme meta and theme docs
- [ ] E17 SEO Audit Log and report
- [ ] E18 Context adapter and v16 notes

### Order
E1 → E2 → E3 → E4. Then E5, E6, E7, E8, E9. Then the rest. E18 is a rule for all issues: no expression reads an ERPNext field path directly.

---

## E1. Schema engine: Schema Template DocTypes and the graph builder

### Goal
A website manager makes a schema.org node in Desk. The page outputs it as JSON-LD with no code change.

### Design
- DocType Schema Template and child table Schema Template Property (design §5.2).
- The builder renders each property expression in a separate Jinja2 `SandboxedEnvironment` that sees only the SEO context, with no `frappe` object (design D8), applies the conditions and `iterate_over`, and joins the nodes by `@id` into one `@graph`. The output uses `json.dumps`.
- An expression that raises an error drops its property, writes an Error Log with the template name and the route, and the page still renders.
- On save: test render against a sample route, check the required properties for each type, clear the website cache.
- A Preview button: the JSON-LD for a route that the manager types.

### Work list
- [ ] DocTypes, permissions (Website Manager writes, Guest has no read).
- [ ] Builder, with cached reads (`get_cached_doc`).
- [ ] Required-property lists for Product, Offer, merchant listing, BreadcrumbList, Organization, Article, LocalBusiness, VideoObject.
- [ ] Preview button.
- [ ] Tests on dev-rigpl-v12, with a query-count guard.

### Acceptance
- A bad expression in one property does not stop the page. The Error Log has the row.
- The output parses as JSON for every seed template.
- A save of a Schema Template changes the page after `clear-website-cache` only, with no deploy.

---

## E2. SEO Rule: meta tags for each page type

### Goal
The title, description, canonical, robots, `og:*` and `twitter:*` tags of each page type come from rules in the database.

### Design
- DocType SEO Rule (design §5.3): match on `reference_doctype` and/or `route_pattern`, with `priority`.
- `item_page.update_website_context` calls the rule engine for every page. It writes `context.title`, `context.metatags` and `context.head_include`.
- Precedence, last wins: SEO Settings, SEO Rule, the document fields, Website Route Meta.
- `og:site_name` comes from SEO Settings, not `ERPNext`.

### Work list
- [ ] DocType and the match logic.
- [ ] Wiring in `update_website_context`. Carrier Tracking keeps its noindex.
- [ ] Length limits (title 60, description 160) as a warning on save.
- [ ] Tests for the precedence order.

### Acceptance
- A change to the default description template changes `<meta name="description">` on every page of that type that has no override.
- A Website Route Meta row wins over the rule.

---

## E3. SEO Settings and the site graph

### Goal
Every page outputs `WebSite`, `Organization` (or `LocalBusiness`) and a `WebPage` node from one settings record.

### Design
- Single DocType SEO Settings (design §5.1).
- `WebSite` with `SearchAction` from the site search URL template.
- `Organization`: Company, logo, brand, `sameAs`, contact points. The `@id` is the same on every page.

### Acceptance
- Rich Results Test on the home page: Organization with 0 errors.
- One `@id` for the Organization on all pages.

---

## E4. Seed the default records

### Goal
A new or upgraded site gets working defaults. A later migrate never changes a manager edit.

### Design
- A one-time import from `after_migrate`, as `import_website_once` does. A Patch Log row stops a second run. No fixtures.
- Seed files in `website_rigpl/website_data/seo/`: the Schema Templates, SEO Rules and SEO Settings for the page types in design §7.
- A record that exists is not changed. A failed import rolls back, logs the error and does not stop migrate.

### Acceptance
- After one migrate, the pages in design §11 output their graph.
- An edited Schema Template stays after the next migrate.

---

## E5. Navigation and breadcrumbs

### Goal
The top bar and the breadcrumbs have markup from database components.

### Design
- A Navigation Schema Template iterates `nav.top_bar` and outputs `SiteNavigationElement`.
- A Breadcrumb Schema Template iterates `page.parents` and the variant-to-template crumb (`add_template_breadcrumb`), and outputs `BreadcrumbList`.
- The last crumb text is the H1 text (E9).

### Acceptance
- The `BreadcrumbList` items are the same as the visible breadcrumb, in the same order.
- A change to a Top Bar Item changes the `SiteNavigationElement` output.

---

## E6. Catalog markup: template, variant and category pages

Replaces #91.

### Goal
Template pages output `ProductGroup` with `hasVariant`. Variant pages output `Product` with `isVariantOf`. Category pages output `CollectionPage` with `ItemList`.

### Design
- Data from `catalog.get_variant_table` through the context adapter (E18).
- `ProductGroup`: `@id` = `<canonical>#product`, `name`, `description` (plain text, max 500 characters), `url`, `image`, `brand`, `productGroupID`, `variesBy`, `additionalProperty` from `common`.
- Each variant: `Product` with `@id`, `sku`, `name`, `url`, `size`, `additionalProperty`, `offers` (E7).
- Above the variant limit (SEO Settings, default 200), a variant has only `@id`, `sku`, `url`.
- Remove the microdata in `rigpl_item_template.html:16-21`.
- Variant and Item Group pages get our own templates in `rigpl_erpnext/templates/generators/`, selected by `update_website_context` (design D10). Item Group joins `PAGE_HANDLERS`. The templates reuse ERPNext's JS and macros, and have no microdata.

### Acceptance
- Rich Results Test on a template page: "Product snippets" with 0 errors.
- The `hasVariant` count is the variant table row count.
- The page source has no microdata `Product` and one `ProductGroup`.
- Variant and Item Group pages have no microdata `Product`.
- The ERPNext cart button and the product listing work as before on these pages.

---

## E7. Merchant listing

### Goal
Template and variant pages pass the Google "Merchant listings" test.

### Design
- `Offer`: `price`, `priceCurrency`, `availability` (`InStock`, or `BackOrder` at 0 stock), `itemCondition`, `url`, `priceValidUntil`, `shippingDetails`, `hasMerchantReturnPolicy`.
- `Product`: `mpn` = item code, `brand`, `image`.
- `offers` only when the page shows the price (E Commerce Settings and the guest rules of README §6.4).
- The return policy at organization level and the shipping rows from SEO Settings.
- The Merchant Center feed from the same data (with #86).

### Acceptance
- Rich Results Test: "Merchant listings" with 0 errors on a template and a variant page.
- A guest with **Hide Price for Guest** set gets no `offers`.

---

## E8. Image alt text and image URLs

### Goal
Every image has alt text from the database. Every image URL in the markup and the meta tags is absolute and URL-encoded.

### Design
- The SEO Rule alt template sets `website_image_alt` on the in-memory `context.doc`. ERPNext reads `doc.website_image_alt` in `item_image.html:27`. Nothing is saved.
- The RIGPL web templates get an `image_alt` field.
- `og:image` and JSON-LD images: absolute and encoded (the #91 audit found spaces).

### Acceptance
- The audit (E17) reports 0 images without alt text on the pages in design §11.

---

## E9. Headings

### Goal
Each page has one H1. The last breadcrumb is the H1. Sections use H2 in order.

### Design
- The SEO Rule H1 template, used by our own templates (D10).
- The template page: H2 "Specifications" above the common specs, H2 "Sizes, stock and prices" above the variant table. The texts come from the database.
- The RIGPL web templates get a `heading_level` field.

### Acceptance
- The audit reports one H1 per page and no skipped heading level.

---

## E10. Page block markup

### Goal
Each Web Page block outputs the markup of its Web Template.

### Design
- A Schema Template with `applies_to` = Web Template reads the block values as `block`.
- Seeds: Slideshow (`ImageObject`), Item Card Group (`ItemList`), RIGPL Latest Blogs (`ItemList` of `BlogPosting`), RIGPL Social Feeds (`VideoObject`), RIGPL Contact Strip (`ContactPoint`).
- Move the script URLs and the inline style of `rigpl_social_feeds.html` into template fields.

### Acceptance
- The home page graph has one node set for each block.

---

## E11. Blog and content pages

### Goal
Blog posts, About and Contact pages output their types.

### Design
- `BlogPosting` with `Person` author (Blogger), `datePublished`, `dateModified`, `image`.
- `AboutPage` and `ContactPage` by SEO Rule.

### Acceptance
- Rich Results Test on a blog post: Article with 0 errors.

---

## E12. GEO-AI

### Goal
AI assistants can find and cite correct facts about the company and the products.

### Design
- `/llms.txt` from the SEO Settings Jinja body.
- AI crawler rows in SEO Settings write their lines into Website Settings `robots_txt`.
- One `@id` and `sameAs` set for the entity on every page. `dateModified` on every `WebPage`.
- An FAQ web template with `FAQPage` markup (opt-in, D7).

### Acceptance
- `/llms.txt` returns 200 and changes when the setting changes.
- A crawler row set to deny shows in `/robots.txt`.

---

## E13. GEO-local

### Goal
Each company location outputs `LocalBusiness` from its Address.

### Design
- SEO Settings location rows: Address, `geo`, `openingHoursSpecification`, `areaServed`.
- The Contact page outputs the locations.

### Acceptance
- Rich Results Test: LocalBusiness with 0 errors on the Contact page.

---

## E14. Sitemap and robots

With #86.

### Design
- `lastmod` from `modified`. Routes with noindex are not in the sitemap.
- Search Console and Bing verification tags in Website Settings `head_html`.

### Acceptance
- No noindex route in `/sitemap.xml`.

---

## E15. Website constants into RIGPL Settings

With #90.

### Design
Move these constants into RIGPL Settings: `catalog.py:20-22`, `routes.py:20-28`, `sales_rank.py:29-31`, and the variant sort order for each template.

### Acceptance
- No website default stays only in code. An empty field uses its DocType default.

---

## E16. Theme meta and theme docs

### Design
- The `theme-color` meta from the Website Theme primary color.
- A user guide page for the theme tokens (README §6.2).

---

## E17. SEO Audit Log and report

### Goal
A website manager sees the SEO faults of all pages in one report.

### Design
- A scheduled job renders each sitemap route and writes an SEO Audit Log row per page (design §5.4).
- A script report groups the faults by type and page.

### Acceptance
- The report lists a page with a 70-character title as a fault.

---

## E18. Context adapter and v16 notes

### Goal
The database templates stay the same through the v14, v15 and v16 upgrades.

### Design
- The adapter builds the context of design §6. Only the adapter reads ERPNext or webshop fields, through `compat.get_ecommerce`.
- Add the SEO checks to `patches/v13/NOTES_v14_upgrade.md`. Add a note to #82.

### Acceptance
- No Schema Template or SEO Rule seed reads a raw ERPNext field path that changes at v15.
