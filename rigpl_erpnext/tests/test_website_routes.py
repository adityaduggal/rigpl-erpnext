import re
import unittest

from rigpl_erpnext.website_rigpl.legacy_routes import pick_item_target
from rigpl_erpnext.website_rigpl.routes import (
    Redirect,
    build_group_route,
    build_item_route,
    check_group_budget,
    cut_slug,
    hijacking_redirects,
    plan_route_rebuild,
    plan_shared_route_fixes,
    retarget_redirects,
    slugify,
    validate_route,
)

SHARED = "tools/end-mills/330-end-mill"


def web_item(name, item_code, route, variant_of=None):
    return {
        "name": name,
        "item_code": item_code,
        "route": route,
        "has_variants": 0 if variant_of else 1,
        "variant_of": variant_of,
    }


class TestSharedRouteFixes(unittest.TestCase):
    def test_template_keeps_route_and_variants_nest_under_it(self):
        rows = [
            web_item("W1", "V-A1", SHARED, "330-Metric"),
            web_item("W2", "330-Metric", SHARED),
            web_item("W3", "V-A2", SHARED, "330-Metric"),
        ]
        new_routes, redirects = plan_shared_route_fixes(rows, {"330-Metric": SHARED})

        self.assertEqual(new_routes, {"W1": SHARED + "/v-a1", "W3": SHARED + "/v-a2"})
        self.assertEqual(redirects, [])

    def test_second_template_moves_and_its_variants_follow(self):
        rows = [
            web_item("W1", "330-Metric", SHARED),
            web_item("W2", "330-BSW", SHARED),
            web_item("W3", "V-B1", SHARED, "330-BSW"),
        ]
        new_routes, _ = plan_shared_route_fixes(rows, {"330-Metric": SHARED, "330-BSW": "old-v12-route"})

        bsw_route = "tools/end-mills/330-bsw"
        self.assertEqual(new_routes, {"W2": bsw_route, "W3": bsw_route + "/v-b1"})

    def test_route_owner_is_the_template_with_the_same_item_route(self):
        rows = [web_item("W1", "330-Metric", SHARED), web_item("W2", "330-BSW", SHARED)]
        new_routes, _ = plan_shared_route_fixes(rows, {"330-BSW": SHARED})

        self.assertEqual(list(new_routes), ["W1"])

    def test_route_with_only_variants_redirects_to_their_template(self):
        old = "tools/end-mills/old-v12-variant-route"
        rows = [
            web_item("W1", "330-Metric", SHARED),
            web_item("W2", "V-A1", old, "330-Metric"),
            web_item("W3", "V-A2", old, "330-Metric"),
        ]
        new_routes, redirects = plan_shared_route_fixes(rows, {})

        self.assertEqual(new_routes, {"W2": SHARED + "/v-a1", "W3": SHARED + "/v-a2"})
        self.assertEqual(redirects, [(old, SHARED)])

    def test_second_run_changes_nothing(self):
        rows = [
            web_item("W1", "330-Metric", SHARED),
            web_item("W2", "330-BSW", SHARED),
            web_item("W3", "V-A1", SHARED, "330-Metric"),
        ]
        new_routes, _ = plan_shared_route_fixes(rows, {})
        fixed = [dict(row, route=new_routes.get(row["name"], row["route"])) for row in rows]

        self.assertEqual(plan_shared_route_fixes(fixed, {}), ({}, []))

    def test_plan_that_makes_a_new_shared_route_fails(self):
        rows = [
            web_item("W1", "330-Metric", SHARED),
            web_item("W2", "V-A1", SHARED, "330-Metric"),
            web_item("W3", "X", SHARED + "/v-a1"),
        ]
        with self.assertRaises(ValueError):
            plan_shared_route_fixes(rows, {})


STAINLESS = [
    "122-4-Flute-GP-Stainless Steel-Solid Carbide Flat End Mills-Metric-less-than-3mm",
    "122-4-Flute-GP-Stainless Steel-Solid Carbide Flat End Mills-Metric-3-to-4mm",
    "122-4-Flute-GP-Stainless Steel-Solid Carbide Flat End Mills-Metric-4.1-to-9.9mm",
    "122-4-Flute-GP-Stainless Steel-Solid Carbide Flat End Mills-Metric-10mm-Above",
]


def group(name, parent, slug=None, include=0, route="", web=1):
    return {
        "name": name,
        "parent_item_group": parent,
        "item_group_name": name,
        "website_slug": slug,
        "include_in_url": include,
        "route": route,
        "web": web,
    }


def item(name, item_code, item_group, route, variant_of=None, has_variants=None, slug=None):
    return {
        "name": name,
        "item_code": item_code,
        "item_group": item_group,
        "route": route,
        "has_variants": (0 if variant_of else 1) if has_variants is None else has_variants,
        "variant_of": variant_of,
        "website_slug": slug,
    }


