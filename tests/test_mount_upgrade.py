"""THU CUOI (座騎): nang cap + boi duong bang 5 vien ky don. Opcode 79 = 0x4f.

Luat lay TU CLIENT GOC (_lua_dec/Logic/Mounts.lua):
  C:079-003 <座騎升級> [bag_index]              -> S:079-002 [cap]        (xac nhan len cap)
  C:079-004 <座騎投點> [kind][bag_index]        -> S:079-003 [kind][diem] (xac nhan diem moi)
  kind: 1=Atk 2=Int 3=Def 4=ExtraHp 5=ExtraSp
  CHAN: cap chi so KHONG duoc vuot cap thu cuoi (Mounts.AttributeUp) -> phai nang cap truoc.
Payload gui BAG INDEX chu KHONG phai item id.
"""
import unittest
from unittest import mock

from bot import config
from bot.client import GameClient

# Bang rut gon giong that: need 10/20/30, item co dinh theo kind.
ITEM = {1: 0x7d66, 2: 0x7d67, 3: 0x7d68, 4: 0x7d69, 5: 0x7d6a}
LEN_CAP = 0x7d65
GROW = {
    lv: {
        "up_item": LEN_CAP if lv < 3 else 0,
        "up_count": 10 * lv,
        "up_money": 1000,
        "attrs": {k: {"add": lv, "item": ITEM[k], "need": 10 * lv} for k in range(1, 6)},
    }
    for lv in (1, 2, 3)
}


class _State:
    in_battle = False


def khong_ngu():
    """do_mount_upgrade() ngu 0.35s/vien de khong doi goi server; test thi bo di (60 vien = 21s)."""
    return mock.patch("bot.client.time.sleep", lambda *_a: None)


def make_client(level=1, points=None, bag=None, xac_nhan=True):
    """bag = {tid: so luong}. xac_nhan=False -> gia lap server IM (khong tra ack)."""
    c = GameClient.__new__(GameClient)
    c._label = "mt"
    c.running = True
    c.state = _State()
    c.mount_level = level
    c.mount_points = dict(points or {k: 0 for k in range(1, 6)})
    bag = bag or {}
    c.bag_counts = dict(bag)
    c.bag_slots = {i + 1: [tid, n] for i, (tid, n) in enumerate(bag.items())}
    c.sent = []

    def _send(op, payload=b""):
        c.sent.append((op, payload))
        if not xac_nhan:
            return
        if payload[:2] == b"\x03\x00":            # nang cap
            c.mount_level += 1
        elif payload[:2] == b"\x04\x00":          # boi duong: server tra diem MOI (+1)
            k = payload[2]
            c.mount_points[k] = c.mount_points.get(k, 0) + 1
    c.send = _send
    return c


class TestMountAttrLevel(unittest.TestCase):
    """Doi diem -> cap, phai giong Mounts.GetAttributeProgress cua client."""

    def test_tru_dan_need_tung_cap(self):
        with mock.patch.object(config, "MOUNTS_GROW", GROW):
            c = make_client(points={1: 0, 2: 9, 3: 10, 4: 29, 5: 30})
            self.assertEqual(c.mount_attr_level(1), (0, 0))
            self.assertEqual(c.mount_attr_level(2), (0, 9))     # chua du 10
            self.assertEqual(c.mount_attr_level(3), (1, 0))     # dung 10 -> cap 1
            self.assertEqual(c.mount_attr_level(4), (1, 19))    # 29-10=19, chua du 20
            self.assertEqual(c.mount_attr_level(5), (2, 0))     # 30-10-20=0 -> cap 2

    def test_khop_so_lieu_that_trong_KNOWLEDGE(self):
        """Capture that: horse level 3, INT point=34 -> cap 2 (KNOWLEDGE ghi INT+2)."""
        with mock.patch.object(config, "MOUNTS_GROW", config._load_mounts_grow()):
            c = make_client(level=3, points={2: 34})
            self.assertEqual(c.mount_attr_level(2)[0], 2)


