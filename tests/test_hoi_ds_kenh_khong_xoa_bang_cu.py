"""Hoi lai danh sach kenh KHONG duoc xoa bang cu -> nhanh "kenh it nguoi nhat" moi chay duoc.

User 10/09: "hinh nhu no van ko tim kenh it nguoi truoc ma no chot kenh member dang o luon, m xem
log di".

Dung. Doc party.log: MOI lan chot deu la nhanh (b):
    02:26:19 [party 45] party lech kenh {1: 2, 3: 1, 4: 2} -> CHOT kenh dich = 4
                        (khong kenh nao du cho ca team -> lay kenh dang NHIEU MEMBER NHAT)
Nhanh (a) "kenh IT NGUOI NHAT ma du cho ca team" KHONG chay lan nao.

Dong log chan doan them hom truoc noi ro vi sao:
    02:26:28 [party 45] khong kenh nao du 5 cho - bang 0 kenh, so den 0 kenh, kenh rong nhat con ?

Dem tren ca file:
    6105 lan  `bang 0 kenh`
     277 lan  `bang 58 kenh`
      96 lan  `bang 56 kenh`
-> 94% so lan chot kenh, dieu phoi KHONG CO du lieu kenh nao. Khong co bang thi nhanh (a) khong co
ung vien de xet, nen LUON roi xuong nhanh (b). Khong phai luat chon sai - la du lieu khong co.

NGUYEN NHAN: `request_channel_list()` dat `self.channels = {}` NGAY khi gui `0x07 0100`, roi goi
`S:007-001` mat vai giay moi ve (co khi khong ve). `pick_best_channel` con goi ham do toi 4 lan
lien tiep. Bang cu vai chuc giay van chon duoc kenh; bang RONG thi khong lam duoc gi.
"""
from __future__ import annotations

import io
import os
import re
import sys
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class TestKhongXoaBangKhiHoi(unittest.TestCase):
    def setUp(self):
        self.cli = _doc("bot", "client.py")
        i = self.cli.find("def request_channel_list(self):")
        self.assertGreater(i, 0)
        than = self.cli[i:self.cli.find("\n    def ", i + 10)]
        than = re.sub(r'"""[\s\S]*?"""', "", than)     # bo docstring
        self.than = re.sub(r"#.*", "", than)

    def test_KHONG_xoa_channels(self):
        self.assertNotIn("self.channels = {}", self.than,
                         "xoa bang cu roi cho goi ve = tu tao cua so mu, 94% nhip chot bang RONG")

    def test_VAN_ghi_moc_hoi_va_clear_event(self):
        """Hai thu nay la cach `pick_best_channel` va dieu phoi biet 'dang cho goi ve'."""
        self.assertIn("self._chan_event.clear()", self.than)
        self.assertIn("self._ds_kenh_hoi_luc = time.time()", self.than)

    def test_van_gui_goi_hoi(self):
        self.assertIn('self.send(0x07, b"\\x01\\x00")', self.than)


class TestBangCuVanDungDuocNhungCoHAN(unittest.TestCase):
    class _C:
        def __init__(self, channels, tuoi=0.0, ch=1):
            self.running = True
            self.current_map = 100
            self.current_channel = ch
            self.channels = dict(channels)
            self._ds_kenh_nhan_luc = time.time() - tuoi

    def test_ban_moi_thi_dung(self):
        c = self._C({5: (10, 50), 7: (48, 50)})
        self.assertEqual(R._bang_kenh([("u", c)]), {5: (10, 40), 7: (48, 2)})

    def test_ban_QUA_CU_thi_bo(self):
        """Nguoi ra vao lien tuc - so cho cua ban vai phut truoc la vo nghia."""
        c = self._C({5: (10, 50)}, tuoi=R.DS_KENH_QUA_CU_SEC + 1)
        self.assertEqual(R._bang_kenh([("u", c)]), {})

    def test_ban_cu_VUA_PHAI_van_dung(self):
        """"Cu" khac han "rong": bang vai chuc giay van chon duoc kenh."""
        c = self._C({5: (10, 50)}, tuoi=R.DS_KENH_QUA_CU_SEC / 2.0)
        self.assertEqual(R._bang_kenh([("u", c)]), {5: (10, 40)})

    def test_han_cu_rong_rai_hon_nhip_hoi_lai(self):
        """Chat hon nhip hoi lai thi luon co luc khong con ban nao dung duoc."""
        self.assertGreater(R.DS_KENH_QUA_CU_SEC, R.DS_KENH_LAM_MOI_SEC * 2)

    def test_gop_nhieu_acc_lay_ban_BI_QUAN_NHAT(self):
        a = self._C({5: (10, 50)})
        b = self._C({5: (40, 50)})
        self.assertEqual(R._bang_kenh([("a", a), ("b", b)]), {5: (40, 10)})

    def test_acc_chua_tung_nhan_thi_khong_tinh(self):
        c = self._C({}, tuoi=0.0)
        c._ds_kenh_nhan_luc = 0.0
        self.assertEqual(R._bang_kenh([("u", c)]), {})


class TestNhanhItNguoiNhatChayDuocKhiCoBang(unittest.TestCase):
    """Co bang thi luat cua user phai chay: "tim kenh it nguoi nhat truoc"."""

    PARTY = 0
    ACCS = ("a1", "a2", "a3")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", u == "a1", u == "a1") for u in self.ACCS]
        self._cl = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)
        from bot import config
        self._pcfg = dict(getattr(config, "PARTY_CONFIG", {}))
        config.PARTY_CONFIG = {self.PARTY: {"mode": "train"}}
        self._cfg = config

    def tearDown(self):
        R.party_accounts = self._pa
        R.account_clients.clear(); R.account_clients.update(self._cl)
        R._party_state.pop(self.PARTY, None)
        self._cfg.PARTY_CONFIG = self._pcfg

    def _dat(self, **kw):
        for u, c in kw.items():
            R.account_clients[u] = c
        return [(u, R.account_clients[u]) for u in self.ACCS if u in R.account_clients]

    def test_chon_kenh_IT_NGUOI_NHAT_du_cho_chu_khong_theo_member(self):
        ds = {2: (49, 50), 9: (48, 50), 30: (3, 50)}    # 30 rong nhat
        song = self._dat(a1=self._C(2, ds), a2=self._C(9, ds), a3=self._C(9, ds))
        self._jmc = R.joined_member_count
        R.joined_member_count = lambda pidx: 0
        self.addCleanup(lambda: setattr(R, "joined_member_count", self._jmc))
        st = R._pstate(self.PARTY)
        dich = R._dieu_phoi_chot_kenh(self.PARTY, st, song)
        self.assertEqual(dich, 30, "co bang ma van chot theo kenh dong member = sai luat user")

    class _C:
        def __init__(self, ch, channels):
            self.running = True
            self.current_map = 100
            self.current_channel = ch
            self.channels = dict(channels)
            self._ds_kenh_nhan_luc = time.time()
            self._ds_kenh_hoi_luc = 0.0
            # Doi RONG = dang gom, dung luc dieu phoi phai chot kenh (du doi thi no giu nguyen).
            self.party_members = []
            self._chan_switch_result = None
            self._chan_switch_target = None
            self._chan_switch_luc = 0.0

        def in_combat(self, *_a, **_k):
            return False

        def request_channel_list(self):
            pass

        def digioi_minutes_live(self):
            return 0.0


if __name__ == "__main__":
    unittest.main()