TREE = [
    group("All Item Groups", None, web=0, route="all-item-groups"),
    group("Solid Carbide Tools", "All Item Groups", "carbide", 1, "carbide-tools"),
    group("Carbide Drills", "Solid Carbide Tools", "drills", 0, "carbide-tools/solid-carbide-drills"),
    group("GP Drills", "Carbide Drills", None, 0, "carbide-tools/solid-carbide-drills/gp", web=0),
    group(
        "Solid Carbide Jobber Drills",
        "GP Drills",
        "jobber-drills",
        0,
        "carbide-tools/solid-carbide-drills/gp/solid-carbide-jobber-drills",
    ),
]
OLD_TEMPLATE = "carbide-tools/solid-carbide-drills/gp/solid-carbide-jobber-drills/c0gj-gp-jobber-x"


class TestRouteRules(unittest.TestCase):
    def test_slugify_keeps_only_letters_digits_and_single_hyphens(self):
        self.assertEqual(slugify("M2-Round HSS Tool Bits-Metric-4.1-to-8mm"), "m2-round-hss-tool-bits-metric-4-1-to-8mm")
        self.assertEqual(slugify(" Upto-5/32 inch- "), "upto-5-32-inch")

    def test_validate_route(self):
        self.assertEqual(validate_route("carbide/jobber-drills", 75), [])
        self.assertEqual(len(validate_route("a" * 76, 75)), 1)
        for bad in ("contact-us-", "Carbide/drills", "carbide//drills", "a_b", ""):
            self.assertTrue(validate_route(bad, 75), bad)

    def test_cut_slug_keeps_series_and_end_so_templates_stay_apart(self):
        slugs = [cut_slug(slugify(code), 30) for code in STAINLESS]

        self.assertEqual(len(set(slugs)), 4)
        for slug in slugs:
            self.assertLessEqual(len(slug), 30)
            self.assertTrue(slug.startswith("122-"))
            self.assertEqual(validate_route(slug, 30), [])
        self.assertTrue(slugs[0].endswith("less-than-3mm"))

    def test_cut_slug_does_not_change_a_short_slug(self):
        self.assertEqual(cut_slug("m35-hss-flat-end-mills-bsw", 30), "m35-hss-flat-end-mills-bsw")

    def test_group_route_uses_ancestors_with_include_in_url(self):
        chain = TREE[1:]
        self.assertEqual(build_group_route(chain, 2), "carbide/jobber-drills")
        self.assertEqual(build_group_route(chain[:2], 2), "carbide/drills")

    def test_group_route_over_max_depth_fails(self):
        chain = [dict(g, include_in_url=1) for g in TREE[1:]]
        with self.assertRaises(ValueError):
            build_group_route(chain, 2)
        self.assertEqual(build_group_route(chain, 4), "carbide/drills/gp-drills/jobber-drills")

    def test_group_budget_leaves_room_for_template_and_item_code(self):
        self.assertEqual(check_group_budget("carbide/high-performance-drills", 75), [])
        self.assertEqual(len(check_group_budget("carbide/" + "x" * 30, 75)), 1)

    def test_item_routes(self):
        template = build_item_route("carbide/jobber-drills", STAINLESS[0], None, True, None, 75)
        variant = build_item_route("ignored", "CR0AGBE00MD1", None, False, template, 75)
        custom = build_item_route("carbide/jobber-drills", STAINLESS[0], "SS Flat 3mm", True, None, 75)

        self.assertLessEqual(len(variant), 75)
        self.assertEqual(variant, template + "/cr0agbe00md1")
        self.assertEqual(custom, "carbide/jobber-drills/ss-flat-3mm")


