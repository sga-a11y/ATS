"""KENH DICH la TRANG THAI do DIEU PHOI chot - khong phai cai bat tay tung vong.

BUG THAT 06/09 (party 53) - party vo lam hai kenh du VUA MOI dong bo xong:
    02:09:00 [vumhai] Kenh it nguoi MA DU CHO ca party (5): kenh 4 (2/20) -> chuyen sang
    02:09:01 [vumhai] sync kenh/map OK: 5/5 acc o map 12001      <- CA 5 DA O KENH 4
    02:09:08 -> LENH THU CONG ('route', 12001, 12061)
    02:09:11 [vumba]  doc dich = kenh 4 -> xong -> ROI vong dong bo
    02:09:12 [vumhai] Kenh it nguoi MA DU CHO ca party (5): kenh 2 (5/20) -> chuyen sang
    02:09:22 sync kenh: 3/5 da sang kenh 2, CHUA sang: {qv813: 4, qv816: 4}

Hai lo hong khac cap:
  1. MOI LUA: picker doi kenh du party DANG ON. Kenh 4 trong co "dong" chinh vi party minh dang
     dung trong do -> picker thay kenh 2 "vang hon" roi doi ca party sang.
  2. CO CHE: kenh dich la cai bat tay tung vong. Acc lam xong thi `break` roi di - doi dich sau
     do la no khong bao gio biet. `channel_sync_gen` chi bao ve acc DANG DUNG TRONG vong cho.
"""
from __future__ import annotations

import io
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class _C:
    def __init__(self, map_id=12001, channel=1):
        self.running = True
        self.current_map = map_id
        self.current_channel = channel
        self._chan_switch_result = None
        self._chan_switch_target = None
        self._chan_switch_luc = 0.0

    def ma_doi_kenh(self, ma, nham):
        """Gia lap: client nay vua doi kenh `nham` va nhan ma `ma` tu server."""
        import time as _t
        self._chan_switch_result = ma
        self._chan_switch_target = nham
        self._chan_switch_luc = _t.time()


class TestDangONThiDungDungVao(unittest.TestCase):
    """Lo hong 1: picker doi kenh du party dang chung kenh."""

    def setUp(self):
        self.src = _doc("bot", "client.py")
        i = self.src.find("def pick_best_channel(")
        self.than = self.src[i:self.src.find("\n    def ", i + 10)]

    def test_kiem_TRUOC_khi_hoi_danh_sach_kenh(self):
        i = self.than.find("_kenh_chung_cua_party()")
        self.assertGreater(i, 0, "picker khong he kiem 'party da cung kenh chua'")
        self.assertLess(i, self.than.find("self.request_channel_list()"),
                        "kiem SAU khi hoi list -> van mo vong dong bo moi vo ich")

    def test_cung_kenh_thi_tra_0_giu_nguyen(self):
        i = self.than.find("_kenh_chung_cua_party()")
        self.assertIn("return 0", self.than[i:i + 400])

    def test_chi_tinh_acc_CUNG_MAP(self):
        """So kenh chi co nghia trong cung mot map."""
        i = self.src.find("def kenh_cua_party(")
        than = self.src[i:self.src.find("\n    def ", i + 10)]
        self.assertIn('getattr(p, "current_map", None) != self.current_map', than)
        self.assertIn('getattr(p, "running", False)', than)

    def test_can_it_nhat_2_acc_moi_tinh_la_CUNG_kenh(self):
        """Mot minh minh thi khong the goi la 'ca party da cung kenh'."""
        i = self.src.find("def _kenh_chung_cua_party(")
        than = self.src[i:self.src.find("\n    def ", i + 10)]
        self.assertIn("n >= 2", than)


