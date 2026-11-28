"""The properties that a schema.org type must have. Each group means "one of"."""
from __future__ import annotations

from typing import Iterable, List, Tuple

PRODUCT_TYPES = ("Product", "ProductGroup")
ARTICLE_GROUPS = [("headline",)]
OFFER_PRICE = ("price", "priceSpecification")

REQUIRED = {
    "Product": [("name",), ("offers", "review", "aggregateRating")],
    # the offers of a ProductGroup are on its variants
    "ProductGroup": [("name",)],
    "Offer": [OFFER_PRICE],
    "BreadcrumbList": [("itemListElement",)],
    "Organization": [("name",), ("url",)],
    "Article": ARTICLE_GROUPS,
    "BlogPosting": ARTICLE_GROUPS,
    "NewsArticle": ARTICLE_GROUPS,
    "LocalBusiness": [("name",), ("address",)],
    "VideoObject": [("name",), ("thumbnailUrl",), ("uploadDate",)],
}

MERCHANT_LISTING = {
    **{schema_type: [("name",), ("image",), ("offers",)] for schema_type in PRODUCT_TYPES},
    "Offer": [OFFER_PRICE, ("priceCurrency", "priceSpecification")],
}


def required_groups(schema_type: str, merchant_listing: bool) -> List[Tuple[str, ...]]:
    if merchant_listing and schema_type in MERCHANT_LISTING:
        return MERCHANT_LISTING[schema_type]
    return REQUIRED.get(schema_type, [])


def missing(groups: List[Tuple[str, ...]], properties: Iterable[str]) -> List[str]:
    present = set(properties)
    return [" or ".join(group) for group in groups if not present.intersection(group)]
