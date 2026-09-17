"""CHI LAP PARTY O THANH TAP KET HOAC MAP TRAIN - thanh di ngang qua thi chua toi luot.

User 13/09: "p4, bon no lap pt o Trac quan lam lon gi the" -> "sua di, thanh tap trung hoac map
train thi moi lap pt, thanh trung gian thi ko pt, nhung nho check can than truong hop thanh tap
trung la Trac quan hay Ng thanh nhe".

Trac Quan (12001) / Nghiep Thanh (12061) la hai thanh ma `pre_route_town_hop` nem acc qua (random
50-50) tren duong ve thanh xuat phat - CHO DI NGANG. Lap party o do la vo ich: buoc ngay sau la
TELEPORT di thanh tap ket, ma teleport bat buoc `leave_party()` -> party vua lap lai tan.

CA THAT (party 4):

    13:32:44 [party 4] dong_bo - cung map nhung LECH KENH [1,4,10,11]   (dang o 12001)
    13:32:47 [party 4] moi - DOI chua du -> CHOT kenh dich = 13
    13:36:01 [party 4] dong_bo - cung map nhung LECH KENH [1,7,10,11]   (van 12001)
    13:36:16 [party 4] LAP LAI PARTY (brubb46677=0 sga008=0 sga009=0 sga011=0 sga012=0)

Roster dung im o 0 suot bon phut.

CHO DE SAI NHAT (user dan truoc): KHONG duoc coi Trac Quan / Nghiep Thanh la "trung gian" theo ID
cung. Chinh chung co the LA thanh tap ket cua party khac - luc do phai lap party o do binh thuong.
Phep so la voi DICH THAT (`_pick_start_city` = thanh gan map train nhat ma ca party deu mo).

DIEU PHOI QUYET: phep nay chay trong `_dieu_phoi_quyet`, chi doi LENH phat ra (GOM thay vi MOI).
Acc khong duoc hoi, khong co co moi nao cho acc doc.
"""
from __future__ import annotations

import io
import os
import sys
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R

from bot import config

TRAC_QUAN = 12001
NGHIEP_THANH = 12061
TRUONG_SA = 23001
MAP_TRAIN = 21852


class _Nen(unittest.TestCase):
    PARTY = 3

    def setUp(self):
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)
        self.st["train_map_dich"] = MAP_TRAIN
        self._pick = R._pick_start_city
        R._pick_start_city = lambda pidx, dest: TRUONG_SA      # dich = Truong Sa

    def tearDown(self):
        R._pick_start_city = self._pick
        R._party_state.pop(self.PARTY, None)


class TestThanhDiNgangQua(_Nen):
    def test_TRAC_QUAN_khi_dich_la_TRUONG_SA(self):
        self.assertTrue(R._o_thanh_di_qua(self.PARTY, self.st, TRAC_QUAN))

    def test_NGHIEP_THANH_khi_dich_la_TRUONG_SA(self):
        self.assertTrue(R._o_thanh_di_qua(self.PARTY, self.st, NGHIEP_THANH))

    def test_dang_o_DUNG_thanh_tap_ket(self):
        self.assertFalse(R._o_thanh_di_qua(self.PARTY, self.st, TRUONG_SA))

    def test_dang_o_MAP_TRAIN(self):
        self.assertFalse(R._o_thanh_di_qua(self.PARTY, self.st, MAP_TRAIN))

    def test_dang_o_map_thuong_khong_phai_thanh(self):
        """Bai train / phy ban -> khong phai thanh, khong chan."""
        self.assertFalse(R._o_thanh_di_qua(self.PARTY, self.st, 62011))