class TestRouteRebuild(unittest.TestCase):
    def rows(self, variant_route=None):
        return [
            item("W1", "C0GJ-GP-Jobber-X", "Solid Carbide Jobber Drills", OLD_TEMPLATE),
            item("W2", "CR0AGBE00MD1", "Solid Carbide Jobber Drills", variant_route or OLD_TEMPLATE + "/cr0agbe00md1", "C0GJ-GP-Jobber-X"),
        ]

    def test_rebuild_moves_groups_and_items_with_one_prefix_redirect(self):
        plan = plan_route_rebuild(TREE, self.rows(), 75, 2)

        self.assertEqual(plan.errors, [])
        self.assertEqual(plan.group_routes["Solid Carbide Jobber Drills"], "carbide/jobber-drills")
        self.assertNotIn("GP Drills", plan.group_routes)
        self.assertNotIn("All Item Groups", plan.group_routes)
        self.assertEqual(plan.item_routes["W1"], "carbide/jobber-drills/c0gj-gp-jobber-x")
        self.assertEqual(plan.item_routes["W2"], "carbide/jobber-drills/c0gj-gp-jobber-x/cr0agbe00md1")
        item_redirects = [r for r in plan.redirects if r.old.startswith(OLD_TEMPLATE)]
        self.assertEqual(item_redirects, [Redirect(OLD_TEMPLATE, plan.item_routes["W1"], True)])

    def test_prefix_redirect_sends_variant_to_its_new_route(self):
        redirect = Redirect(OLD_TEMPLATE, "carbide/jobber-drills/c0gj-gp-jobber-x", True)
        pattern = redirect.source.strip("/ ") + "$"
        path = OLD_TEMPLATE + "/cr0agbe00md1"

        self.assertEqual(re.sub(pattern, redirect.target, path), "/carbide/jobber-drills/c0gj-gp-jobber-x/cr0agbe00md1")
        self.assertEqual(re.sub(pattern, redirect.target, OLD_TEMPLATE), "/carbide/jobber-drills/c0gj-gp-jobber-x")
        self.assertIsNone(re.match(pattern, OLD_TEMPLATE + "-2"))

    def test_variant_with_other_old_route_gets_exact_redirects_only(self):
        legacy = OLD_TEMPLATE + "/high-speed-steel-description"
        plan = plan_route_rebuild(TREE, self.rows(legacy), 75, 2)

        item_redirects = {r.old: r for r in plan.redirects if r.old.startswith(OLD_TEMPLATE)}
        self.assertFalse(item_redirects[OLD_TEMPLATE].prefix)
        self.assertEqual(item_redirects[legacy].new, plan.item_routes["W2"])

    def test_second_rebuild_changes_nothing(self):
        plan = plan_route_rebuild(TREE, self.rows(), 75, 2)
        groups = [dict(g, route=plan.group_routes.get(g["name"], g["route"])) for g in TREE]
        items = [dict(w, route=plan.item_routes.get(w["name"], w["route"])) for w in self.rows()]

        again = plan_route_rebuild(groups, items, 75, 2)
        self.assertEqual((again.group_routes, again.item_routes, again.redirects, again.errors), ({}, {}, [], []))

    def test_duplicate_route_is_an_error_and_keeps_the_old_route(self):
        rows = self.rows() + [item("W3", "X", "Solid Carbide Jobber Drills", "old-x", slug="C0GJ GP Jobber X")]
        plan = plan_route_rebuild(TREE, rows, 75, 2)

        self.assertNotIn("W3", plan.item_routes)
        self.assertEqual(len(plan.errors), 1)

    def test_too_long_route_is_an_error_and_keeps_the_old_route(self):
        plan = plan_route_rebuild(TREE, self.rows(), 40, 2)

        self.assertNotIn("Solid Carbide Jobber Drills", plan.group_routes)
        self.assertTrue(plan.errors)

    def test_existing_redirects_point_to_the_new_route(self):
        existing = [
            {"name": "R1", "target": "/" + OLD_TEMPLATE},
            {"name": "R2", "target": "/" + OLD_TEMPLATE + r"\1"},
            {"name": "R3", "target": "/other"},
        ]
        updates = retarget_redirects(existing, {OLD_TEMPLATE: "carbide/x"})

        self.assertEqual(updates, {"R1": "/carbide/x", "R2": "/carbide/x" + r"\1"})

    def test_redirect_that_matches_a_live_route_is_found(self):
        live = ["carbide/jobber-drills", "carbide/jobber-drills/t1"]
        sources = [re.escape("carbide/jobber-drills"), re.escape("old") + "(/.*)?", "("]

        self.assertEqual(hijacking_redirects(sources, live), [re.escape("carbide/jobber-drills")])


class TestLegacyItemTarget(unittest.TestCase):
    TEMPLATE = "carbide/jobber-drills/c0gj-metric"
    VARIANT = TEMPLATE + "/cr0agbe00md1"

    def test_published_variant_goes_to_its_own_page(self):
        published = {"CR0AGBE00MD1": self.VARIANT, "C0GJ-Metric": self.TEMPLATE}

        target = pick_item_target("CR0AGBE00MD1", "C0GJ-Metric", published, "carbide/jobber-drills")

        self.assertEqual(target, self.VARIANT)

    def test_unpublished_variant_goes_to_its_template(self):
        target = pick_item_target(
            "CR0AGBE00MD1", "C0GJ-Metric", {"C0GJ-Metric": self.TEMPLATE}, "carbide/jobber-drills"
        )

        self.assertEqual(target, self.TEMPLATE)

    def test_item_without_a_published_page_goes_to_its_group(self):
        target = pick_item_target("C0GJ-Metric", None, {}, "carbide/jobber-drills")

        self.assertEqual(target, "carbide/jobber-drills")

    def test_item_with_no_live_page_has_no_target(self):
        self.assertIsNone(pick_item_target("C0GJ-Metric", None, {}, None))
