import os
import tempfile
import unittest

from bot.pathfind import GroundMapStore
from bot.smart_route import SmartRouteCache, SmartWorldRouter
from bot.world_nav import WorldNavStore


class TestSmartWorldRouter(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.nav = WorldNavStore("world_nav.json")
        self.ground = GroundMapStore("gamedata/Ground.mmg")
        self.cache = SmartRouteCache(
            os.path.join(self.temp.name, "smart_routes.json")
        )
        self.router = SmartWorldRouter(self.nav, self.ground, self.cache)

    def test_builds_and_caches_hap_coc_route(self):
        route = self.router.build_route(14821, (1230, 470))
        self.assertEqual(route["city"], 14001)
        self.assertEqual([leg["gate"] for leg in route["legs"]], [1, 17])
        self.assertEqual(
            self.cache.get(14821, (1230, 470), self.nav.fingerprint),
            route,
        )

    def test_changed_fingerprint_invalidates_cache(self):
        route = self.router.build_route(14821, (1230, 470))
        self.assertIsNotNone(route)
        self.assertIsNone(self.cache.get(14821, (1230, 470), "changed"))

    def test_local_leg_path_is_cached_by_start_block(self):
        route = self.router.build_route(14821, (1230, 470))
        path = self.router.get_leg_path(route, 14001, (770, 610))
        self.assertEqual(path[-1], (940, 670))
        again = self.router.get_leg_path(route, 14001, (770, 610))
        self.assertEqual(again, path)

    def test_cache_write_is_atomic_and_reloadable(self):
        route = self.router.build_route(14821, (1230, 470))
        reloaded = SmartRouteCache(self.cache.path)
        self.assertEqual(
            reloaded.get(14821, (1230, 470), self.nav.fingerprint),
            route,
        )
        self.assertFalse(os.path.exists(self.cache.path + ".tmp"))

    def test_route_without_safe_stops_at_final_warp_arrival(self):
        route = self.router.build_route(20801, None)

        self.assertEqual(route["city"], 20001)
        self.assertEqual(
            [leg["target_scene"] for leg in route["legs"]],
            [20000, 20801],
        )
        self.assertIsNone(route["safe"])
        self.assertEqual(route["final_paths"], {})

    def test_nearest_city_can_exclude_destination_city(self):
        picked = self.router.nearest_city(12001, exclude_city=12001)

        self.assertIsNotNone(picked)
        self.assertNotEqual(picked["city"], 12001)
        self.assertEqual(picked["route"]["dest_map"], 12001)

    def test_builds_scene_to_scene_route_from_current_map(self):
        route = self.router.build_scene_route(14001, 14821, start=(750, 590))

        self.assertEqual(route["source_map"], 14001)
        self.assertEqual(route["dest_map"], 14821)
        self.assertEqual([leg["gate"] for leg in route["legs"]], [1, 17])
        self.assertEqual(route["city"], 14001)


if __name__ == "__main__":
    unittest.main()