class TestMountLevelUp(unittest.TestCase):
    def test_du_vien_thi_len_cap(self):
        with mock.patch.object(config, "MOUNTS_GROW", GROW):
            c = make_client(level=1, bag={LEN_CAP: 10})
            self.assertTrue(c._mount_level_up_once())
            self.assertEqual(c.sent[0][0], 0x4f)
            self.assertEqual(c.sent[0][1][:2], b"\x03\x00")
            self.assertEqual(c.sent[0][1][2], 1, "phai gui BAG INDEX (slot), khong phai item id")

    def test_THIEU_vien_thi_KHONG_gui(self):
        with mock.patch.object(config, "MOUNTS_GROW", GROW):
            c = make_client(level=1, bag={LEN_CAP: 9})   # can 10
            self.assertFalse(c._mount_level_up_once())
            self.assertEqual(c.sent, [])

    def test_server_KHONG_xac_nhan_thi_thoi_ngay(self):
        """Thieu vang / cham tran VIP: bot khong duoc lap vo han."""
        with mock.patch.object(config, "MOUNTS_GROW", GROW):
            c = make_client(level=1, bag={LEN_CAP: 100}, xac_nhan=False)
            c.MOUNT_ACK_WAIT = 0.01
            self.assertFalse(c._mount_level_up_once())
            self.assertEqual(len(c.sent), 1, "gui lai nhieu lan du server im")

    def test_cap_cuoi_bang_thi_dung(self):
        with mock.patch.object(config, "MOUNTS_GROW", GROW):
            c = make_client(level=3, bag={LEN_CAP: 100})   # cap 3 co up_item = 0
            self.assertFalse(c._mount_level_up_once())
            self.assertEqual(c.sent, [])


class TestMountFeed(unittest.TestCase):
    def test_boi_duong_gui_dung_kind_va_bag_index(self):
        with mock.patch.object(config, "MOUNTS_GROW", GROW):
            c = make_client(level=2, bag={ITEM[3]: 5})
            self.assertTrue(c._mount_feed_once(3))
            op, pl = c.sent[0]
            self.assertEqual(op, 0x4f)
            self.assertEqual(pl[:2], b"\x04\x00")
            self.assertEqual(pl[2], 3, "sai kind")
            self.assertEqual(pl[3], 1, "phai gui BAG INDEX")

    def test_CHAN_khi_cap_chi_so_da_bang_cap_thu_cuoi(self):
        """Luat client: attributeLv < mountsLv. Cap thu cuoi 1, chi so da cap 1 -> KHONG duoc."""
        with mock.patch.object(config, "MOUNTS_GROW", GROW):
            c = make_client(level=1, points={1: 10}, bag={ITEM[1]: 99})
            self.assertEqual(c.mount_attr_level(1)[0], 1)
            self.assertFalse(c._mount_feed_once(1))
            self.assertEqual(c.sent, [], "boi duong vuot cap thu cuoi")

    def test_khong_co_vien_trong_tui_thi_thoi(self):
        with mock.patch.object(config, "MOUNTS_GROW", GROW):
            c = make_client(level=3, bag={})
            self.assertFalse(c._mount_feed_once(2))
            self.assertEqual(c.sent, [])


