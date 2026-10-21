# RIGPL Website: v12 to v13 Guide

This guide is for website managers. It tells you how to make the v13 website look and work like the v12 website at rigpl.com. GitHub issue #88 tracks this work.

## 1. What changed from v12

In v12, the home page and the website theme were code in this app:

- `www/index.html` and `www/index.py` made the home page.
- `templates/base.html`, the navbar and the footer templates made the page frame.
- `public/scss/*.scss` made the theme (the colors, the font and the dark navbar).

Commit eeb391b removed all of this code. In v13, the website is data in the database. You edit it in Desk. You do not need a code deploy for a change.

| v12 code | v13 place to edit it |
|---|---|
| `www/index.html` sections | Web Page `home`, table **Page Blocks** |
| Social ids in `www/index.py` | The **RIGPL Social Feeds** block on the home page |
| Contact block | The **RIGPL Contact Strip** block on the home page |
| `public/scss/*.scss` | Website Theme `rigpl-v12` (section 4 of this guide) |
| Navbar menu | Website Settings, table **Top Bar Items** (no change from v12) |
| Footer links | Website Settings, table **Footer Items** (no change from v12) |

## 2. The web templates in this app

A web template is a reusable section of a page. A Web Page block uses one web template and keeps the values for it. To edit a block, open the Web Page, open the row in **Page Blocks**, and click **Edit Values**.

This app adds five web templates in the module Website-RIGPL. `bench migrate` installs them.

| Web Template | What it shows | Fields |
|---|---|---|
| RIGPL Social Feeds | The Twitter timeline, the Facebook page and a YouTube video, in three columns | Title, Twitter Handle, Facebook Page, YouTube Channel ID, YouTube Video ID |
| RIGPL Contact Strip | "Have more questions?" with the email, the phone and a button | Title, Email, Phone, Button Label, Button URL |
| RIGPL Latest Blogs | The latest published Blog Posts as cards | Title, Number of Blog Posts |
| RIGPL Homepage Section | One Homepage Section with its cards or its HTML | Homepage Section |
| RIGPL Variant Table | The published variants of a template Website Item, with the item code of each variant (section 6) | Title, Website Item |

The home page also uses two standard templates:

- **Slideshow** shows a Website Slideshow. Edit the images in the Website Slideshow document.
- **Item Card Group** shows up to 12 Website Items. Each card is a link to a Website Item.

Notes:

- RIGPL Latest Blogs reads the Blog Posts each time the page is built. When you publish, change or delete a Blog Post, the app clears the website cache, so the home page shows the change.
- RIGPL Homepage Section reads the Homepage Section document. To change the cards, edit the Homepage Section document, not the block.
- Do not edit these five web templates in Desk. They are standard templates, and the next update replaces your changes. If you need a different layout, ask a developer to change the template files in `website_rigpl/web_template/`.

## 3. Import the v12 website

The import makes the v12 theme and the v12 home page in the database. Do these steps one time on each site, after the v13 migration.

### 3.1 Before the import

1. Make a backup of the site.
2. Run `bench --site <site> migrate`. This installs the four web templates.
3. At the end of the migrate, look for this message:

   ```
   rigpl_erpnext: the v12 website (theme and home page) is not imported.
   ```

   The message shows on each migrate until you do step 3.2 or step 3.3.
4. In Desk, open **Homepage**. Make sure that **Slideshow** is set and that the **Products** table has the products that you want on the home page.
5. Open **Contact Us Settings**. Make sure that **Email Id** and **Phone** are correct.

### 3.2 Import the theme and the home page

1. Run this command:

   ```
   bench --site <site> run-patch rigpl_erpnext.patches.manual.import_website_data
   ```

2. Read the output. It tells you what the import did:
   - `Website Theme rigpl-v12 was imported. CSS: /files/website_theme/...`
   - `Website Settings theme changed from None to 'rigpl-v12'.`
   - `Web Page home was imported with N blocks at /rohit-cutting-tools.`
   - `Website Settings home page changed from 'index' to 'rohit-cutting-tools'.`
3. Open the site root `/` in a private browser window. Compare it with the v12 home page (section 5 of this guide).

