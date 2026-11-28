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

Each template is text with Jinja, for example `{{ page.h1 }} | Rohit Cutting Tools`. Plain text is also correct. The variables are the same as in a Schema Template: `site`, `page` and `doc`. Use `page.h1` for the title of the page without the website title prefix.

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

## Examples

| Reference DocType | Field | Value |
|---|---|---|
| `Website Item` | Title Template | `{{ doc.web_item_name }}` |
| `Website Item` | Description Template | `Buy {{ doc.web_item_name }} from Rohit Cutting Tools.` |
| `Website Item` | OG Type Template | `product` |
| `Blog Post` | Title Template | `{{ page.h1 }} \| Blog` |
