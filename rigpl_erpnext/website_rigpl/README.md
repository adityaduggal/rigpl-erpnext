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

This app adds four web templates in the module Website-RIGPL. `bench migrate` installs them.

| Web Template | What it shows | Fields |
|---|---|---|
| RIGPL Social Feeds | The Twitter timeline, the Facebook page and a YouTube video, in three columns | Title, Twitter Handle, Facebook Page, YouTube Channel ID, YouTube Video ID |
| RIGPL Contact Strip | "Have more questions?" with the email, the phone and a button | Title, Email, Phone, Button Label, Button URL |
| RIGPL Latest Blogs | The latest published Blog Posts as cards | Title, Number of Blog Posts |
| RIGPL Homepage Section | One Homepage Section with its cards or its HTML | Homepage Section |

The home page also uses two standard templates:

- **Slideshow** shows a Website Slideshow. Edit the images in the Website Slideshow document.
- **Item Card Group** shows up to 12 Website Items. Each card is a link to a Website Item.

Notes:

- RIGPL Latest Blogs reads the Blog Posts each time the page is built. When you publish, change or delete a Blog Post, the app clears the website cache, so the home page shows the change.
- RIGPL Homepage Section reads the Homepage Section document. To change the cards, edit the Homepage Section document, not the block.
- Do not edit these four web templates in Desk. They are standard templates, and the next update replaces your changes. If you need a different layout, ask a developer to change the template files in `website_rigpl/web_template/`.

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

## 6. Open items

- 16 Web Pages are not published (for example drilling-tools, lathe-tools and services). Decide for each page: publish it, redirect it to an Item Group page, or delete it. Issue #88 has the list.
- To add a new page, make a new Web Page with Content Type "Page Builder". Do not add page HTML to this app.