The import makes the theme first. Section 4.2 lists the theme records.

Then the import makes these home page blocks in this order. This is the same order as the v12 page:

| # | Block | Data comes from |
|---|---|---|
| 1 | Slideshow | Homepage, field Slideshow |
| 2 | Item Card Group, title "Products" (one block for each 12 products) | Homepage, table Products |
| 3 | RIGPL Latest Blogs, title "Publications", 3 posts | Blog Post |
| 4 | RIGPL Homepage Section (one block for each Homepage Section) | Homepage Section, sorted by Section Order |
| 5 | RIGPL Social Feeds, title "Social" | `website_data/home.json` |
| 6 | RIGPL Contact Strip, "Have more questions?" | Contact Us Settings and `website_data/home.json` |

The import also sets these Web Page fields: Title, Meta Title and Meta Description from Homepage. It sets Published, Full Width and Content Type "Page Builder".

Safety rules of the import:

- The import does not change a Color or a Website Theme that already exists.
- The import changes Website Settings **Website Theme** only if it is empty or `Standard`.
- If Web Page `home` already has blocks or content, the import does not change it.
- The import changes Website Settings **Home Page** only if the current value shows no page.
- If a step fails, the import stops with an error and saves nothing. This includes an SCSS error in the theme, a missing slideshow, a product with no Website Item, or a missing web template. Correct the data and run the command again with `--force`.

### 3.3 Skip the import

If you do not want the import, run this command. It does not change data. It only stops the migrate message.

```
bench --site <site> run-patch rigpl_erpnext.patches.manual.skip_website_data_import
```

### 3.4 Run the import again

`run-patch` runs a patch only one time. To run it again, add `--force`:

```
bench --site <site> run-patch --force rigpl_erpnext.patches.manual.import_website_data
```

The import does not change records that exist. To make a record again from the v12 data, first remove the record in Desk:

- For the theme: delete Website Theme `rigpl-v12`.
- For the home page: open Web Page `home`, delete all rows in **Page Blocks**, and save.

Then run the command with `--force`.

## 4. The v12 website theme

The v12 theme was the file `public/scss/index.scss` in this app. v13 uses a **Website Theme** document instead. Until the import runs, Website Settings has no theme set, and the site uses the plain Frappe theme.

### 4.1 The v12 design values

| Item | v12 value |
|---|---|
| Font | Poppins (Google Fonts), weights 300, 400 and 700 |
| Font size | 16px |
| Primary color (buttons, links on hover, navbar top line) | Green `#8BBF46` |
| Dark color (navbar, footer, dropdown menus) | Dark purple `#191B69` |
| Other colors of the palette | Midnight blue `#18427B`, light grey `#E2DBD4`, slate grey `#7F8487` |
| Navbar | Dark background, a 5px green line at the top, white links that turn green on hover |
| Dropdown menus | Dark background, small text (0.75rem), square corners |
| Primary buttons | White text on green |
| Footer | Dark background, logo (200px) on the left, link groups, copyright and address at the bottom |
| Images | Never wider than their container |
### 4.2 The theme that the import makes

The import (section 3.2) makes these records. The data is in `website_data/theme.json` and `website_data/rigpl_v12_theme.scss`.

Colors:

| Color | Value |
|---|---|
| `rigpl-v12-green` | `#8BBF46` |
| `rigpl-v12-dark-purple` | `#191B69` |
| `rigpl-v12-midnight-blue` | `#18427B` |
| `rigpl-v12-light-grey` | `#E2DBD4` |
| `rigpl-v12-slate-grey` | `#7F8487` |

Website Theme `rigpl-v12`:

| Field | Value |
|---|---|
| Custom? | Yes |
| Google Font | `Poppins` |
| Font Properties | `wght@300;400;700` |
| Font Size | `16px` |
| Primary Color | `rigpl-v12-green` |
| Dark Color | `rigpl-v12-dark-purple` |
| Button Rounded Corners | Yes |
| Button Shadows | No |
| Button Gradients | No |
| Custom SCSS | The content of `rigpl_v12_theme.scss`: the dark navbar with the green top line, the dark dropdown menus, the dark footer, white text on primary buttons |

