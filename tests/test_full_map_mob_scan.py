import os
import tempfile
import unittest
from unittest import mock

from bot import config, mob_spots
from bot.mob_scanner import scan_full_map


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += float(seconds)

    def tick(self, seconds=0.05):
        self.value += float(seconds)
        return self.value


class FakeGround:
    def __init__(self, stations=((100, 100), (500, 500))):
        self.stations = list(stations)

    def map_fingerprint(self, _map_id):
        return "abc12345"

    def coverage_stations(self, _map_id, _start, _stride):
        return list(self.stations)

    def find_world_path(self, _map_id, start, target):
        return [start, target]

    def nearest_walkable_world(self, _map_id, point, _start):
        return point


class FakeClient:
    def __init__(self, clock, ground, mode="stable"):
        self.clock = clock
        self.ground = ground
        self.mode = mode
        self.pos = (30, 30)
        self.current_map = 11013
        self.self_entity = b"self0000"
        self.running = True
        self.navigate_calls = []
        self.active_session = None
        self.visits = {}

    def get_ground_store(self):
        return self.ground

    def begin_mob_observation(self, session):
        self.active_session = session

    def end_mob_observation(self, session):
        if self.active_session is session:
            self.active_session = None

    def navigate_to(self, x, y, **_kwargs):
        point = (x, y)
        self.navigate_calls.append(point)
        self.pos = point
        visit = self.visits.get(point, 0) + 1
        self.visits[point] = visit
        entity = (f"m{x:04d}{y:02d}").encode()[:8].ljust(8, b"0")
        base = [(x, y), (x + 40, y), (x + 40, y + 40)]
        points = base + base[:2]
        if self.mode == "second_pass" and visit == 1:
            points = base[:2]
        for px, py in points:
            self.active_session.observe_move(
                entity, self.current_map, px, py, self.clock.tick()
            )
        if self.mode == "disconnect":
            self.running = False


class TestFullMapMobScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_path = os.path.join(self.tmp.name, "mob_spots.json")
        self.path_patch = mock.patch.object(mob_spots, "_path", return_value=self.cache_path)
        self.path_patch.start()
        self.config_patch = mock.patch.multiple(
            config,
            MOB_SCAN_STATION_STRIDE=(320, 240),
            MOB_SCAN_QUIET_SECONDS=0.2,
            MOB_SCAN_STATION_TIMEOUT=0.6,
            MOB_SCAN_MIN_SAMPLES=3,
            MOB_SCAN_MAX_PATROL_DIAMETER=800,
            MOB_SCAN_MERGE_DISTANCE=200,
            MOB_SCAN_SECOND_PASS=True,
            create=True,
        )
        self.config_patch.start()

    def tearDown(self):
        self.config_patch.stop()
        self.path_patch.stop()
        self.tmp.cleanup()

    def test_cache_hit_skips_navigation(self):
        mob_spots.save_complete(11013, "abc12345", [(530, 930)], {}, {})
        clock = FakeClock()
        client = FakeClient(clock, FakeGround())

        result = scan_full_map(client, 11013, clock=clock, sleep=clock.sleep)

        self.assertEqual(result.status, "cached")
        self.assertEqual([c.point for c in result.centers], [(530, 930)])
        self.assertEqual(client.navigate_calls, [])

    def test_first_pass_visits_every_station_and_saves_only_centers(self):
        clock = FakeClock()
        client = FakeClient(clock, FakeGround())

        result = scan_full_map(client, 11013, clock=clock, sleep=clock.sleep)

        self.assertEqual(result.status, "complete")
        self.assertEqual(client.navigate_calls, [(100, 100), (500, 500)])
        self.assertEqual(result.visited, 2)
        self.assertEqual(len(mob_spots.load_complete_centers(11013, "abc12345")), 2)
        self.assertIsNone(client.active_session)

    def test_low_confidence_station_gets_one_second_pass(self):
        clock = FakeClock()
        client = FakeClient(clock, FakeGround(stations=((100, 100),)), "second_pass")

        result = scan_full_map(client, 11013, clock=clock, sleep=clock.sleep)

        self.assertEqual(result.status, "complete")
        self.assertEqual(client.navigate_calls, [(100, 100), (100, 100)])

    def test_disconnect_saves_incomplete_progress(self):
        clock = FakeClock()
        client = FakeClient(clock, FakeGround(), "disconnect")

        result = scan_full_map(client, 11013, clock=clock, sleep=clock.sleep)

        self.assertEqual(result.status, "incomplete")
        self.assertIsNone(mob_spots.load_complete_centers(11013, "abc12345"))
        self.assertTrue(mob_spots.load_progress(11013, "abc12345"))
        self.assertIsNone(client.active_session)

    def test_missing_ground_is_unavailable(self):
        clock = FakeClock()
        client = FakeClient(clock, None)

        result = scan_full_map(client, 11013, clock=clock, sleep=clock.sleep)

        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.centers, ())
        self.assertEqual(client.navigate_calls, [])


if __name__ == "__main__":
    unittest.main()
