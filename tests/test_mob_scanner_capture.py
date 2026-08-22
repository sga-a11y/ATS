import math
import unittest
import warnings

from analyze_pcap import load_frames
from bot.mob_scanner import MobScanSession, compute_centers


class TestBachHaiCaptureRegression(unittest.TestCase):
    def test_map_11013_recovers_two_patrol_centers(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            frames, _flows = load_frames("captures/bachai_route_20260716.pcap")
        players = {
            frame["body"][2:10]
            for frame in frames
            if frame["dir"] == "S2C"
            and frame["op"] == 0x0C
            and len(frame["body"]) >= 40
            and frame["body"][:2] == b"\x00\x00"
        }
        session = MobScanSession(map_id=11013, quiet_seconds=8.0)
        session.begin_station(0.0)
        for entity in players:
            session.mark_player(entity)

        now = 0.0
        # Final route segment starts when rich player info reports map 0x2b05.
        for frame in frames[315:]:
            body = frame["body"]
            if frame["dir"] != "S2C":
                continue
            if frame["op"] == 0x07 and len(body) == 16 and body[:2] == b"\x00\x00":
                map_id = int.from_bytes(body[10:12], "little")
                session.observe_spawn(
                    body[2:10], map_id,
                    int.from_bytes(body[12:14], "little"),
                    int.from_bytes(body[14:16], "little"), now,
                )
                now += 0.1
            elif frame["op"] == 0x06 and len(body) == 15 and body[:2] == b"\x01\x00":
                session.observe_move(
                    body[2:10], 11013,
                    int.from_bytes(body[11:13], "little"),
                    int.from_bytes(body[13:15], "little"), now,
                )
                now += 0.1

        centers = compute_centers(session, None, (410, 1050), now=now + 8.1)

        # DOI CHINH SACH (324228a): bo gom bai theo khoang cach - 1 TRACE (1 con quai) = 1 BAI.
        # Cung capture nay: 5 con -> truoc gom con 2 bai (3 con + 2 con), nay ra du 5 bai.
        # Gia tri hoi quy that su cua test la VI TRI hoc duoc, khong phai so bai -> van kiem day du:
        # 3 con quanh (530, 930) va 2 con quanh (1150, 530).
        points = [center.point for center in centers]
        self.assertEqual(len(centers), 5)
        self.assertEqual([c.monster_count for c in centers], [1] * 5)
        self.assertEqual(sum(1 for p in points if math.dist(p, (530, 930)) <= 180), 3)
        self.assertEqual(sum(1 for p in points if math.dist(p, (1150, 530)) <= 120), 2)


if __name__ == "__main__":
    unittest.main()
