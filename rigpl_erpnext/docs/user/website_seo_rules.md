# SEO Rules and SEO Settings

An **SEO Rule** sets the title, description and other meta tags of one page type. **SEO Settings** gives the values for the whole website. A change needs no code deploy.

Only the role **Website Manager** can open them.

## Which rule a page uses

A rule matches a page when each condition that you set is true.

| Field | Condition |
|---|---|
| Reference DocType | The page is a document of this DocType, for example `Web Page` or `Website Item`. |
| Route Pattern | The route matches, for example `blog/*`. `*` is any text, also `/`. Do not start with `/`. |

A page uses one rule: the matching rule with the highest **Priority**. At the same priority, a rule with both conditions wins, then the first name.

## Which value wins

The last one in this list wins.

1. SEO Settings (title, description and site name only).
2. The SEO Rule.
3. The fields **Meta Title**, **Meta Description** and **Meta Image** of the page document. They replace a rule or settings value.
4. **Website Route Meta** for the route.

An empty field, or a template with an empty result, changes nothing.

## Templates

Each template is text with Jinja, for example `{{ page.h1 }} | {{ site.brand }}`. Plain text is also correct. The variables are the same as in a Schema Template: `site`, `page` and `doc`. **Site Name** in SEO Settings is also Jinja text. Use `page.h1` for the title of the page without the website title prefix.

| Field | Tags |
|---|---|
| Title Template | `<title>`, `og:title`, `twitter:title` |
| Description Template | `description`, `og:description`, `twitter:description` |
| Canonical Template | the canonical link and `og:url`. A route becomes a full URL. |
| Robots Template | `robots`. It cannot remove a `noindex` that the page already has. |
| OG Type Template | `og:type` |
| Image Template | `og:image`, `twitter:image` |
| Twitter Card | `twitter:card` |

**Schema Templates:** the JSON-LD templates (Applies To = **Page Type**) that the pages of this rule output.

If a template has an error, the page keeps the value before it. The **Error Log** has the rule name and the route.

## Length limits

The title limit is 60 characters and the description limit is 160. You can change both in SEO Settings.

- A longer description is cut at a word.
- A longer title is not cut.
- The save of a rule shows a warning for a longer text. Set **Sample Route** to check a template that has variables.

## Default rules

The system creates these rules one time after `migrate`. The button **Create Missing Records** in **SEO Settings** creates the ones that do not exist. A rule that exists is never changed.

| Rule | Reference DocType | Title | Schema Template |
|---|---|---|---|
| `Product pages` | Website Item | the Website Item name | `Product Group`, `Product` |
| `Item Group pages` | Item Group | the Item Group and the brand | `Collection Page` |
| `Web Pages` | Web Page | the H1 and the brand | none |
| `Blog posts` | Blog Post | the H1 | `Blog Posting` |
| `About page` | route `about` | no change | `About Page` |
| `Contact pages` | route `contact*` | no change | `Contact Page` |

All have Priority `10`. The **Site Name** of SEO Settings becomes `{{ site.brand }}` if it is empty. To change a text, open the rule. To stop a rule, clear **Enabled**.

Many product names are longer than 60 characters. The title stays complete. For a better description of one page, fill its **Meta Description**.

## A rule for a group of routes

To give all HSS product pages another title, make a rule with Reference DocType `Website Item`, Route Pattern `hss/*`, Priority `20` and Title Template `{{ doc.web_item_name }} \| {{ site.brand }}`.

## One page only

Use **Website Route Meta**. Its name is the route, for example `news`. Add rows with the keys `title` and `description`. These rows win over each rule.

## Check the result

Open the page on the website and view its source. Check `<title>`, `<meta name="description">` and the canonical link. After a change, reload the page. If it does not change, run **Clear Website Cache**.

## Image alt text

Every image on a page gets an alt text. The first source found wins:

1. The alt text set in that place: the HTML `alt` attribute, the **Website Image Alt** of a Website Item, or the slide **Heading**.
2. The newest comment on the **File** that starts with `Alt:`, for example `Alt: 4 flute carbide end mill`.
3. The file name, if it has two or more words.
4. The **Image Alt Template** of the SEO Rule. Empty: the H1 of the page.

To set an alt text for an image everywhere, open its **File** and add the comment. Then run **Clear Website Cache** or save the page.

## Image check

When you save a Web Page, Blog Post, Website Slideshow, Website Item, Item Group, Website Settings, Contact Us Settings or About Us Settings:

- A **new** image that has only source 4 stops the save.
- An image that the document **had before** only shows a warning with a link to the File.

Only public files of this site are checked. `alt=""` marks a decorative image. A migrate, an import and a system save are never stopped.

Do not rename a file that the website uses: its address changes. Add the `Alt:` comment.

## Headings

Each page has one H1 text. The page shows it as its heading and as the last breadcrumb. The browser tab and the search result show the **title**.

| Value | Change it here |
|---|---|
| H1 | **H1 Template** of the SEO Rule. Empty: the title of the document. |
| Headings of a template page | **SEO Settings** > Specifications Heading and Variants Heading |
| Heading level of a RIGPL block | **Heading Level** in the block. Empty: 2. |

A Web Page that shows no H1 gets one that only screen readers and search engines see. Switch on **Show Title**, or write an H1 in the page, to show it.

The footer headings, the blog author name and the address on `/contact` come from Frappe templates. Their levels do not change.