The import also sets `rigpl-v12` as the website theme in Website Settings, but only if no other theme is set.

To change the theme after the import:

1. Open Website Theme `rigpl-v12` in Desk.
2. Change the fields or the **Custom SCSS**.
3. Save. Frappe compiles the theme. If the SCSS has an error, the save shows it and changes nothing.
4. Open the site in a private browser window and check the change.

Do not edit `rigpl_v12_theme.scss` to change a live site. The import reads it only one time. After the import, the theme is in the database.

To use the other v12 colors, select them in a color field of the theme, or use them in Custom SCSS as plain values, for example `color: #18427B;`.

### 4.3 Website Settings that complete the theme

These values are already in the database from v12. Make sure that they are correct:

| Website Settings field | Value |
|---|---|
| Brand HTML | The logo `/files/rohit_cutting_tools_logo_192x192.png` |
| Favicon | `/files/Rohit_Cutting_Tools_32x32_Favicon.ico.png` |
| Title Prefix | `Rohit Cutting Tools` |
| Copyright | `Rohit Industries Group (P) Ltd <year> \| All rights reserved` |
| Address | The plant address and the WhatsApp number |
| Top Bar Items | The Products, Services, Resources, About Us and Contact Us menus |
| Footer Items | The Social, Company and Resources link groups |
| Hide Footer Signup | Yes |
| Head HTML | The Facebook Pixel code |

The v12 footer showed the logo. v13 shows it only when **Footer Logo** is set. Set **Footer Logo** to `/files/rohit_cutting_tools_logo_192x192.png`.

## 5. Compare v13 with v12

Open the v12 site and the v13 site next to each other. Check each item:

1. The site root `/` shows the home page, not a 404 error.
2. The slideshow shows the same images and changes slides.
3. The Products section shows the same products. Each card opens the product page.
4. The Publications section shows the 3 latest blog posts.
5. The Social section shows the Twitter timeline, the Facebook page and the YouTube video.
6. The contact section shows the email and the phone as links, and the button opens `/contact`.
7. The navbar and the footer have the v12 colors, font and links.
8. The page title in the browser tab is the Homepage title.
9. On a phone, the navbar menu opens and the sections show one below the other.

Known differences:

- The product cards show the image of the Website Item. v12 showed the image from the Homepage product row. To change a card image, change the Website Item image.
- The `/home` URL shows the ERPNext home page template, not the Web Page `home`. Use the site root `/`. The Web Page `home` is also at `/rohit-cutting-tools`.

## 6. Template pages

A template page is the page of a Website Item whose item has variants. For example, the home page product cards open template pages. GitHub issues #95 and #108 track this work.

The app changes each template page automatically. You do not need to set anything for each item. The page shows:

1. The image, the name, the template item code and the long description of the Website Item. The description uses the font of the theme, not the fonts in its stored HTML (section 6.2).
2. The common specifications table: each attribute that has the same value for all variants, shown one time above the variant table. For example, Material and Brand. It looks like the variant table: a heading row with the names and one row with the values. On a phone, it shows as one card.
3. A table with one row for each published variant Website Item. The first column is the item code, with a link to the variant page. The next columns are the attributes that are different between the variants. The last column is Price: the price, the stock and the Add to Cart button of the variant (section 6.4).
4. The tabs and the Website Content of the Website Item, if they have content.

The page does not show the ERPNext variant selector. A variant Website Item and an item without variants show the standard ERPNext page.

The website shows only what is published as a Website Item. Website Item links to Item with **Item Code** and to Item Group with **Item Group**:

- The rows are the variant Website Items with **Variant Of** set to the template item and **Published** set. Section 6.3 tells you when a Website Item is published.
- If the template Website Item is not published, the table is empty.
- Website Item has no attributes. The attribute values come from the **Variant Attributes** table of each Item. The columns are the rows of the template Item that have **Use in Description** set, in the order of the table.
- The column headings and the common specification names come from the **Field Name** column of the template Item's **Variant Attributes** table. For example, `d1_mm` shows as "Flute Dia (mm)". If **Field Name** is empty, the page shows the attribute name. To change a heading, edit **Field Name** in the template Item.
- The breadcrumbs come from the Item Group of the Website Item.
- The rows are sorted from small to large by each column, in the order of the template table. For example, they sort by `d1_mm` first, then by `l1_mm`. An attribute with **Numeric Values** set in Item Attribute sorts as a number, so 9 comes before 10. An empty value sorts last. Issue #90 adds a sort order that you can set for each template.
- The website cache can show an old table for some time after a change. Issue #85 covers this.

