import json
import os
import tempfile
import unittest

from src.assets.python.layout.ars import build_ars_lookup, load_ars_routes, save_ars_routes


class ArsRouteTests(unittest.TestCase):
    def test_build_ars_lookup_maps_signal_to_next_signal(self):
        routes = [
            {"name": "route-1", "signals": [(1, 2), (3, 2), (5, 2)]},
            {"name": "route-2", "signals": [(8, 3), (9, 3)]},
        ]

        lookup = build_ars_lookup(routes)

        self.assertEqual(lookup[(1, 2)], [(3, 2)])
        self.assertEqual(lookup[(3, 2)], [(5, 2)])
        self.assertEqual(lookup[(8, 3)], [(9, 3)])
        self.assertIsNone(lookup.get((99, 99)))

    def test_load_and_save_ars_routes_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "demo_ars_routes.json")
            routes = [
                {"name": "stage-1", "signals": [(1, 2), (3, 2)]},
                {"name": "stage-2", "signals": [(4, 5), (6, 5), (7, 5)]},
            ]

            save_ars_routes(path, routes)
            loaded = load_ars_routes(path)

            self.assertEqual(loaded, routes)
            expected_json = {
                "routes": [
                    {"name": "stage-1", "signals": [[1, 2], [3, 2]]},
                    {"name": "stage-2", "signals": [[4, 5], [6, 5], [7, 5]]},
                ]
            }
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), expected_json)


if __name__ == "__main__":
    unittest.main()