class TestKenhDichLaTRANG_THAI(unittest.TestCase):
    PARTY = 0
    ACCS = ("a1", "a2", "a3")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", False, False) for u in self.ACCS]
        self._cl = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)

    def tearDown(self):
        R.party_accounts = self._pa
        R.account_clients.clear(); R.account_clients.update(self._cl)
        R._party_state.pop(self.PARTY, None)

    def _song(self, **kw):
        for u, c in kw.items():
            R.account_clients[u] = c
        return [(u, R.account_clients[u]) for u in self.ACCS if u in R.account_clients]

    def test_chot_kenh_DONG_NGUOI_NHAT(self):
        """It phai di chuyen nhat. Party 53: 2 dua o kenh 4, 3 dua o kenh 2 -> chot 2."""
        st = R._pstate(self.PARTY)
        song = self._song(a1=_C(channel=4), a2=_C(channel=2), a3=_C(channel=2))
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, st, song), 2)
        self.assertEqual(st["kenh_dich"], 2)

    def test_dang_chung_kenh_thi_KHONG_chot_gi(self):
        st = R._pstate(self.PARTY)
        song = self._song(a1=_C(channel=4), a2=_C(channel=4), a3=_C(channel=4))
        self.assertIsNone(R._dieu_phoi_chot_kenh(self.PARTY, st, song))
        self.assertIsNone(st["kenh_dich"])

    def test_khac_map_thi_KHONG_quyet(self):
        """So kenh o hai map khac nhau la vo nghia."""
        st = R._pstate(self.PARTY)
        song = self._song(a1=_C(map_id=12001, channel=4), a2=_C(map_id=49942, channel=2),
                          a3=_C(map_id=49942, channel=2))
        self.assertIsNone(R._dieu_phoi_chot_kenh(self.PARTY, st, song))

    def test_chua_ro_kenh_thi_KHONG_quyet(self):
        st = R._pstate(self.PARTY)
        song = self._song(a1=_C(channel=None), a2=_C(channel=2), a3=_C(channel=2))
        self.assertIsNone(R._dieu_phoi_chot_kenh(self.PARTY, st, song))

    def test_KHONG_nhuong_vong_bat_tay(self):
        """Dieu phoi la nguoi quyet - vong sync cu chi la canh tay thi hanh, khong duoc chan."""
        st = R._pstate(self.PARTY)
        st["channel_ready"].set()
        song = self._song(a1=_C(channel=4), a2=_C(channel=2), a3=_C(channel=2))
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, st, song), 2)

    def test_kenh_bao_DAY_thi_KHONG_chot_lai(self):
        """P3 06/09: kenh 15 day, batbat vao khong duoc -> chot lai 15 la bat no dam dau mai.
        Dieu phoi DOC THANG `_chan_switch_result` cua client, khong cho acc bao cao."""
        st = R._pstate(self.PARTY)
        song = self._song(a1=_C(channel=4), a2=_C(channel=2), a3=_C(channel=2))
        R.account_clients["a1"].ma_doi_kenh(4, 2)     # a1 vua vao kenh 2 khong duoc: DAY
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, st, song), 4,
                         "kenh dong nhat da DAY -> phai lay kenh dong nhi")

    def test_moi_kenh_deu_day_thi_tim_kenh_MOI_du_cho_ca_party(self):
        st = R._pstate(self.PARTY)
        song = self._song(a1=_C(channel=4), a2=_C(channel=2), a3=_C(channel=2))
        for _u, c in song:
            c.channels = {2: (20, 20), 4: (20, 20), 7: (19, 20), 9: (5, 20)}
        R.account_clients["a1"].ma_doi_kenh(4, 2)
        R.account_clients["a2"].ma_doi_kenh(4, 4)
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, st, song), 9,
                         "kenh 7 chi con 1 cho (can 3) -> phai chon kenh 9")

    def test_ma_CU_thi_khong_tinh_nua(self):
        """Nguoi ra vao lien tuc - cam vinh vien mot kenh la tu bo phi."""
        st = R._pstate(self.PARTY)
        song = self._song(a1=_C(channel=4), a2=_C(channel=2), a3=_C(channel=2))
        R.account_clients["a1"].ma_doi_kenh(4, 2)
        R.account_clients["a1"]._chan_switch_luc -= R.KENH_MA_CON_MOI_SEC + 1
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, st, song), 2)

    def test_ma2_thi_THOI_ra_lenh_doi_kenh(self):
        """`result=2` <khong co khu do> = dang trong instance event -> doi kenh vo nghia."""
        st = R._pstate(self.PARTY)
        song = self._song(a1=_C(channel=4), a2=_C(channel=2), a3=_C(channel=2))
        R.account_clients["a1"].ma_doi_kenh(2, 2)
        self.assertIsNone(R._dieu_phoi_chot_kenh(self.PARTY, st, song))
        self.assertIsNone(st["kenh_dich"])

    def test_KHONG_cho_ai_bao_cao(self):
        """Doc THANG client, khong dung `channel_map_reports` hay `channel_ready` lam dau vao."""
        src = _doc("run_party_digioi.py")
        i = src.find("def _dieu_phoi_chot_kenh(")
        than = src[i:src.find("\ndef ", i + 10)]
        self.assertNotIn("channel_map_reports", than)
        self.assertIn('getattr(c, "current_channel", None)', than)