The item code links to the page of the variant Website Item. Its route is `<template route>/<item code>`. Before the patch `fix_shared_website_item_routes` (issue #99), variants used the route of their template, so some template pages showed a variant. The patch gives each Website Item a route of its own, and it adds a redirect from each old route that only variants used to the template page.

Each row has the item code as its anchor. To link to one variant, add `#<item code>` to the page URL. The browser scrolls to the row and highlights it.

### 6.1 Filter, sort and phones

Above the variant table, a toolbar has a filter box and the item count:

- Type in the filter box to show only the rows that contain all the words. For example, `6 50` shows the rows with 6 and 50 in any column. The count shows "12 of 46 items".
- Click a column heading to sort by that column, from small to large. Click it again to sort from large to small. An arrow shows the sorted column. Number columns sort as numbers. Empty cells always go last.
- The table box has a maximum height and scrolls inside, so the heading row and the item code column stay in view on a long list. When the table is wider than the page, the Price column stays on the right and the attribute columns scroll under it.
- On a phone, each row shows as a card: the item code at the top, then one line for each column with its heading, and a price bar at the bottom with the price, the stock and the button. The toolbar shows a **Sort by** list, because the heading row is not shown.

The filter and the sort run in the browser. The page from the server always has all rows in the default order (section 6), so search engines see all items.

### 6.2 The look of the tables

The styles are in the Website Theme `rigpl-v12`, in **Custom SCSS**, in the section from `// RIGPL tables v5 (#126)` to `// End of RIGPL tables`. Frappe uses one Website Theme for each site, so the table styles are part of the site theme and use its colors and font. The page script only shows or hides rows and marks the sorted column. It does not set colors or sizes.

The variables at the start of the section control the look. For example:

| Variable | Default | What it changes |
|---|---|---|
| `$rigpl-variant-head-bg` | `$dark` | Heading row color |
| `$rigpl-variant-sorted-color` | `$primary` | Heading text of the sorted column |
| `$rigpl-variant-hover-bg` | 12% primary | Row color under the mouse |
| `$rigpl-variant-max-height` | `75vh` | Height of the table box before it scrolls inside |
| `$rigpl-variant-card-breakpoint` | `sm` | Width at which rows show as cards (`xs`, `sm`, `md`) |
| `$rigpl-variant-head-min-width` | `4.5rem` | Minimum column width. A longer heading wraps to 2 or 3 lines |
| `$rigpl-variant-stock-color` | 25% darker primary | Stock text when the variant is in stock |
| `$rigpl-variant-cart-bg` / `$rigpl-variant-enquire-bg` | `$primary` / `$dark` | Add to Cart and Enquire button colors |
| `$rigpl-variant-button-min-width` | `7.5rem` | Width of the Add to Cart and Enquire buttons, so they line up |

The data in the cells sets the width of each column. A heading does not make its column wider: it wraps inside the column, and is centred vertically in the heading row. Attribute values and their headings are centred. The item code is on the left. The Price column is on the right and its text is right-aligned.

The section also sets the font of the product description. The long description HTML from v12 has its own fonts and colors (`<font>` tags and inline styles). The section makes all text in `.product-description` use the font, size and color of the theme, and shows italic text as normal text. Lists and bold text stay. The stored HTML does not change.

To change the look:

1. Open Website Theme `rigpl-v12` in Desk.
2. In **Custom SCSS**, change the variables or the rules in the RIGPL tables section.
3. Save. Frappe compiles the theme.

The reference copy of the section is in `website_data/rigpl_v12_theme.scss`. A new import (section 3) adds it with the rest of the theme. On a site that has the theme already:

- The patch `update_table_styles_in_website_theme` adds the section if it is not there. If the theme has an earlier version that nobody edited, the patch replaces it with the newest version. If somebody edited it, the patch prints a message, and you copy the newest section into Custom SCSS by hand.
- The patch saves the SCSS in the theme, so you can change it in Desk. Saving a Website Theme compiles the SCSS with `node-sass`, which needs Node 14. If node-sass cannot run, the patch saves only the SCSS and the site keeps its old CSS. Then use Node 14, open the Website Theme in Desk and save it.
- For a new version of the section, add the hash of the old version to `UNEDITED_SHA256` in the patch, and change the `#date` after the patch in `patches.txt`, so it runs again.

After that, the theme in the database is the source. A change to the file does not change a site.

To show a variant table on a Web Page, add a block with the web template **RIGPL Variant Table** and set **Website Item** to a published template Website Item.

### 6.3 The Item controls its Website Item

Edit these values in the Item, not in the Website Item. When you save the Item, the app changes its Website Item (issue #105):

| Website Item field | Value |
|---|---|
| **Website Image** and **Thumbnail** | The **Image** of the Item |
| **Published** | Set if the Item is enabled and **PL Item** is "Yes". Else clear. The app does not delete the Website Item, so its route and redirects stay. |
| **Web Long Description** (variant) | The long description that the app makes from the variant attributes |

The long description of a template is not made from attributes. Edit it in the template Website Item.

Each day at 02:10, the job `variant_copy` applies the same rules to all Items. It also corrects a change made in a Website Item by hand.

The patch `fix_shared_website_item_routes` repaired the Website Items that the v13 migration made. It copied the image and the empty web fields from Item, set **PL Item** to "Yes" on the published templates that had published variants, and moved the v12 **Website Item Group** rows from Item to Website Item.

### 6.4 Stock, price and add to cart

The variant table shows the Price column only when **E Commerce Settings** > **Enable Shopping Cart** is set (issue #126). Each cell has up to 3 lines, from top to bottom:

| Line | Shows when | Value |
|---|---|---|
| Price | **Show Price** is set, and the visitor is logged in or **Hide Price for Guest** is not set | The list price and its unit, for example `₹ 245.00 / Nos`. The list price comes from the **Item Price** of the variant. If the variant has no price, the price of the template. The unit is the **Stock UOM** of the variant Website Item. Issue #127 adds the sales UOM. |
| Stock | **Show Stock Availability** is set | `In stock: 100+ Nos`, or `Stock: On request` when there is no stock. The value is the free quantity in the **Website Warehouse** of the variant Website Item, or of the template Website Item if the variant has none. Free quantity is the actual quantity minus the reserved quantities, as ERPNext counts it. |
| Button | Always | **Add to Cart** adds 1 of the variant to the cart. A guest goes to the login page. After the add, the button changes to **In Cart ✓**, a link to the cart. **Enquire** (a dark button of the same size) opens the contact page. |

The stock text comes from **RIGPL Settings** > **Website Settings**:

| Field | Default | Use |
|---|---|---|
| **Website Stock Cap** | 100 | A quantity above this number shows as the cap label. |
| **Website Stock Cap Label** | `{cap}+` | The text above the cap. `{cap}` changes to the cap, for example `100+`. |
| **Website Zero Stock Label** | `On request` | The text when the free quantity is 0. |

An empty field uses its default. The page never contains a quantity above the cap. If **Show Quantity in Website** is not set, the stock line shows "In stock" or the zero stock label.

The price list is the **Default Price List** of the customer of the logged-in user, or of the customer's group. For a guest, or if there is none, it is the **Price List** of E Commerce Settings. An Item Price for one customer only, or out of its valid dates, is not used. The page does not apply Pricing Rules (#77). The cart applies them when it makes the quotation.

The Add to Cart button shows only for a variant that has a price and stock. A variant with **On Backorder** set, or all variants if **Allow items not in stock to be added to cart** is set, can also be added. For any other variant, the cell shows the Enquire button.

The shop columns use two queries for the page (Bin and Item Price), for any number of variants. Click the Price heading to sort by price. If prices are not shown, the heading is Stock and sorts by stock. On a phone, the **Sort by** list also has "Stock ↓". The stock sort uses the capped number, so the page source does not contain a quantity above the cap either.

### 6.5 Routes

A route is the part of the URL after the site name. GitHub issues #97, #100 and #102 track this work. The app makes the routes of Item Groups and Website Items. Do not edit the **Route** field of these documents. Edit the **Website Slug** instead.

| Page | Route | Example |
|---|---|---|
| Category (Item Group) | The Website Slug of each ancestor with **Include in URL** set, then the Website Slug of the group | `carbide/jobber-drills` |
| Template, or item without variants | `<category route>/<slug>` | `carbide/jobber-drills/c0gj-jobber-solid-carbide-drills-metric` |
| Variant | `<template route>/<item code>` | `carbide/jobber-drills/c0gj-jobber-solid-carbide-drills-metric/cr0agbe00md1` |

Rules:

1. A route uses only `a-z`, `0-9` and `-`. A part of a route does not start or end with `-`.
2. A route has at most **Website Route Max Length** characters (RIGPL Settings, default 75).
3. A category route has at most **Website Route Max Depth** groups (RIGPL Settings, default 2).
4. A category route must leave 30 characters for a template slug, so that the variant routes also fit.
5. A slug never gets a random suffix. If a Website Item has no Website Slug, the app makes the slug from the item code. If the item code is too long, the app keeps the first word (the series, for example `122`) and the last words (for example `metric-less-than-3mm`), and removes words from the middle.
6. A route that changes gets a Website Route Redirect (301) from the old route.

The Item Group and Website Item fields:

| Field | Doctype | Use |
|---|---|---|
| **Website Slug** | Item Group | The short name of the group in the URL. Empty: made from the Item Group name. |
| **Include in URL** | Item Group | Put the Website Slug of this group in the route of each descendant group. Set it on the top groups (`carbide`, `hss`). |
| **Website Slug** | Website Item | The name of the item in the URL. Empty: made from the item code. Set it for a better search engine name, for example `ss-flat-end-mill-under-3mm`. |

When you save:

- **Item Group**: the app checks the rules and sets the route. If a rule fails, the save stops and tells you the rule. Then a background job changes the routes of the descendant groups and of their Website Items. The new routes show after some seconds.
- **Website Item**: the app checks the rules and sets the route. If another page has the same route, the save stops. Set a different Website Slug. A template change also starts the background job, so its variants follow.
- **Web Page**: the app checks rules 1 and 2. It does not change the route.

The redirects are rows in Website Settings, table **Route Redirects**. The app adds them. For a template, one row redirects the template and all its variants, for example `old-template(/.*)?` to `/new-template\1`. When a route changes again, the app changes the target of the earlier rows, so a visitor gets one redirect, not a chain. The app deletes a redirect whose source is the route of a live page, because Frappe reads the redirects before the pages. If the job cannot change a route (for example, it is too long), it keeps the old route and writes an Error Log "RIGPL website routes not changed".

The rigpl.com (v12) URLs of items do not have redirect rows. Frappe tries every redirect row on each request, so 2,600 more rows would make every page slower. Instead, the 404 page of this app (`www/404.py`, issue #84) looks up the path in **Item > Route**, which still has the v12 route. It sends a 301 to the most specific live page: the Website Item of the item, then its template, then its Item Group. A variant route `<template route>/<item code>` of a variant that is not published goes to the template. The route of a hidden Item Group goes to its nearest shown ancestor. If nothing matches, the visitor gets the normal 404 page. The lookup runs only when no page matches, and it reads today's routes, so it never makes a redirect chain. After a deploy, run `bench --site <site> clear-website-cache`, because Frappe caches the page context of the Frappe 404 page.

The patch `rebuild_website_routes` made the first short routes. It set the Website Slug of 55 groups from `website_data/route_slugs.json`, only where the Website Slug was empty. To change a slug after the patch, edit the Item Group in Desk.

## 7. Open items

- 16 Web Pages are not published (for example drilling-tools, lathe-tools and services). Decide for each page: publish it, redirect it to an Item Group page, or delete it. Issue #88 has the list.
- To add a new page, make a new Web Page with Content Type "Page Builder". Do not add page HTML to this app.
