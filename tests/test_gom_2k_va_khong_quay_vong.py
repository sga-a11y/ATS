"""GOM trong pha EVENT: di bo xuong tang, KHONG ve thanh - va khong duoc quay vong tran.

Party 5 (06/09) - leader `thsau` co 422.627 dong log, trong do 201.495 cap lap lai:
    13:20:58 (LEADER) dieu phoi bao GOM (party lech kenh [1, 5]) -> thoi moi, gom lai
    13:20:58 (LEADER) reform: khong co smart/legacy route -> bo qua
Cao diem 7.985 dong trong MOT giay. Ba loi chong nhau:

  1. `_do_reform()` di theo route VE THANH; trong thap 2K khong co route nao -> tra ve NGAY,
     roi `continue` KHONG NGU -> vong nong 8.000 vong/giay. Vong do an GIL + ghi log lien tuc nen
     BO DOI luon luong dieu phoi: ke hoach dong bang o `viec=gom` suot 5 phut du ca party da
     chung kenh tu 13:15:37. Vong nong tu nuoi chinh no.
  2. Ca 5 acc deu o map 12922 (CUNG map, chi lech KENH) ma van ra lenh GOM. Cung map thi phai
     DONG BO TAI CHO - gom ve thanh giua thap 2K la vo nghia.
  3. Lenh GOM trong thap phai la DI BO XUONG TANG, khong phai reform.

Party 1 (06/09) cung goc: leader len tang 12925 mot minh, 4 member o 12924. Dieu phoi bat dung
("2 MAP khac nhau [12924, 12925]") nhung lenh gom khong ai thi hanh duoc.

VA: code "lech tang thi gom ve TANG THAP NHAT ca doi toi duoc" (`_2k_regroup_target`, commit
032f42a ngay 09/08) DA CO nhung CHET - no nam o nhanh `elif` thu HAI voi dieu kien y HET nhanh
thu nhat ngay tren, nen Python khong bao gio vao. Nhanh thu nhat xuong thang DAY thap (12922),
mat het tang da leo.
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
    def __init__(self, map_id, channel=1):
        self.running = True
        self.current_map = map_id
        self.current_channel = channel
        self.party_idx = 0
        self.flee_mode = False
        self.di = []

    def regroup_to_event_start(self, ev, dest=None):
        self.di.append(int(dest))
        return True


EV_2K = {"dest_map": 12922, "party_battle": {"kind": "floor_crawl"},
         "floor_maps": [12922, 12923, 12924, 12925, 12931]}


class TestKhongQuayVongTran(unittest.TestCase):
    def test_thi_hanh_GOM_xong_phai_NGU_mot_nhip(self):
        src = _doc("run_party_digioi.py")
        i = src.find('dieu phoi bao GOM (%s) -> thoi moi, gom lai')
        self.assertGreater(i, 0)
        khoi = src[i:i + 2200]
        ngu = khoi.find("time.sleep(KE_HOACH_NHIP)")
        self.assertGreater(ngu, 0, "khong ngu -> quay 8.000 vong/giay (party 5, 06/09)")
        # `continue` cua MA (canh le 24 dau cach), khong phai chu trong chu thich.
        tiep = khoi.find(chr(10) + " " * 24 + "continue")
        self.assertGreater(tiep, ngu, "ngu phai nam TRUOC continue")

    def test_khong_goi_thang_do_reform_nua(self):
        """`_do_reform` o map event la lenh RONG -> phai qua `_thi_hanh_gom` de con biet duong
        di bo xuong tang."""
        src = _doc("run_party_digioi.py")
        i = src.find('dieu phoi bao GOM (%s) -> thoi moi, gom lai')
        khoi = src[i:i + 900]
        self.assertIn("_thi_hanh_gom(", khoi)


class TestCungMapThiDONG_BO_ChuKhongGom(unittest.TestCase):
    PARTY = 0

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", False, False) for u in ("a1", "a2", "a3")]
        self._cl = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        R.config.PARTY_CONFIG = {self.PARTY: {"mode": "event", "event_key": "2k"}}

    def tearDown(self):
        R.party_accounts = self._pa
        R.account_clients.clear(); R.account_clients.update(self._cl)
        R._party_state.pop(self.PARTY, None)
        R.config.PARTY_CONFIG = self._pc

    def _quyet(self, clients, lech_tu):
        st = R._pstate(self.PARTY)
        song = []
        for u, c in clients.items():
            R.account_clients[u] = c
            song.append((u, c))
        return R._dieu_phoi_quyet(self.PARTY, st, song, lech_tu)

    def test_cung_map_lech_kenh_thi_DONG_BO(self):
        """Party 5: ca 5 acc o 12922, kenh [1,5] -> gom ve thanh la vo nghia."""
        cu = __import__("time").time() - 999
        kh, _ly, _lt = self._quyet(
            {"a1": _C(12922, 1), "a2": _C(12922, 5), "a3": _C(12922, 5)}, cu)
        self.assertEqual(kh["viec"], R.VIEC_DONG_BO)

    def test_KHONG_doi_leader_bao_cao_moi_chiu_dong_bo(self):
        """Truoc day phai co `_lech_kenh_that` (bao cao doi chieu tung cap cua leader) moi vao
        nhanh DONG_BO; leader ban viec khac la roi thang xuong GOM."""
        src = _doc("run_party_digioi.py")
        i = src.find("viec = VIEC_DONG_BO if")
        self.assertGreater(i, 0)
        dong = src[i:src.find("\n", i)]
        self.assertNotIn("_lech_kenh_that", dong)

    def test_lech_MAP_thi_van_GOM(self):
        cu = __import__("time").time() - 999
        kh, _ly, _lt = self._quyet(
            {"a1": _C(12924, 1), "a2": _C(12925, 1), "a3": _C(12924, 1)}, cu)
        self.assertEqual(kh["viec"], R.VIEC_GOM)


class TestTangGom2K(unittest.TestCase):
    PARTY = 0

    def setUp(self):
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        R.config.PARTY_CONFIG = {self.PARTY: {"mode": "event", "event_key": "2k"}}
        self._ehn = R.config.event_hom_nay
        R.config.event_hom_nay = lambda key, now=None: EV_2K if key == "2k" else None
        self._itr = R._inside_floor_crawl_tower
        R._inside_floor_crawl_tower = lambda ev, m: int(m) in (EV_2K["floor_maps"])

    def tearDown(self):
        R.config.PARTY_CONFIG = self._pc
        R.config.event_hom_nay = self._ehn
        R._inside_floor_crawl_tower = self._itr

    def test_lay_TANG_THAP_NHAT_ca_doi_dang_o(self):
        """Party 1: leader 12925, 4 member 12924 -> gom o 12924, KHONG tut ve day 12922."""
        song = [("a1", _C(12925)), ("a2", _C(12924)), ("a3", _C(12924))]
        self.assertEqual(R._tang_gom_2k(self.PARTY, song), 12924)

    def test_co_acc_NGOAI_thap_thi_ve_CUA_VAO(self):
        song = [("a1", _C(12925)), ("a2", _C(12003))]
        self.assertEqual(R._tang_gom_2k(self.PARTY, song), 12922)

    def test_KHONG_AI_trong_thap_thi_tra_None(self):
        """Cho goi dung ket qua nay de biet "party co dang trong thap khong" (chan lenh doi kenh).
        Tra `dest_map` khi ca party dang o thanh = chan nham doi kenh o moi noi."""
        song = [("a1", _C(12001)), ("a2", _C(12001))]
        self.assertIsNone(R._tang_gom_2k(self.PARTY, song))

    def test_event_khac_thi_khong_dinh_toi(self):
        R.config.event_hom_nay = lambda key, now=None: {"dest_map": 10991}
        self.assertIsNone(R._tang_gom_2k(self.PARTY, [("a1", _C(10991))]))

    def test_doc_map_LIVE_chu_khong_doc_bang_luc_login(self):
        """`st["event_start_map"]` chi duoc dien luc LOGIN -> khong bat duoc lech tang GIUA CHUNG
        (dung ca party 1)."""
        src = _doc("run_party_digioi.py")
        i = src.find("def _tang_gom_2k(")
        than = src[i:src.find("\ndef ", i + 10)]
        ma = than[than.find('"""', than.find('"""') + 3):]      # bo docstring
        self.assertIn('getattr(c, "current_map"', ma)
        self.assertNotIn("event_start_map", ma)


class TestTangGomPhaiDINH(unittest.TestCase):
    """L6: chot roi thi GIU. Tinh lai moi nhip = dich tut theo buoc chan member dang di xuong.

    Party 8 (06/09) - user: "bot dang lam gi ma moi dua 1 noi":
        17:47:08 gom [12932, 12934] -> dich 12932
        17:47:19 gom [12931, 12934] -> dich 12931   (member vua xuong 12931)
        17:51:05 gom [12922, 12934] -> dich 12922   (tut toi DAY thap, mat het tang da leo)
    """

    PARTY = 0

    def setUp(self):
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        R.config.PARTY_CONFIG = {self.PARTY: {"mode": "event", "event_key": "2k"}}
        self._ehn = R.config.event_hom_nay
        R.config.event_hom_nay = lambda key, now=None: EV_2K if key == "2k" else None
        self._itr = R._inside_floor_crawl_tower
        R._inside_floor_crawl_tower = lambda ev, m: 12922 <= int(m) <= 12938
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)

    def tearDown(self):
        R.config.PARTY_CONFIG = self._pc
        R.config.event_hom_nay = self._ehn
        R._inside_floor_crawl_tower = self._itr
        R._party_state.pop(self.PARTY, None)

    def test_member_di_xuong_thi_dich_KHONG_tut_theo(self):
        song = [("a1", _C(12934)), ("a2", _C(12932)), ("a3", _C(12932))]
        self.assertEqual(R._chot_tang_gom(self.PARTY, self.st, song), 12932)
        song[1][1].current_map = 12931          # a2 dang tren duong xuong
        song[2][1].current_map = 12931
        self.assertEqual(R._chot_tang_gom(self.PARTY, self.st, song), 12932,
                         "dich tut theo buoc chan -> ca doi tut toi day thap")

    def test_qua_HAN_thi_chot_lai(self):
        song = [("a1", _C(12934)), ("a2", _C(12932))]
        R._chot_tang_gom(self.PARTY, self.st, song)
        self.st["tang_gom_luc"] -= R.TANG_GOM_KIEN_NHAN_SEC + 1
        song[1][1].current_map = 12931
        self.assertEqual(R._chot_tang_gom(self.PARTY, self.st, song), 12931)

    def test_gom_XONG_thi_xoa_dich(self):
        song = [("a1", _C(12934)), ("a2", _C(12932))]
        R._chot_tang_gom(self.PARTY, self.st, song)
        song[0][1].current_map = 12932          # ca doi da ve cung tang
        self.assertIsNone(R._chot_tang_gom(self.PARTY, self.st, song))
        self.assertIsNone(self.st["tang_gom"])

    def test_ra_khoi_thap_thi_xoa_dich(self):
        song = [("a1", _C(12934)), ("a2", _C(12932))]
        R._chot_tang_gom(self.PARTY, self.st, song)
        for _u, c in song:
            c.current_map = 12001               # ca doi da ra ngoai
        self.assertIsNone(R._chot_tang_gom(self.PARTY, self.st, song))
        self.assertEqual(self.st["tang_gom_luc"], 0.0)

    def test_kien_nhan_du_dai_cho_di_bo_vai_tang(self):
        self.assertGreaterEqual(R.TANG_GOM_KIEN_NHAN_SEC, 120)

    def test_ke_hoach_dung_ban_DA_CHOT(self):
        src = _doc("run_party_digioi.py")
        i = src.find('kh["tang_gom"]')
        self.assertIn("_chot_tang_gom(", src[i:i + 120],
                      "goi thang `_tang_gom_2k` moi nhip = tinh lai = tut dich (L6)")


class TestThiHanhGom(unittest.TestCase):
    def setUp(self):
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        R.config.PARTY_CONFIG = {0: {"mode": "event", "event_key": "2k"}}
        self._ehn = R.config.event_hom_nay
        R.config.event_hom_nay = lambda key, now=None: EV_2K if key == "2k" else None

    def tearDown(self):
        R.config.PARTY_CONFIG = self._pc
        R.config.event_hom_nay = self._ehn

    def test_trong_thap_thi_DI_BO_xuong_tang_chu_khong_reform(self):
        c = _C(12925)
        goi = []
        R._thi_hanh_gom(c, R._pstate(0), "x", "LEADER",
                        {"tang_gom": 12924, "ly_do": "lech tang"}, lambda: goi.append(1))
        self.assertEqual(c.di, [12924])
        self.assertEqual(goi, [], "van goi _do_reform -> lenh rong trong thap")

    def test_da_o_dung_tang_thi_DUNG_YEN(self):
        c = _C(12924)
        R._thi_hanh_gom(c, R._pstate(0), "x", "LEADER", {"tang_gom": 12924}, lambda: None)
        self.assertEqual(c.di, [], "dang o dung tang gom ma van di")

    def test_ngoai_event_thi_van_reform_nhu_cu(self):
        c = _C(12001)
        goi = []
        R._thi_hanh_gom(c, R._pstate(0), "x", "LEADER", {"ly_do": "lech map"},
                        lambda: goi.append(1))
        self.assertEqual(goi, [1])


class TestMOI_ACC_deu_thi_hanh_gom_tang(unittest.TestCase):
    """Lenh gom tang phai toi MOI ACC, khong rieng leader.

    Party 8 (06/09, 17:55) - user: "ca lu co di chuyen ty nao deo dau":
        lbumot (LEADER) map=12928            <- da tut xuong TANG 5, dang leo nguoc len MOT MINH
        lubhai/lubba/lubbon/lubnam map=12934  <- dung im tang 11, pos=(650,430)
    `_thi_hanh_gom` chi duoc goi trong vong MOI cua leader -> member khong co cho nao thi hanh
    -> cang gom cang lech.
    """

    def setUp(self):
        self.src = _doc("run_party_digioi.py")

    def test_keepalive_co_nhanh_tu_di_ve_tang_gom(self):
        i = self.src.find('_tg = (_ke_hoach(st) or {}).get("tang_gom")')
        self.assertGreater(i, 0, "member khong co cho thi hanh lenh gom tang")
        khoi = self.src[i:i + 1200]
        self.assertIn("regroup_to_event_start(", khoi)

    def test_nhanh_do_KHONG_phan_biet_leader(self):
        """Leader va member deu la acc thi hanh - khong duoc mien ai."""
        i = self.src.find('_tg = (_ke_hoach(st) or {}).get("tang_gom")')
        khoi = self.src[i:i + 1200]
        self.assertNotIn("is_leader", khoi)

    def test_da_o_dung_tang_thi_khong_di(self):
        i = self.src.find('_tg = (_ke_hoach(st) or {}).get("tang_gom")')
        khoi = self.src[i:i + 400]
        self.assertIn('!= int(_tg)', khoi)

    def test_khong_di_giua_tran(self):
        i = self.src.find('_tg = (_ke_hoach(st) or {}).get("tang_gom")')
        self.assertIn("not c.in_combat()", self.src[i:i + 300])


class TestNhanhChetDaBiXoa(unittest.TestCase):
    def test_chi_con_MOT_nhanh_lech_tang(self):
        """Hai `elif` dieu kien y het nhau -> nhanh duoi (co `_2k_regroup_target`) khong bao gio
        chay. Ton tai am tham tu 09/08."""
        src = _doc("run_party_digioi.py")
        self.assertEqual(src.count("elif _inside_floor_crawl_tower(ev, c.current_map):"), 1)

    def test_nhanh_con_lai_gom_ve_TANG_THAP_NHAT(self):
        src = _doc("run_party_digioi.py")
        i = src.find("elif _inside_floor_crawl_tower(ev, c.current_map):")
        self.assertIn("_2k_regroup_target", src[i:i + 900])

    def test_client_chi_con_MOT_regroup_to_event_start(self):
        self.assertEqual(_doc("bot", "client.py").count("def regroup_to_event_start("), 1)

    def test_ban_con_lai_nhan_duoc_dest(self):
        src = _doc("bot", "client.py")
        i = src.find("def regroup_to_event_start(")
        self.assertIn("dest", src[i:src.find("\n", i)])


class TestAPKGiongPC(unittest.TestCase):
    def test_apk_co_du(self):
        apk = _doc("android", "app", "src", "main", "python", "train_bot", "run_party_digioi.py")
        self.assertIn("def _thi_hanh_gom(", apk)
        self.assertIn("def _tang_gom_2k(", apk)


if __name__ == "__main__":
    unittest.main()
