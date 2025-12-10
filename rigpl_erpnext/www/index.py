from __future__ import unicode_literals
import frappe

no_cache = 1
no_sitemap = 1


def get_context(context):
    db = frappe.db

    # ----- Blogs (optional - removed in your site) -----
    if db.exists("DocType", "Blog Post"):
        context.blogs = frappe.get_all(
            "Blog Post",
            fields=["title", "blogger", "blog_intro", "route"],
            filters={"published": 1},
            order_by="modified desc",
            limit=3,
        )
    else:
        context.blogs = []

    # ----- Homepage settings (old v12 Homepage doctype - missing in v15+) -----
    # Fallback to an empty object with .products = [] so template doesn't break
    context.homepage_settings = frappe._dict(products=[])
    if db.exists("DocType", "Homepage") and db.exists("Homepage", "Homepage"):
        try:
            context.homepage_settings = frappe.get_doc("Homepage", "Homepage")
        except Exception:
            context.homepage_settings = frappe._dict(products=[])

    context.get_item_route = get_item_route

    # ----- Custom sections (Homepage Section - also optional) -----
    context.custom_sections = []
    if db.exists("DocType", "Homepage Section"):
        section_names = db.get_all(
            "Homepage Section",
            order_by="section_order asc",
            pluck="name",
        )
        context.custom_sections = [
            frappe.get_doc("Homepage Section", name) for name in section_names
        ]

    # ----- Social handles (static) -----
    context.twitter_handle = "rigpl1"
    context.facebook_id = "RohitCuttingTools"
    context.youtube_channel_id = "UCrVTlU5g3SeNSZDc1MQV8GA"
    context.youtube_video_id = "8cER4UUPxK8"
    context.explore_link = "/hss-tools"

    # ----- Contact info (Contact Us Settings - optional) -----
    context.email = ""
    context.phone = ""
    if db.exists("DocType", "Contact Us Settings"):
        context.email = db.get_single_value("Contact Us Settings", "email_id") or ""
        context.phone = db.get_single_value("Contact Us Settings", "phone") or ""

    # ----- Slideshow (Homepage Settings + Website Slideshow - both optional) -----
    context.slides = []
    context.slideshow = None
    if db.exists("DocType", "Homepage Settings"):
        slideshow_name = db.get_single_value("Homepage Settings", "hero_slideshow")
        if slideshow_name and db.exists("Website Slideshow", slideshow_name):
            try:
                slideshow = frappe.get_doc("Website Slideshow", slideshow_name)
                context.slides = slideshow.slideshow_items
                context.slideshow = slideshow
            except Exception:
                context.slides = []
                context.slideshow = None

    # ----- Page title (Homepage doctype - optional) -----
    context.title = ""
    if db.exists("DocType", "Homepage"):
        context.title = db.get_single_value("Homepage", "title") or ""

    return context


def get_item_route(item_code):
    route = frappe.db.get_value("Item", item_code, "route")
    return route or f"/items/{item_code}"
