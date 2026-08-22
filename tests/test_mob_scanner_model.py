import unittest

from bot.mob_scanner import MobScanSession, compute_centers, compute_regions


def feed_cycle(session, entity, points, start=0.0):
    now = start
    for point in list(points) + list(points[:2]):
        session.observe_move(entity, session.map_id, point[0], point[1], now)
        now += 1.0
    return now


class ProjectingGround:
    def find_world_path(self, _map_id, _start, _target):
        return [_start, _target]

    def nearest_walkable_world(self, _map_id, point, _reachable_from):
        return point[0] + 10, point[1] + 10


class BlockingGround(ProjectingGround):
    def find_world_path(self, _map_id, start, target):
        if start[0] < 500 < target[0] or target[0] < 500 < start[0]:
            return None
        return [start, target]


class SafeGround(ProjectingGround):
    def __init__(self):
        self.calls = []

    def nearest_walkable_outside(self, map_id, center, hazards,
                                 clearance, max_path):
        self.calls.append((map_id, center, tuple(hazards), clearance, max_path))
        return center[0] + 200, center[1]


class TestMobScanSession(unittest.TestCase):
    def setUp(self):
        self.self_entity = b"self0000"
        self.party_entity = b"party000"
        self.session = MobScanSession(
            map_id=11013,
            self_entity=self.self_entity,
            party_entities={self.party_entity},
            quiet_seconds=8.0,
        )
        self.session.begin_station(0.0)

    def test_self_party_and_other_map_are_ignored(self):
        for entity in (self.self_entity, self.party_entity):
            feed_cycle(self.session, entity, [(100, 100), (200, 100)])
        self.session.observe_move(b"monster1", 99999, 100, 100, 1.0)

        self.assertEqual(self.session.candidate_count(), 0)

    def test_player_mark_removes_movement_seen_first(self):
        entity = b"player00"
        feed_cycle(self.session, entity, [(100, 100), (200, 100)])
        self.assertEqual(self.session.candidate_count(), 1)

        self.session.mark_player(entity)

        self.assertEqual(self.session.candidate_count(), 0)

    def test_repeating_bounded_patrol_stabilizes_after_quiet_window(self):
        feed_cycle(
            self.session,
            b"monster1",
            [(310, 850), (430, 930), (530, 830), (630, 930)],
        )

        # The fourth unique point arrived at t=3.0.
        self.assertFalse(self.session.station_stable(10.9))
        self.assertTrue(self.session.station_stable(11.1))

    def test_one_off_mover_does_not_stabilize_as_monster(self):
        self.session.observe_move(b"unknown1", 11013, 100, 100, 1.0)
        self.session.observe_move(b"unknown1", 11013, 200, 100, 2.0)

        self.assertFalse(self.session.station_stable(30.0))
        self.assertEqual(compute_centers(self.session, None, (30, 30)), [])

    def test_route_over_maximum_diameter_is_rejected(self):
        feed_cycle(self.session, b"runner00", [(100, 100), (1000, 100)])

        self.assertFalse(self.session.station_stable(30.0))
        self.assertEqual(compute_centers(self.session, None, (30, 30)), [])

    def test_empty_station_settles_after_quiet_window(self):
        self.assertFalse(self.session.station_stable(7.9))
        self.assertTrue(self.session.station_stable(8.1))

    def test_probe_can_reduce_bounded_trace_without_full_loop(self):
        entity = b"monster1"
        self.session.observe_move(entity, 11013, 3900, 2400, 0.0)
        self.session.observe_move(entity, 11013, 3990, 2490, 1.0)
        self.session.observe_move(entity, 11013, 4040, 2450, 2.0)

        centers = compute_centers(
            self.session, None, (3990, 2490), now=2.0, stable_only=False
        )

        # Tam bai = TAM BBOX o vuong tuan tra (x 3900..4040 -> 3970, y 2400..2490 -> 2445).
        # Truoc day la _medoid (mot diem CO THAT trong trace) -> doi (3990, 2490). Doi sang bbox
        # o commit 324228a vi medoid lech ve cho quai DUNG LAU chu khong phai giua bai.
        self.assertEqual([center.point for center in centers], [(3970, 2445)])


class TestCenterComputation(unittest.TestCase):
    def _session(self):
        session = MobScanSession(11013, quiet_seconds=8.0)
        session.begin_station(0.0)
        return session

    def test_overlapping_patrols_merge_and_separated_patrol_stays_separate(self):
        session = self._session()
        feed_cycle(session, b"monster1", [(310, 850), (430, 930), (530, 830)])
        feed_cycle(session, b"monster2", [(410, 890), (510, 790), (610, 890)])
        feed_cycle(session, b"monster3", [(1050, 430), (1150, 530), (1250, 430)])

        centers = compute_centers(session, None, (410, 1050), now=30.0)

        # DOI CHINH SACH (324228a): KHONG con gom bai theo khoang cach - 1 TRACE (1 con quai) =
        # 1 BAI. Gom lam map 20801 chi hoc duoc 7/16 bai vi bai quai lat SAT NHAU bi dinh lam mot;
        # bo gom -> 16/16. Nen 3 con o day = 3 bai, moi bai dung 1 con.
        self.assertEqual(len(centers), 3)
        self.assertEqual(sorted(c.monster_count for c in centers), [1, 1, 1])

    def test_wall_prevents_nearby_patrols_from_merging(self):
        session = self._session()
        feed_cycle(session, b"monster1", [(410, 500), (450, 500)])
        feed_cycle(session, b"monster2", [(550, 500), (590, 500)])

        centers = compute_centers(session, BlockingGround(), (410, 500), now=30.0)

        self.assertEqual(len(centers), 2)

    def test_center_is_projected_to_walkable_world_point(self):
        session = self._session()
        feed_cycle(session, b"monster1", [(310, 850), (430, 930), (530, 830)])

        center = compute_centers(session, ProjectingGround(), (410, 1050), now=30.0)[0]

        # tam bbox (420, 880) roi ProjectingGround day sang o di duoc (+10, +10)
        self.assertEqual(center.point, (430, 890))
        self.assertEqual(center.monster_count, 1)

    def test_regions_pair_each_center_with_safe_outside_all_traces(self):
        session = self._session()
        feed_cycle(session, b"monster1", [(310, 850), (430, 930), (530, 830)])
        feed_cycle(session, b"monster2", [(1050, 430), (1150, 530), (1250, 430)])
        ground = SafeGround()

        regions = compute_regions(session, ground, (410, 1050), now=30.0)

        self.assertEqual(len(regions), 2)
        self.assertTrue(all(
            region.safe[0] == region.center.point[0] + 200
            for region in regions
        ))
        self.assertTrue(all(len(call[2]) == 6 for call in ground.calls))

    def test_region_uses_fallback_safe_when_search_fails(self):
        session = self._session()
        feed_cycle(session, b"monster1", [(310, 850), (430, 930), (530, 830)])
        ground = SafeGround()
        ground.nearest_walkable_outside = lambda *_args, **_kwargs: None

        regions = compute_regions(
            session, ground, (410, 1050), fallback_safe=(100, 200), now=30.0
        )

        self.assertEqual(regions[0].safe, (100, 200))


if __name__ == "__main__":
    unittest.main()
