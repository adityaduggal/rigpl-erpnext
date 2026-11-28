"""
The default Schema Templates, SEO Rules and SEO Settings (#263). Each business value is an
expression that reads the database through the SEO context. Managers edit the records in Desk.
"""

ORGANIZATION_ID = "{{ site.url }}/#organization"
HTML_TO_TEXT = "replace('><', '> <') | striptags"


def expression(name, value, **extra):
    return dict(property=name, value=value, value_type="Expression", **extra)


def linked(name, template):
    return dict(property=name, value_type="Template", linked_template=template)


def schema(name, schema_type, applies_to, properties, **values):
    return dict(template_name=name, schema_type=schema_type, applies_to=applies_to, properties=properties, **values)


def linked_list(name, template):
    return dict(property=name, value_type="Template List", linked_template=template)


def item_list(name, web_template, element_template, source):
    """The `ItemList` of a block that has a list of records."""
    return schema(
        name,
        "ItemList",
        "Web Template",
        [expression("name", "block.get('title')"), linked_list("itemListElement", element_template)],
        web_template=web_template,
        id_expression="{{ page.url }}#itemlist-{{ block.idx }}",
        condition="block." + source,
    )


def rule(name, doctype, schema_templates=(), **templates):
    rows = [{"schema_template": template} for template in schema_templates]
    return dict(rule_name=name, reference_doctype=doctype, priority=10, schema_templates=rows, **templates)


# a template comes after the templates that it links to
SCHEMA_TEMPLATES = [
    schema(
        "Company Address",
        "PostalAddress",
        "Component",
        [
            expression("streetAddress", "site.organization.address.street"),
            expression("addressLocality", "site.organization.address.city"),
            expression("addressRegion", "site.organization.address.state"),
            expression("postalCode", "site.organization.address.pincode"),
            expression("addressCountry", "site.organization.address.country_code"),
        ],
        condition="site.organization.address",
    ),
    schema(
        "Company",
        "Organization",
        "Site",
        [
            expression("name", "site.brand"),
            expression("url", "site.url"),
            expression("legalName", "site.organization.legal_name"),
            expression("logo", "site.organization.logo"),
            expression("email", "site.organization.email"),
            expression("telephone", "site.organization.telephone"),
            expression("foundingDate", "site.organization.founding_date"),
            expression("sameAs", "site.organization.same_as"),
            linked("address", "Company Address"),
        ],
        id_expression=ORGANIZATION_ID,
    ),
    schema(
        "Company Ref",
        "Organization",
        "Component",
        [expression("name", "site.brand"), expression("url", "site.url")],
        id_expression=ORGANIZATION_ID,
    ),
    schema(
        "WebSite",
        "WebSite",
        "Site",
        [expression("url", "site.url"), expression("name", "site.brand"), linked("publisher", "Company Ref")],
        id_expression="{{ site.url }}/#website",
    ),
    schema(
        "WebPage",
        "WebPage",
        "Site",
        [expression("url", "page.url"), expression("name", "page.h1")],
        id_expression="{{ page.url }}#webpage",
    ),
    schema(
        "Product Group",
        "ProductGroup",
        "Page Type",
        [
            expression("name", "doc.web_item_name"),
            expression("productGroupID", "doc.item_code"),
            expression("url", "page.url"),
            expression("image", "doc.get('website_image') | abs_url"),
            expression("category", "doc.item_group"),
            expression(
                "description",
                "(doc.get('web_long_description') or doc.get('description') or '') | "
                + HTML_TO_TEXT
                + " | truncate(500)",
            ),
        ],
        id_expression="{{ page.url }}#productgroup",
        condition="doc.get('has_variants')",
    ),
    schema(
        "Collection Page",
        "CollectionPage",
        "Page Type",
        [
            expression("name", "doc.name"),
            expression("url", "page.url"),
            expression("image", "doc.get('image') | abs_url"),
            expression(
                "description", "(doc.get('description') or '') | " + HTML_TO_TEXT + " | truncate(300)"
            ),
        ],
        id_expression="{{ page.url }}#collection",
    ),
    schema(
        "Blog Posting",
        "BlogPosting",
        "Page Type",
        [
            expression("headline", "doc.title"),
            expression("url", "page.url"),
            expression("datePublished", "doc.published_on"),
            expression("dateModified", "doc.modified"),
            expression("description", "(doc.get('blog_intro') or '') | striptags"),
            expression("image", "doc.get('meta_image') | abs_url"),
            linked("publisher", "Company Ref"),
        ],
        id_expression="{{ page.url }}#article",
    ),
    # Web Page blocks (#269)
    schema(
        "Product List Item",
        "ListItem",
        "Component",
        [
            expression("position", "row.position"),
            expression("url", "row.url"),
            expression("name", "row.title"),
        ],
        iterate_over="block.products",
    ),
    item_list("Item Card Group List", "Item Card Group", "Product List Item", "products"),
    item_list("Item Cards List", "RIGPL Item Cards", "Product List Item", "products"),
    schema(
        "Block Blog Author",
        "Person",
        "Component",
        [expression("name", "row.author")],
        condition="row.author",
    ),
    schema(
        "Block Blog Post",
        "BlogPosting",
        "Component",
        [
            expression("headline", "row.title"),
            expression("url", "row.url"),
            expression("datePublished", "row.published_on"),
            expression("description", "row.description"),
            expression("image", "row.image"),
            linked("author", "Block Blog Author"),
        ],
    ),
    schema(
        "Blog List Item",
        "ListItem",
        "Component",
        [expression("position", "row.position"), linked("item", "Block Blog Post")],
        iterate_over="block.posts",
    ),
    item_list("Latest Blogs List", "RIGPL Latest Blogs", "Blog List Item", "posts"),
    schema(
        "Slideshow Images",
        "ImageObject",
        "Web Template",
        [
            expression("contentUrl", "row.image"),
            expression("name", "row.heading"),
            expression("description", "row.description"),
        ],
        web_template="Slideshow",
        id_expression="{{ page.url }}#slide-{{ block.idx }}-{{ row.idx }}",
        iterate_over="block.slides",
        condition="row.image",
    ),
    schema(
        "Social Video",
        "VideoObject",
        "Web Template",
        [
            expression("name", "block.video_title"),
            expression("thumbnailUrl", "https://i.ytimg.com/vi/{{ block.youtube_video_id }}/hqdefault.jpg"),
            expression("uploadDate", "block.video_upload_date"),
            expression("embedUrl", "https://www.youtube.com/embed/{{ block.youtube_video_id }}"),
        ],
        web_template="RIGPL Social Feeds",
        id_expression="{{ page.url }}#video-{{ block.idx }}",
        condition="block.get('youtube_video_id') and block.get('video_title') "
        "and block.get('video_upload_date')",
    ),
    schema(
        "Block Contact Point",
        "ContactPoint",
        "Component",
        [
            expression("telephone", "block.get('phone')"),
            expression("email", "block.get('email')"),
            expression("url", "block.get('cta_url') | abs_url"),
        ],
    ),
    schema(
        "Contact Strip",
        "Organization",
        "Web Template",
        [
            expression("name", "site.brand"),
            expression("url", "site.url"),
            linked("contactPoint", "Block Contact Point"),
        ],
        web_template="RIGPL Contact Strip",
        id_expression=ORGANIZATION_ID,
        condition="block.get('phone') or block.get('email')",
    ),
]

