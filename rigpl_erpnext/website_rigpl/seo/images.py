"""
Alt text for website images (#267). The first source found wins:
the alt text set in that place, the newest "Alt:" comment on the File, a readable file name,
and the image alt template of the SEO Rule. A save blocks a new image that only has the last.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote

import frappe
from frappe.utils import escape_html, get_link_to_form

from .sandbox import plain_text

FILES = "/files/"
ALT_PREFIX = "alt:"
# the context values of a page that hold HTML from the database
HTML_KEYS = (
    "page_builder_html",
    "main_section",
    "content",
    "introduction",
    "brand_html",
    "footer_address",
    "head_html",
)
# DocType: (fields with HTML or Markdown, (image field, field with its alt text))
IMAGE_FIELDS = {
    "Web Page": (("main_section", "main_section_md", "main_section_html"), (("meta_image", None),)),
    "Blog Post": (("content", "content_md", "content_html"), (("meta_image", None),)),
    "Website Item": (
        ("web_long_description", "website_content"),
        (("website_image", "website_image_alt"),),
    ),
    "Item Group": (("description",), (("image", None),)),
    "Website Settings": (("brand_html", "address", "head_html"), ()),
    "Contact Us Settings": (("introduction",), ()),
    "About Us Settings": (("company_introduction",), ()),
    "Website Slideshow": ((), ()),
}
TAG = re.compile(r"<script\b.*?</script>|<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
ATTRIBUTE = r"""\s{}\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))"""
MARKDOWN_IMAGE = re.compile(r"""!\[([^\]]*)\]\(\s*([^)]*?)(?:\s+["'][^)]*["'])?\s*\)""")
# a suffix that Frappe adds to a file name that exists
HASH_SUFFIX = re.compile(r"[\s_-]*(?=[a-f]*\d)[0-9a-f]{6}$")


def get_file_key(url: str) -> Optional[str]:
    """The `file_url` of a public file of this site, else None."""
    url = unquote(str(url or "").strip()).split("?")[0]
    start = url.find(FILES)
    if start < 0 or url.startswith("/private/"):
        return None
    return url[start:]


def get_readable_name(url: str) -> str:
    """The file name as text, if it has two or more words. Else an empty string."""
    name = unquote(str(url or "")).split("?")[0].rsplit("/", 1)[-1]
    name = HASH_SUFFIX.sub("", name.rsplit(".", 1)[0].split("@")[0])
    text = " ".join(re.sub(r"[_\-.·+]+", " ", name).split())
    words = re.findall(r"(?<![A-Za-z0-9])[A-Za-z]{3,}(?![A-Za-z0-9])", text)
    return text if len(words) >= 2 else ""


def get_comment_alts(keys: list) -> Dict[str, str]:
    """{file_url: text} of the newest "Alt:" comment on any File of the URL, in one query."""
    if not keys:
        return {}
    file = frappe.qb.DocType("File")
    comment = frappe.qb.DocType("Comment")
    rows = (
        frappe.qb.from_(file)
        .inner_join(comment)
        .on((comment.reference_name == file.name) & (comment.reference_doctype == "File"))
        .select(file.file_url, comment.content)
        .where(
            file.file_url.isin(keys)
            & (comment.comment_type == "Comment")
            & comment.content.like("%{}%".format(ALT_PREFIX))
        )
        .orderby(comment.creation, order=frappe.qb.desc)
    ).run(as_dict=True)
    alts = {}
    for row in rows:
        text = plain_text(row.content)
        if text.lower().startswith(ALT_PREFIX):
            alts.setdefault(row.file_url, text[len(ALT_PREFIX) :].strip())
    return {key: value for key, value in alts.items() if value}


def get_file_alts(urls: list) -> Dict[str, str]:
    """{file_url: alt} of the URLs that have a comment or a readable name."""
    keys = list({key for key in map(get_file_key, urls) if key})
    comments = get_comment_alts(keys)
    found = {key: comments.get(key) or get_readable_name(key) for key in keys}
    return {key: value for key, value in found.items() if value}


def get_attribute(tag: str, name: str) -> Optional[str]:
    """None when the tag does not have the attribute."""
    match = re.search(ATTRIBUTE.format(name), tag, re.IGNORECASE)
    return next((group for group in match.groups() if group is not None), "") if match else None


def get_untagged(html: str) -> List[str]:
    """The `<img>` tags that have no alt attribute. Tags inside a script are not used."""
    return [
        tag
        for tag in TAG.findall(str(html or ""))
        if tag.lower().startswith("<img") and get_attribute(tag, "alt") is None
    ]


def add_alt(html: str, alts: Dict[str, str], fallback: str) -> str:
    def replace(match):
        tag = match.group(0)
        if not tag.lower().startswith("<img") or get_attribute(tag, "alt") is not None:
            return tag
        # a tracking pixel is not content
        if get_attribute(tag, "width") == "1":
            text = ""
        else:
            text = alts.get(get_file_key(get_attribute(tag, "src"))) or fallback
        return '{} alt="{}"{}'.format(tag[:4], escape_html(text), tag[4:])

    return TAG.sub(replace, str(html))


def fill_page(context, values: dict, fallback: str) -> None:
    """Gives every image of the page an alt text. Nothing is saved."""
    pages = {key: values.get(key, context.get(key)) for key in HTML_KEYS}
    pages = {key: html for key, html in pages.items() if html and get_untagged(html)}
    doc = context.get("doc")
    item = doc if getattr(doc, "doctype", None) == "Website Item" else None
    slides = context.get("slides") if item else None

    urls = [get_attribute(tag, "src") for html in pages.values() for tag in get_untagged(html)]
    if item:
        urls += [item.get("website_image")] + [slide.get("image") for slide in slides or []]
    alts = get_file_alts(urls)

    for key, html in pages.items():
        values[key] = add_alt(html, alts, fallback)
    if not item:
        return
    if not item.get("website_image_alt"):
        item.website_image_alt = alts.get(get_file_key(item.get("website_image"))) or fallback
    if slides:
        # ERPNext writes the slide heading as the alt text
        values["slides"] = [
            frappe._dict(
                image=slide.get("image"),
                heading=slide.get("heading")
                or alts.get(get_file_key(slide.get("image")))
                or fallback,
            )
            for slide in slides
        ]


def get_document_images(doc) -> List[Tuple[str, str]]:
    """(file_url, alt text set in that place) of the public images of a website document."""
    html_fields, image_fields = IMAGE_FIELDS[doc.doctype]
    images = []
    for field in html_fields:
        text = str(doc.get(field) or "")
        for tag in TAG.findall(text):
            if tag.lower().startswith("<img"):
                # an empty alt text marks a decorative image
                alt = get_attribute(tag, "alt")
                images.append((get_attribute(tag, "src"), None if alt is None else alt or "-"))
        images += [(url, alt) for alt, url in MARKDOWN_IMAGE.findall(text)]
    images += [(doc.get(field), doc.get(alt) if alt else None) for field, alt in image_fields]
    if doc.doctype == "Website Slideshow":
        images += [(row.get("image"), row.get("heading")) for row in doc.get("slideshow_items") or []]
    return [(get_file_key(url), (alt or "").strip()) for url, alt in images if get_file_key(url)]


def validate_images(doc, method=None) -> None:
    """Blocks a save that adds an image with no alt text and no readable name. Warns for the
    images that the document had before. Never blocks a migrate, an import or a system save."""
    missing = get_missing(doc)
    if not missing:
        return
    before = doc.get_doc_before_save()
    old = {url for url, _ in get_document_images(before)} if before else set()
    new = [url for url in missing if url not in old]
    flags = frappe.flags
    system = flags.in_migrate or flags.in_install or flags.in_patch or flags.in_import
    if new and not system and not doc.flags.ignore_permissions:
        frappe.throw(describe(new), title="Image without alt text", exc=frappe.ValidationError)
    frappe.msgprint(describe(missing), title="Images without alt text", indicator="orange")


def get_missing(doc) -> List[str]:
    urls = list(dict.fromkeys(url for url, alt in get_document_images(doc) if not alt))
    found = get_file_alts(urls)
    return [url for url in urls if url not in found]


def describe(urls: List[str]) -> str:
    files = dict(
        frappe.get_all(
            "File", filters={"file_url": ["in", urls]}, fields=["file_url", "name"], as_list=True
        )
    )
    lines = [
        get_link_to_form("File", files[url], escape_html(url)) if url in files else escape_html(url)
        for url in urls
    ]
    return (
        "Give each image an alt text, or add a comment that starts with <b>Alt:</b> to its File, "
        "or upload it with a name of two or more words.<br><br>{}".format("<br>".join(lines))
    )
