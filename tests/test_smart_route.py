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


if __name__ == "__main__":
    unittest.main()
