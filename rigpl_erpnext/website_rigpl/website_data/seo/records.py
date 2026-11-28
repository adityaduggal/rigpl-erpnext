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


def days_template(name, key):
    """The `QuantitativeValue` of a number of days of a shipping row."""
    properties = [
        expression(prop, "row.{}.{}".format(key, source))
        for prop, source in (("minValue", "min"), ("maxValue", "max"), ("unitCode", "unit"))
    ]
    return schema(name, "QuantitativeValue", "Component", properties, condition="row." + key)


def product_properties(code, full=None):
    """The properties of a `Product`. With `full`, some need a variant below the variant limit."""
    extra = {"condition": full} if full else {}
    return [
        expression("sku", code),
        expression("mpn", code, **extra),
        expression("name", "row.name"),
        expression("url", "row.url"),
        expression("image", "row.image"),
        dict(linked("brand", "Product Brand"), **extra),
        linked_list("additionalProperty", "Property Value"),
        linked_list("offers", "Product Offer"),
    ]


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
        "Return Policy",
        "MerchantReturnPolicy",
        "Component",
        [
            expression("returnPolicyCategory", "row.category"),
            expression("applicableCountry", "row.country"),
            expression("merchantReturnDays", "row.days"),
            expression("returnFees", "row.fees"),
            expression("returnMethod", "row.method"),
        ],
        iterate_over="[site.organization.return_policy] if site.organization.return_policy else []",
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
            linked("hasMerchantReturnPolicy", "Return Policy"),
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
    # products and categories (#265, #266)
    schema("Product Brand", "Brand", "Component", [expression("name", "site.brand")]),
    schema(
        "Property Value",
        "PropertyValue",
        "Component",
        [expression("name", "row.name"), expression("value", "row.value")],
        iterate_over="row.properties",
    ),
    schema(
        "Shipping Region",
        "DefinedRegion",
        "Component",
        [expression("addressCountry", "row.country")],
    ),
    schema(
        "Shipping Charge",
        "MonetaryAmount",
        "Component",
        [expression("value", "row.rate"), expression("currency", "row.currency")],
    ),
    days_template("Handling Time", "handling"),
    days_template("Transit Time", "transit"),
    schema(
        "Delivery Time",
        "ShippingDeliveryTime",
        "Component",
        [linked("handlingTime", "Handling Time"), linked("transitTime", "Transit Time")],
        condition="row.handling or row.transit",
    ),
    schema(
        "Shipping Details",
        "OfferShippingDetails",
        "Component",
        [
            linked("shippingDestination", "Shipping Region"),
            linked("shippingRate", "Shipping Charge"),
            linked("deliveryTime", "Delivery Time"),
        ],
        iterate_over="row.shipping",
    ),
    schema(
        "Product Offer",
        "Offer",
        "Component",
        [
            expression("price", "row.price"),
            expression("priceCurrency", "row.currency"),
            expression("availability", "row.availability"),
            expression("itemCondition", "row.condition"),
            expression("url", "row.url"),
            expression("priceValidUntil", "row.valid_until"),
            linked_list("shippingDetails", "Shipping Details"),
        ],
        merchant_listing=1,
        iterate_over="[row.offer] if row.offer else []",
    ),
    schema(
        "Variant Product",
        "Product",
        "Component",
        product_properties("row.sku", full="row.full") + [expression("size", "row.size")],
        id_expression="{{ row.id }}",
        merchant_listing=1,
        iterate_over="variants",
    ),
    schema(
        "Parent Product Group",
        "ProductGroup",
        "Component",
        [
            expression("name", "row.parent.name"),
            expression("productGroupID", "row.parent.code"),
            expression("url", "row.parent.url"),
        ],
        id_expression="{{ row.parent.id }}",
        condition="row.parent",
    ),
    schema(
        "Product",
        "Product",
        "Page Type",
        product_properties("row.code")
        + [
            expression("description", "row.description | truncate(500)"),
            expression("category", "row.category"),
            linked("isVariantOf", "Parent Product Group"),
        ],
        id_expression="{{ row.id }}",
        merchant_listing=1,
        iterate_over="[item] if item and not item.is_template else []",
    ),
    schema(
        "Product Group",
        "ProductGroup",
        "Page Type",
        [
            expression("name", "row.name"),
            expression("productGroupID", "row.code"),
            expression("url", "row.url"),
            expression("image", "row.image"),
            expression("category", "row.category"),
            expression("description", "row.description | truncate(500)"),
            linked("brand", "Product Brand"),
            expression("variesBy", "row.varies_by"),
            linked_list("additionalProperty", "Property Value"),
            linked_list("hasVariant", "Variant Product"),
        ],
        id_expression="{{ row.id }}",
        iterate_over="[item] if item and item.is_template else []",
    ),
    schema(
        "Listing Item",
        "ListItem",
        "Component",
        [
            expression("position", "row.position"),
            expression("url", "row.url"),
            expression("name", "row.name"),
        ],
        iterate_over="listing",
    ),
    schema(
        "Category Listing",
        "ItemList",
        "Component",
        [linked_list("itemListElement", "Listing Item")],
        condition="listing",
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
            linked("mainEntity", "Category Listing"),
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
    # navigation and breadcrumbs (#264)
    schema(
        "Breadcrumb Item",
        "ListItem",
        "Component",
        [expression("position", "row.position"), expression("name", "row.name"), expression("item", "row.url")],
        iterate_over="page.crumbs",
    ),
    schema(
        "Breadcrumbs",
        "BreadcrumbList",
        "Breadcrumb",
        [linked_list("itemListElement", "Breadcrumb Item")],
        id_expression="{{ page.url }}#breadcrumb",
        condition="page.crumbs",
    ),
    schema(
        "Top Bar",
        "SiteNavigationElement",
        "Navigation",
        [expression("name", "row.name"), expression("url", "row.url")],
        id_expression="{{ site.url }}/#navigation-{{ row.position }}",
        iterate_over="nav.top_bar",
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
        ["Product Group", "Product"],
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
