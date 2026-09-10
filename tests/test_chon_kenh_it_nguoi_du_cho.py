"""CHOT KENH: kenh IT NGUOI NHAT ma DU CHO ca team; khong du cho thi lay kenh DONG MEMBER NHAT.

User chot 07/09: "cai thang dieu phoi phai lam la moi lan gom kenh thi phai xem kenh nao it nguoi
nhat, neu du cho ca team thi sang do, ko du cho trong thi chon kenh dang co nhieu member nhat".

Ban cu bo qua han buoc 1: chi lay "kenh dong member nhat" roi moi phat hien kenh do DAY (server tra
ma 4) -> kenh vao `hong` -> chot lai -> lai day -> ... Log 40NPC (07/09), CUNG mot phan bo ma chot
ba kenh khac nhau trong 12 giay:

    20:24:38 [party 1] party lech kenh {5: 3, 12: 1, 13: 1} -> CHOT kenh dich = 13
    20:24:40 [party 1] party lech kenh {5: 3, 12: 1, 13: 1} -> CHOT kenh dich = 5
    20:24:46 [party 1] party lech kenh {5: 3, 12: 1, 13: 1} -> CHOT kenh dich = 13
    20:24:50 [party 1] party lech kenh {5: 3, 12: 1, 13: 1} -> CHOT kenh dich = 12

Moi lan doi y la ca party quay dau -> khong bao gio gom xong, va leader thi lap lai "chua moi N
member vi chua xac nhan live dung map/kenh".

Va `c.channels` truoc day chi nap MOT LAN trong `pick_best_channel` roi khong ai cap nhat (user:
"sao cai tim kenh it nguoi nhat chi chay 1 lan") - so nguoi/kenh doi lien tuc nen ban cu la chot
vao kenh da day tu bao gio.

Du lieu deu DOC THANG tu client (`c.channels` tu `S:007-001 <分區列表>`) - khong acc nao bao cao.
"""
from __future__ import annotations

import io
import os
import sys
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class _C:
    def __init__(self, ch, channels=None, running=True):
        self.running = running
        self.current_map = 10991
        self.current_channel = ch
        self.channels = dict(channels or {})
        # Moc "vua nhan duoc `S:007-001`". `_bang_kenh` bo qua ban qua cu (`DS_KENH_QUA_CU_SEC`) -
        # ban vai phut truoc thi so cho khong con dung nua.
        self._ds_kenh_nhan_luc = time.time()
        self.party_members = []
        self._chan_switch_result = None
        self._chan_switch_target = None
        self._chan_switch_luc = 0.0
        self.hoi = 0

    def in_combat(self, *_a, **_k):
        return False

    def request_channel_list(self):
        self.hoi += 1


class TestBangKenh(unittest.TestCase):
    def test_hop_tu_moi_client(self):
        song = [("a", _C(1, {2: (5, 20)})), ("b", _C(2, {3: (1, 20)}))]
        b = R._bang_kenh(song)
        self.assertEqual(b[2], (5, 15))
        self.assertEqual(b[3], (1, 19))

    def test_lay_ban_BI_QUAN_NHAT(self):
        """Hai acc giu hai ban chup o hai thoi diem -> lay ban it cho nhat cho chac."""
        song = [("a", _C(1, {2: (5, 20)})), ("b", _C(2, {2: (18, 20)}))]
        self.assertEqual(R._bang_kenh(song)[2], (18, 2))

    def test_du_lieu_hong_khong_lam_no_ham(self):
        song = [("a", _C(1, {2: ("x", None), 3: (1, 20)}))]
        self.assertEqual(R._bang_kenh(song), {3: (1, 19)})


class TestLamMoiDanhSachKenh(unittest.TestCase):
    def setUp(self):
        self.st = {}

    def test_chi_MOT_acc_hoi(self):
        """Hoi tung acc moi nhip = spam `0x07 0100` -> nguy co ma 13."""
        song = [("a", _C(1)), ("b", _C(2)), ("c", _C(3))]
        R._lam_moi_ds_kenh(0, self.st, song)
        self.assertEqual(sum(c.hoi for _u, c in song), 1)

    def test_co_cach_quang(self):
        song = [("a", _C(1))]
        R._lam_moi_ds_kenh(0, self.st, song)
        R._lam_moi_ds_kenh(0, self.st, song)
        self.assertEqual(song[0][1].hoi, 1, "hoi lien tuc -> spam goi")

    def test_qua_han_thi_hoi_lai(self):
        song = [("a", _C(1))]
        R._lam_moi_ds_kenh(0, self.st, song)
        self.st["ds_kenh_luc"] = time.time() - R.DS_KENH_LAM_MOI_SEC - 1
        R._lam_moi_ds_kenh(0, self.st, song)
        self.assertEqual(song[0][1].hoi, 2)

    def test_acc_da_ROT_thi_bo_qua(self):
        a = _C(1, running=False)
        b = _C(2)
        R._lam_moi_ds_kenh(0, self.st, [("a", a), ("b", b)])
        self.assertEqual((a.hoi, b.hoi), (0, 1))


