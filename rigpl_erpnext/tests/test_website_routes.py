import unittest

from rigpl_erpnext.website_rigpl.routes import plan_shared_route_fixes

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