class TestDoMountUpgrade(unittest.TestCase):
    def test_nang_cap_TRUOC_roi_moi_boi_duong(self):
        """Nang cap mo them tran cho chi so -> lam nguoc thu tu se boi duong duoc it hon."""
        with mock.patch.object(config, "MOUNTS_GROW", GROW):
            c = make_client(level=1, bag={LEN_CAP: 100, ITEM[1]: 50})
            with khong_ngu():
                c.do_mount_upgrade()
            lenh = [pl[:2] for _op, pl in c.sent]
            self.assertIn(b"\x03\x00", lenh)
            self.assertIn(b"\x04\x00", lenh)
            self.assertLess(lenh.index(b"\x03\x00"), lenh.index(b"\x04\x00"),
                            "boi duong TRUOC khi nang cap -> mat tran")

    def test_dung_HET_vien_toi_khi_cham_tran(self):
        """Thu cuoi len cap 3 -> chi so duoc phep len TOI cap 3 (= 10+20+30 = 60 vien).

        Luat client kiem `attributeLv >= mountsLv` TRUOC khi gui: o cap 2 voi thu cuoi cap 3 thi
        VAN duoc gui -> chi so cham DUNG cap thu cuoi roi moi dung. (Khong phai dung o cap 2.)"""
        with mock.patch.object(config, "MOUNTS_GROW", GROW):
            c = make_client(level=1, bag={LEN_CAP: 100, ITEM[2]: 999})
            with khong_ngu():
                c.do_mount_upgrade()
            n = sum(1 for _op, pl in c.sent if pl[:2] == b"\x04\x00" and pl[2] == 2)
            self.assertEqual(n, 60)
            self.assertEqual(c.mount_level, 3)
            self.assertEqual(c.mount_attr_level(2)[0], 3, "chi so phai cham dung cap thu cuoi")

    def test_tui_rong_thi_khong_gui_gi(self):
        with mock.patch.object(config, "MOUNTS_GROW", GROW):
            c = make_client(level=2, bag={})
            with khong_ngu():
                c.do_mount_upgrade()
            self.assertEqual(c.sent, [])

    def test_chua_nhan_duoc_goi_mount_thi_bo_qua(self):
        with mock.patch.object(config, "MOUNTS_GROW", GROW):
            c = make_client(level=0, bag={LEN_CAP: 100})
            with khong_ngu():
                c.do_mount_upgrade()
            self.assertEqual(c.sent, [])

    def test_DANG_TRAN_thi_khong_lam_gi(self):
        with mock.patch.object(config, "MOUNTS_GROW", GROW):
            c = make_client(level=1, bag={LEN_CAP: 100})
            c.state.in_battle = True
            with khong_ngu():
                c.do_mount_upgrade()
            self.assertEqual(c.sent, [])


class TestParseGoiMount(unittest.TestCase):
    """Goi HAM THAT trong client.py, KHONG chep lai phep doc vao test: test ma chep lai chinh
    offset can kiem thi luon PASS du offset sai (da dinh dung loi do mot lan trong repo nay)."""

    def _client(self):
        c = GameClient.__new__(GameClient)
        c._label = "mt"
        c.mount_level = 0
        c.mount_points = {}
        c._mount_base_int = 0
        c._refresh_char_int = lambda: None
        c._refresh_char_agi = lambda: None
        return c

    def test_S079_001_doc_dung_cap_va_6_diem(self):
        """So lieu lay tu capture THAT ghi trong KNOWLEDGE: level 3, point [22,34,16,15,22,0]."""
        c = self._client()
        body = bytes([3]) + b"".join(x.to_bytes(2, "little")
                                     for x in (22, 34, 16, 15, 22, 0)) + bytes([0])
        c._on_mount_data(bytes(7) + bytes([0x01, 0x00]) + body)

        self.assertEqual(c.mount_level, 3)
        self.assertEqual(c.mount_points, {1: 22, 2: 34, 3: 16, 4: 15, 5: 22, 6: 0})

    def test_S079_002_cap_nhat_CAP(self):
        c = self._client()
        c.mount_level = 4
        with self.assertLogs("bot", level="INFO"):
            c._on_mount_level(bytes(7) + bytes([0x02, 0x00]) + bytes([5]))
        self.assertEqual(c.mount_level, 5)

    def test_S079_003_cap_nhat_DIEM_theo_gia_tri_TUYET_DOI(self):
        """Server bao so diem MOI (tuyet doi) -> bot khong duoc tu cong don."""
        c = self._client()
        c.mount_points = {3: 5}
        c._on_mount_point(bytes(7) + bytes([0x03, 0x00, 3]) + (41).to_bytes(2, "little"))
        self.assertEqual(c.mount_points[3], 41)




if __name__ == "__main__":
    unittest.main()
