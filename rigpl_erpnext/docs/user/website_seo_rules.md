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
| `Product pages` | Website Item | the Website Item name | `Product Group` |
| `Item Group pages` | Item Group | the Item Group and the brand | `Collection Page` |
| `Web Pages` | Web Page | the H1 and the brand | none |
| `Blog posts` | Blog Post | the H1 | `Blog Posting` |

All have Priority `10`. The **Site Name** of SEO Settings becomes `{{ site.brand }}` if it is empty. To change a text, open the rule. To stop a rule, clear **Enabled**.

Many product names are longer than 60 characters. The title stays complete. For a better description of one page, fill its **Meta Description**.

## A rule for a group of routes

To give all HSS product pages another title, make a rule with Reference DocType `Website Item`, Route Pattern `hss/*`, Priority `20` and Title Template `{{ doc.web_item_name }} \| {{ site.brand }}`.

## One page only

Use **Website Route Meta**. Its name is the route, for example `news`. Add rows with the keys `title` and `description`. These rows win over each rule.

## Check the result

Open the page on the website and view its source. Check `<title>`, `<meta name="description">` and the canonical link. After a change, reload the page. If it does not change, run **Clear Website Cache**.