class TestChotRoiThiGIU(unittest.TestCase):
    """Ham chot chay MOI 2 GIAY. Chot lai tu dau moi nhip = acc vua bat dau chuyen sang kenh A
    thi phan bo doi -> chot kenh B -> ca lu quay dau -> lai doi... Party 3 (06/09) mat 4 phut:
        15:38:28 {1: 1, 2: 1}       -> CHOT 1
        15:38:38 {1: 1, 2: 2}       -> CHOT 2      (doi y sau 10 giay)
        15:41:27 {1: 2, 2: 2, 4: 1} -> CHOT 1
        15:41:39 {1: 3, 2: 1, 4: 1} -> CHOT 2
    """

    PARTY = 0
    ACCS = ("a1", "a2", "a3")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", False, False) for u in self.ACCS]
        self._cl = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)

    def tearDown(self):
        R.party_accounts = self._pa
        R.account_clients.clear(); R.account_clients.update(self._cl)
        R._party_state.pop(self.PARTY, None)

    def _song(self, **kw):
        for u, c in kw.items():
            R.account_clients[u] = c
        return [(u, R.account_clients[u]) for u in self.ACCS if u in R.account_clients]

    def test_phan_bo_doi_giua_chung_thi_VAN_GIU_dich_cu(self):
        song = self._song(a1=_C(channel=1), a2=_C(channel=1), a3=_C(channel=2))
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song), 1)
        # a1 dang tren duong sang 2 (hoac ai do vua vao 2) -> phan bo nghieng ve 2
        R.account_clients["a1"].current_channel = 2
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song), 1,
                         "doi y giua chung -> ca party quay dau, thrash 4 phut")

    def test_qua_HAN_ma_chua_xong_thi_moi_chot_lai(self):
        song = self._song(a1=_C(channel=1), a2=_C(channel=1), a3=_C(channel=2))
        R._dieu_phoi_chot_kenh(self.PARTY, self.st, song)
        self.st["kenh_dich_luc"] -= R.KENH_DICH_KIEN_NHAN_SEC + 1
        R.account_clients["a1"].current_channel = 2
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song), 2)

    def test_dich_bao_DAY_thi_chot_lai_NGAY(self):
        song = self._song(a1=_C(channel=1), a2=_C(channel=1), a3=_C(channel=2))
        R._dieu_phoi_chot_kenh(self.PARTY, self.st, song)
        R.account_clients["a3"].ma_doi_kenh(4, 1)    # a3 vao kenh 1 khong duoc: DAY
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song), 2)

    def test_ve_chung_kenh_thi_xoa_ca_moc(self):
        song = self._song(a1=_C(channel=1), a2=_C(channel=1), a3=_C(channel=2))
        R._dieu_phoi_chot_kenh(self.PARTY, self.st, song)
        R.account_clients["a3"].current_channel = 1
        R._dieu_phoi_chot_kenh(self.PARTY, self.st, song)
        self.assertIsNone(self.st["kenh_dich"])
        self.assertEqual(self.st["kenh_dich_luc"], 0.0)

    def test_kien_nhan_du_dai_cho_acc_dang_danh(self):
        self.assertGreaterEqual(R.KENH_DICH_KIEN_NHAN_SEC, 30)


class TestAccTuSoiVaoKenhDich(unittest.TestCase):
    def setUp(self):
        self.src = _doc("run_party_digioi.py")

    def test_keepalive_co_nhanh_tu_chuyen(self):
        i = self.src.find('st.get("kenh_dich")')
        self.assertGreater(i, 0, "acc khong he soi vao kenh dich -> chot xong khong ai lam")
        khoi = self.src[i:i + 900]
        self.assertIn("switch_channel", khoi)

    def test_khong_chuyen_khi_dang_danh(self):
        i = self.src.find('_kd = st.get("kenh_dich")')
        khoi = self.src[i:i + 400]
        self.assertIn("not c.in_combat()", khoi, "doi kenh giua tran")

    def test_KHONG_bi_vong_bat_tay_chan(self):
        i = self.src.find('_kd = st.get("kenh_dich")')
        khoi = self.src[i:i + 400]
        self.assertNotIn('channel_ready', khoi,
                         "cong channel_ready = nhuong quyet dinh cho vong bat tay")

    def test_vao_kenh_DAY_thi_DI_LUON_khong_bao_cao(self):
        i = self.src.find('_kd = st.get("kenh_dich")')
        khoi = self.src[i:i + 800]
        self.assertNotIn("bao_kenh_day", khoi, "bat acc bao cao = sai luat 'bot dieu phoi'")
        self.assertNotIn("while", khoi, "do lai cho leader pick lai = bug P3")

    def test_APK_giong_PC(self):
        apk = _doc("android", "app", "src", "main", "python", "train_bot", "run_party_digioi.py")
        self.assertIn("def _dieu_phoi_chot_kenh(", apk)


if __name__ == "__main__":
    unittest.main()