class TestTracQuanCO_THE_LA_DIEM_TAP_KET(_Nen):
    """User dan do dung cho nay: dung hardcode ID."""

    def test_TRAC_QUAN_la_dich_thi_lap_party_binh_thuong(self):
        R._pick_start_city = lambda pidx, dest: TRAC_QUAN
        self.st.pop("thanh_tap_ket_cache", None)
        self.assertFalse(R._o_thanh_di_qua(self.PARTY, self.st, TRAC_QUAN),
                         "Trac Quan la thanh tap ket ma van bi coi la trung gian")

    def test_NGHIEP_THANH_la_dich_thi_lap_party_binh_thuong(self):
        R._pick_start_city = lambda pidx, dest: NGHIEP_THANH
        self.st.pop("thanh_tap_ket_cache", None)
        self.assertFalse(R._o_thanh_di_qua(self.PARTY, self.st, NGHIEP_THANH))

    def test_khong_hardcode_id_trong_ma(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            src = fh.read()
        i = src.find("def _o_thanh_di_qua(")
        j = src.find("\ndef ", i + 10)
        than = src[i:j]
        _ma = than[than.find('"""', than.find('"""') + 3):]
        for _id in ("12001", "12061"):
            self.assertNotIn(_id, _ma, "hardcode thanh trung gian theo ID")


class TestChuaBietThiKHONG_KET_LUAN(_Nen):
    """L13: thieu du lieu -> 'khong biet', khong duoc mac dinh thanh mot ben."""

    def test_chua_co_map_train_dich(self):
        self.st.pop("train_map_dich", None)
        self.st.pop("thanh_tap_ket_cache", None)
        self.assertFalse(R._o_thanh_di_qua(self.PARTY, self.st, TRAC_QUAN))

    def test_khong_chot_duoc_thanh_tap_ket(self):
        R._pick_start_city = lambda pidx, dest: None
        self.st.pop("thanh_tap_ket_cache", None)
        self.assertFalse(R._o_thanh_di_qua(self.PARTY, self.st, TRAC_QUAN))

    def test_router_loi_thi_khong_chan(self):
        def _no(pidx, dest):
            raise RuntimeError("router hong")
        R._pick_start_city = _no
        self.st.pop("thanh_tap_ket_cache", None)
        self.assertFalse(R._o_thanh_di_qua(self.PARTY, self.st, TRAC_QUAN))


class TestCacheKhongGoiRouterMoiNhip(_Nen):
    """Vong dieu phoi chay moi 2 giay cho MOI party; `_pick_start_city` goi router."""

    def test_chi_goi_mot_lan_cho_mot_map_train(self):
        dem = []
        R._pick_start_city = lambda pidx, dest: (dem.append(dest), TRUONG_SA)[1]
        self.st.pop("thanh_tap_ket_cache", None)
        for _ in range(5):
            R._o_thanh_di_qua(self.PARTY, self.st, TRAC_QUAN)
        self.assertEqual(len(dem), 1, "goi router moi nhip")

    def test_doi_map_train_thi_chot_lai(self):
        dem = []
        R._pick_start_city = lambda pidx, dest: (dem.append(dest), TRUONG_SA)[1]
        self.st.pop("thanh_tap_ket_cache", None)
        R._o_thanh_di_qua(self.PARTY, self.st, TRAC_QUAN)
        self.st["train_map_dich"] = 21864
        R._o_thanh_di_qua(self.PARTY, self.st, TRAC_QUAN)
        self.assertEqual(dem, [MAP_TRAIN, 21864])


class TestDieuPhoiRaLenhDung(unittest.TestCase):
    """Chay that `_dieu_phoi_quyet`: dung o thanh trung gian -> GOM, o dich -> MOI."""

    PARTY = 3
    ACCS = ("b1", "b2", "b3")

    class _C:
        def __init__(self, map_id, channel):
            self.current_map = map_id
            self.current_channel = channel
            self.running = True
            self.party_members = []

        def digioi_minutes_live(self):
            return 0.0

        def kenh_dang_chac(self):
            return True

    def setUp(self):
        self._accounts = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", u == "b1", u == "b1") for u in self.ACCS]
        self._clients = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)
        self._pcfg = dict(getattr(config, "PARTY_CONFIG", {}))
        config.PARTY_CONFIG = {self.PARTY: {"mode": "train"}}
        self._pick = R._pick_start_city
        R._pick_start_city = lambda pidx, dest: TRUONG_SA

    def tearDown(self):
        R.party_accounts = self._accounts
        R.account_clients.clear()
        R.account_clients.update(self._clients)
        R._party_state.pop(self.PARTY, None)
        config.PARTY_CONFIG = self._pcfg
        R._pick_start_city = self._pick

    def _quyet(self, map_id):
        for u in self.ACCS:
            R.account_clients[u] = self._C(map_id, 1)
        st = R._pstate(self.PARTY)
        st["train_map_dich"] = MAP_TRAIN
        kh, ly_do, _ = R._dieu_phoi_quyet(self.PARTY, st, R._acc_song(self.PARTY), None)
        return kh, ly_do

    def test_o_TRAC_QUAN_thi_KHONG_moi(self):
        kh, ly_do = self._quyet(TRAC_QUAN)
        self.assertEqual(kh["viec"], R.VIEC_GOM, ly_do)
        self.assertIn("DI NGANG QUA", ly_do)

    def test_o_thanh_tap_ket_thi_MOI(self):
        kh, ly_do = self._quyet(TRUONG_SA)
        self.assertEqual(kh["viec"], R.VIEC_MOI, ly_do)

    def test_o_map_train_thi_MOI(self):
        kh, ly_do = self._quyet(MAP_TRAIN)
        self.assertEqual(kh["viec"], R.VIEC_MOI, ly_do)


class TestDIEU_PHOI_quyet_khong_phai_ACC(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            self.src = fh.read()

    def test_goi_trong_vong_dieu_phoi(self):
        i = self.src.find("def _dieu_phoi_quyet(")
        j = self.src.find("\ndef ", i + 10)
        self.assertIn("_o_thanh_di_qua(pidx, st, _noi)", self.src[i:j],
                      "phep quyet phai nam trong dieu phoi")

    def test_khong_de_ra_co_moi_cho_acc_doc(self):
        """Phep quyet chi duoc goi tu DIEU PHOI (ca hai engine), khong de ra co cho acc doc.

        3 cho: dinh nghia + goi trong `_dieu_phoi_quyet` (engine cu) + callback `hoi_thanh` cho
        ENGINE MOI. Engine moi hoi THANG ham nay thay vi tu viet lai phep thu - chinh la de khong
        co phep thu thu hai cho cung mot cau hoi.
        """
        self.assertEqual(self.src.count("_o_thanh_di_qua("), 3,
                         "chi dinh nghia + dieu phoi cu + callback engine moi")

    def test_engine_moi_HOI_chu_khong_tu_viet_lai(self):
        i = self.src.find("hoi_thanh=")
        self.assertGreater(i, 0, "engine moi khong hoi -> coi moi thanh la diem tap ket")
        self.assertIn("_o_thanh_di_qua(", self.src[i:i + 200])


if __name__ == "__main__":
    unittest.main()
