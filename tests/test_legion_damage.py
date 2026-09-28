import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bot import legion_damage as ld

ROOT = Path(__file__).resolve().parents[1]
# 2026-09-28 (thu Hai) 13:00 gio VN
MON = 1790564400 - 7 * 3600 + 10 * 3600


def _org_body(members, org="QD"):
    """Dung goi S:039-002 dung cau truc client (Organization.SetData)."""
    def s(x):
        b = x.encode("utf-16-le")
        return bytes([len(b)]) + b
    b = b"\x02\x00" + s(org) + bytes([0, len(members) - 1])
    for rid, nm, dmg in members:
        b += bytes.fromhex(rid) + s(nm) + b"\x00" * 15 + b"\x01" + b"\x00" * 13 + struct.pack("<I", dmg)
    b += s("") + b"\x00" * 26 + b"\x00\x00" + b"\x00\x00\x00\x00" + s("")
    return b


def _boss_body(rid, total):
    return b"\x74\x00" + bytes.fromhex(rid) + struct.pack("<I", total)


A = "0100000000000000"
B = "0200000000000000"


class TuanTest(unittest.TestCase):
    def test_moc_tuan_la_0h_thu_hai_gio_vn(self):
        self.assertEqual(ld.week_key(MON), "2026-09-28")
        mon0 = ld.week_start(MON)
        self.assertEqual(ld.week_key(mon0), "2026-09-28")
        self.assertEqual(ld.week_key(mon0 - 1), "2026-09-21")   # CN 23:59:59
        self.assertEqual(ld.week_key(mon0 + 7 * 86400 - 1), "2026-09-28")


class ParseCaptureTest(unittest.TestCase):
    def test_parse_039_002_capture_that_doc_het_goi(self):
        cap = ROOT / "login_cap.pcap"
        if not cap.exists():
            self.skipTest("thieu capture")
        from analyze_pcap import load_frames
        frames, _ = load_frames(str(cap))
        body = next(f["body"] for f in frames
                    if f["dir"] == "S2C" and f["op"] == 0x27 and f["body"][:1] == b"\x02")
        name, ms, count = ld.parse_org_data(body)
        self.assertEqual(count, 0)
        self.assertEqual(len(ms), 28)
        # tong dame member = BOSS傷害量 cua QD trong cung goi
        self.assertEqual(sum(m[2] for m in ms), struct.unpack_from("<I", body, len(body) - 5)[0])

    def test_parse_039_116(self):
        self.assertEqual(ld.parse_member_boss(_boss_body(A, 1234)), (A, 1234))


class GhiNhanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        p = os.path.join(self.tmp, "legion_damage.json")
        self.patch = mock.patch.object(ld, "_path", return_value=p)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def _m(self, rid, now=MON):
        return next(m for m in ld.info("u1", now=now)["weeks"][0]["members"] if m["rid"] == rid)

    def test_online_dem_so_lan_login_chi_cong_dame(self):
        ld.on_org_data("u1", 896, _org_body([(A, "Abc", 0), (B, "Xyz", 0)]), now=MON)
        ld.on_member_boss("u1", 896, _boss_body(A, 100), now=MON + 10)
        ld.on_member_boss("u1", 896, _boss_body(A, 250), now=MON + 20)
        # acc off, A danh them -> login thay tong 400: +150 offline, KHONG tang so lan
        ld.on_org_data("u2", 896, _org_body([(A, "Abc", 400), (B, "Xyz", 0)]), now=MON + 30)
        m = self._m(A)
        self.assertEqual((m["total"], m["hits"]), (400, 2))
        self.assertEqual([(x["dmg"], x["off"]) for x in m["log"]], [(100, 0), (150, 0), (150, 1)])

    def test_nhieu_acc_cung_goi_khong_dem_doi(self):
        ld.on_member_boss("u1", 896, _boss_body(A, 100), now=MON)
        self.assertIsNone(ld.on_member_boss("u2", 896, _boss_body(A, 100), now=MON + 1))
        ld.on_org_data("u3", 896, _org_body([(A, "Abc", 100)]), now=MON + 2)
        self.assertEqual(self._m(A)["hits"], 1)
        self.assertEqual(len(self._m(A)["log"]), 1)

    def test_tong_giam_la_reset_khong_delta_am(self):
        ld.on_member_boss("u1", 896, _boss_body(A, 500), now=MON)
        ld.on_member_boss("u1", 896, _boss_body(A, 30), now=MON + 5)
        m = self._m(A)
        self.assertEqual((m["total"], m["hits"]), (30, 1))
        self.assertEqual(m["log"][-1].get("reset"), 1)

    def test_sang_tuan_moi_bat_dau_lai_giu_2_tuan(self):
        ld.on_org_data("u1", 896, _org_body([(A, "Abc", 0)]), now=MON - 14 * 86400)
        ld.on_member_boss("u1", 896, _boss_body(A, 900), now=MON - 7 * 86400)
        ld.on_member_boss("u1", 896, _boss_body(A, 50), now=MON)   # server reset 0h T2
        inf = ld.info("u1", now=MON)
        self.assertEqual([w["week"] for w in inf["weeks"]], ["2026-09-28", "2026-09-21"])
        now_w, prev_w = inf["weeks"]
        self.assertEqual((now_w["members"][0]["total"], now_w["members"][0]["hits"]), (50, 1))
        self.assertEqual(now_w["members"][0]["name"], "Abc")
        self.assertEqual(prev_w["members"][0]["total"], 900)
        self.assertEqual(len(ld.load()["orgs"]["896"]["weeks"]), 2)

    def test_cap_boss_va_ha_boss(self):
        ld.on_org_data("u1", 896, _org_body([(A, "Abc", 0), (B, "Xyz", 0)]), now=MON)
        ld.on_boss_info("u1", 896, b"\x73\x00" + struct.pack("<HI", 2, 0), now=MON + 1)
        ld.on_member_boss("u1", 896, _boss_body(A, 100), now=MON + 10)   # danh Lv3
        ld.on_boss_info("u1", 896, b"\x73\x00" + struct.pack("<HI", 2, 100), now=MON + 10)
        ld.on_member_boss("u1", 896, _boss_body(B, 400), now=MON + 20)   # ha Lv3
        self.assertEqual(ld.on_boss_info("u1", 896, b"\x73\x00" + struct.pack("<HI", 3, 0),
                                         now=MON + 20)[0], 3)
        # acc thu 2 nhan cung goi 115 -> khong danh dau lai
        self.assertIsNone(ld.on_boss_info("u2", 896, b"\x73\x00" + struct.pack("<HI", 3, 0),
                                          now=MON + 21))
        ld.on_member_boss("u1", 896, _boss_body(A, 150), now=MON + 30)   # danh Lv4
        a, b = self._m(A)["log"], self._m(B)["log"]
        self.assertEqual([(e.get("lv"), e.get("kill")) for e in a], [(3, None), (4, None)])
        self.assertEqual([(e.get("lv"), e.get("kill")) for e in b], [(3, 1)])

    def test_cap_boss_quay_vong_lv7_ve_lv1(self):
        self.assertEqual([ld.boss_level(c) for c in (0, 6, 7, 13, 14)], [1, 7, 1, 7, 1])
        ld.on_org_data("u1", 896, _org_body([(A, "Abc", 0)]), now=MON)
        ld.on_boss_info("u1", 896, b"\x73\x00" + struct.pack("<HI", 6, 0), now=MON + 1)
        ld.on_member_boss("u1", 896, _boss_body(A, 100), now=MON + 10)   # danh Lv7
        # ha Lv7 -> server dua bossCount ve 0 (6 -> 0 van la HA boss)
        r = ld.on_boss_info("u1", 896, b"\x73\x00" + struct.pack("<HI", 0, 0), now=MON + 10)
        self.assertEqual(r[0], 7)
        ld.on_member_boss("u1", 896, _boss_body(A, 150), now=MON + 20)   # quay ve Lv1
        self.assertEqual([(e.get("lv"), e.get("kill")) for e in self._m(A)["log"]],
                         [(7, 1), (1, None)])

    def test_nap_bu_bang_cu_khi_tick_giua_chung(self):
        # tick SAU login: da nhan 116 (khong ten) roi moi nap bang QD cu (tong nho hon)
        ld.on_member_boss("u1", 896, _boss_body(A, 900), now=MON)
        ld.on_org_data("u1", 896, _org_body([(A, "Abc", 300), (B, "Xyz", 50)], org="QDX"),
                       now=MON + 1, stale=True)
        a = self._m(A)
        self.assertEqual((a["name"], a["total"], a["hits"]), ("Abc", 900, 1))
        self.assertFalse(any(e.get("reset") for e in a["log"]))
        self.assertEqual(ld.info("u1", now=MON)["name"], "QDX")

    def test_dame_offline_khong_co_cap(self):
        ld.on_org_data("u1", 896, _org_body([(A, "Abc", 500)]), now=MON)
        self.assertNotIn("lv", self._m(A)["log"][0])

    def test_xem_offline_theo_acc_da_ghi(self):
        ld.on_member_boss("u1", 896, _boss_body(A, 100), now=MON)
        self.assertEqual(ld.info("u1", now=MON)["org_id"], "896")
        self.assertEqual(ld.info("khac", now=MON)["weeks"], [])


if __name__ == "__main__":
    unittest.main()