SEO_RULES = [
    rule(
        "Product pages",
        "Website Item",
        ["Product Group"],
        title_template="{{ doc.web_item_name }}",
        description_template="Buy {{ doc.web_item_name }} from {{ site.brand }}. Category: {{ doc.item_group }}.",
        og_type_template="product",
    ),
    rule(
        "Item Group pages",
        "Item Group",
        ["Collection Page"],
        title_template="{{ doc.name }} | {{ site.brand }}",
        description_template="{{ ((doc.get('description') or '') | "
        + HTML_TO_TEXT
        + ") or (doc.name ~ ' from ' ~ site.brand ~ '.') }}",
        image_template="{{ doc.get('image') or '' }}",
        og_type_template="website",
    ),
    rule(
        "Web Pages",
        "Web Page",
        title_template="{{ page.h1 }} | {{ site.brand }}",
        description_template="{{ page.h1 }}: information from {{ site.brand }}.",
        og_type_template="website",
    ),
    rule(
        "Blog posts",
        "Blog Post",
        ["Blog Posting"],
        title_template="{{ page.h1 }}",
        description_template="{{ doc.get('blog_intro') or '' }}",
        og_type_template="article",
        twitter_card="summary_large_image",
    ),
]

# its Route Pattern is the home page of Website Settings, set when it is created
HOME_RULE = dict(
    rule(
        "Home page",
        "Web Page",
        title_template="{{ page.h1 }}",
        description_template="{{ page.h1 }}: information from {{ site.brand }}.",
        image_template="{{ site.organization.logo }}",
        og_type_template="website",
        twitter_card="summary_large_image",
    ),
    priority=20,
)

# only an empty field of SEO Settings gets a value
SETTINGS = {"site_name": "{{ site.brand }}"}