class TestLuatChotKenh(unittest.TestCase):
    PARTY = 4242
    ACCS = ("a", "b", "c")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", False, False) for u in self.ACCS]
        self._cl = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        R.config.PARTY_CONFIG = {self.PARTY: {"mode": "event", "event_key": "40npc"}}

    def tearDown(self):
        R.party_accounts = self._pa
        R.account_clients.clear(); R.account_clients.update(self._cl)
        R._party_state.pop(self.PARTY, None)
        R.config.PARTY_CONFIG = self._pc

    def _song(self, chans, ds):
        for u, ch in zip(self.ACCS, chans):
            R.account_clients[u] = _C(ch, ds)
        return [(u, R.account_clients[u]) for u in self.ACCS]

    def test_kenh_IT_NGUOI_NHAT_duoc_uu_tien_TRUOC(self):
        """User chot 08/09: "phai tim kenh it nguoi nhat truoc chu, ko co kenh nao du cho ca team
        thi moi chon kenh nhieu member nhat".

        Truoc do co mot buoc dung TRUOC buoc nay - "uu tien kenh party dang dung" - do la thu toi
        tu them, khong phai luat user ra. No de ra dung cai no dinh tranh (party 15, 08/09: kenh 3
        giu 4 acc bi bao DAY -> chot kenh 4 noi mot acc le dung, bat 4 nguoi kia di theo)."""
        song = self._song([5, 5, 12], {5: (10, 20), 12: (18, 20), 9: (2, 20)})
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song), 9)

    def test_kenh_it_nguoi_nhung_KHONG_du_cho_thi_bo_qua(self):
        # 9 it nguoi nhat nhung chi con 2 cho, khong chua noi 3 acc -> lay 12 (con 12 cho)
        song = self._song([5, 5, 12], {5: (19, 20), 12: (8, 20), 9: (18, 20)})
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song), 12)

    def test_KHONG_kenh_nao_du_cho_thi_lay_kenh_DONG_MEMBER_NHAT(self):
        # moi kenh chi con 1 cho, khong kenh nao chua noi 3 acc -> lay kenh 5 (2 member)
        song = self._song([5, 5, 12], {5: (19, 20), 12: (19, 20), 9: (19, 20)})
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song), 5)

    def test_kenh_DAY_khong_duoc_chon_du_it_nguoi(self):
        song = self._song([5, 5, 12], {5: (19, 20), 12: (18, 20), 9: (0, 20)})
        R.account_clients["a"]._chan_switch_result = 4
        R.account_clients["a"]._chan_switch_target = 9
        R.account_clients["a"]._chan_switch_luc = time.time()
        self.assertNotEqual(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song), 9)

    def test_chua_biet_danh_sach_kenh_thi_van_chot_duoc(self):
        """Chua nhan duoc `S:007-001` -> khong co du lieu suc chua, phai roi ve luat cu."""
        song = self._song([5, 5, 12], {})
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song), 5)


class TestDangTienTrienThiGiaHan(unittest.TestCase):
    """Chot lai luc gan xong = bat ca party quay dau.

    Log 07/09 party 1: `kenh dich 45 qua 45s van chua gom xong ({6: 1, 45: 4}) -> chot lai` -
    4/5 acc DA sang 45, chi con mot dua, the ma no doi dich."""

    PARTY = 4343
    ACCS = ("a", "b", "c", "d", "e")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", False, False) for u in self.ACCS]
        self._cl = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        R.config.PARTY_CONFIG = {self.PARTY: {"mode": "event", "event_key": "40npc"}}

    def tearDown(self):
        R.party_accounts = self._pa
        R.account_clients.clear(); R.account_clients.update(self._cl)
        R._party_state.pop(self.PARTY, None)
        R.config.PARTY_CONFIG = self._pc

    def _song(self, chans):
        for u, ch in zip(self.ACCS, chans):
            R.account_clients[u] = _C(ch, {})
        return [(u, R.account_clients[u]) for u in self.ACCS]

    def test_da_gom_duoc_da_so_thi_GIU_dich(self):
        song = self._song([45, 45, 45, 45, 6])
        self.st["kenh_dich"] = 45
        self.st["kenh_dich_luc"] = time.time() - R.KENH_DICH_KIEN_NHAN_SEC - 5
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song), 45)

    def test_gia_han_lai_dong_ho(self):
        song = self._song([45, 45, 45, 45, 6])
        self.st["kenh_dich"] = 45
        self.st["kenh_dich_luc"] = time.time() - R.KENH_DICH_KIEN_NHAN_SEC - 5
        R._dieu_phoi_chot_kenh(self.PARTY, self.st, song)
        self.assertGreater(self.st["kenh_dich_luc"], time.time() - 5)

    def test_chua_duoc_da_so_thi_VAN_chot_lai(self):
        """Gia han vo dieu kien = ket vinh vien o mot kenh khong ai toi duoc."""
        song = self._song([6, 6, 6, 6, 45])
        self.st["kenh_dich"] = 45
        self.st["kenh_dich_luc"] = time.time() - R.KENH_DICH_KIEN_NHAN_SEC - 5
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song), 6)


class TestVienDan(unittest.TestCase):
    def test_ghi_ro_luat_trong_code(self):
        s = _src()
        i = s.find("LUAT CHON KENH (user chot 07/09)")
        self.assertGreater(i, 0, "thieu ghi chu luat chon kenh")
        khoi = s[i:i + 1500]
        self.assertIn("IT NGUOI NHAT", khoi)
        self.assertIn("NHIEU MEMBER NHAT", khoi)


if __name__ == "__main__":
    unittest.main()
