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

from tests.party_controller_helpers import quyet_party

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
    def test_worker_ngu_sau_viec_tra_ve_ngay(self):
        src = _doc("bot", "party_engine.py")
        i = src.find("class AccWorker:")
        j = src.find("class PartyEngine:", i)
        body = src[i:j]
        self.assertIn("NHIP_WORKER_SEC", body)
        self.assertIn("self._huy.wait(_con)", body)

    def test_engine_giao_gom_tang_bang_worker(self):
        src = _doc("bot", "party_engine.py")
        self.assertIn("VIEC_FC_GOM", src)
        self.assertIn("regroup_to_event_start", src)



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
        return quyet_party(R, self.PARTY, st, song, lech_tu)

    def test_cung_map_lech_kenh_thi_DONG_BO(self):
        """Party 5: ca 5 acc o 12922, kenh [1,5] -> gom ve thanh la vo nghia."""
        cu = __import__("time").time() - 999
        kh, _ly, _lt = self._quyet(
            {"a1": _C(12922, 1), "a2": _C(12922, 5), "a3": _C(12922, 5)}, cu)
        self.assertEqual(kh["viec"], R.VIEC_DONG_BO)

    def test_KHONG_doi_leader_bao_cao_moi_chiu_dong_bo(self):
        """Truoc day phai co `_lech_kenh_that` (bao cao doi chieu tung cap cua leader) moi vao
        nhanh DONG_BO; leader ban viec khac la roi thang xuong GOM."""
        src = _doc(os.path.join("bot", "party_engine.py"))
        i = src.find("viec = DP_DONG_BO if")
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
        i = src.find("def _engine_ap_dung_party(")
        body = src[i:src.find("\ndef ", i + 10)]
        self.assertIn('kh["tang_gom"] = _chot_tang_gom(', body,
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


class TestMoiAccNhanViecGomTang(unittest.TestCase):
    def _jobs(self, leader_fighting=False):
        from bot import party_engine as PE
        accs = [PE.AnhAcc("leader", la_leader=True, map_id=12925, kenh=1,
                           so_member=2, trong_event=True, dang_danh=leader_fighting),
                PE.AnhAcc("member1", map_id=12924, kenh=1, so_member=2,
                           trong_event=True),
                PE.AnhAcc("member2", map_id=12925, kenh=1, so_member=2,
                           trong_event=True)]
        anh = PE.AnhParty(0, accs, can_bao_nhieu=2, pha=PE.PHA_EVENT,
                          tang_gom=12924)
        return PE.quyet_dinh(anh)

    def test_leader_va_member_lech_tang_deu_duoc_giao_gom(self):
        from bot import party_engine as PE
        jobs = self._jobs()
        self.assertEqual(jobs["leader"], PE.VIEC_FC_GOM)
        self.assertEqual(jobs["member2"], PE.VIEC_FC_GOM)

    def test_dung_tang_thi_nghi(self):
        from bot import party_engine as PE
        self.assertEqual(self._jobs()["member1"], PE.VIEC_NGHI)

    def test_khong_di_giua_tran(self):
        from bot import party_engine as PE
        self.assertEqual(self._jobs(leader_fighting=True)["leader"], PE.VIEC_NGHI)



class TestNhanhChetDaBiXoa(unittest.TestCase):
    def test_chi_con_MOT_nhanh_lech_tang(self):
        """One engine decision assigns the regroup task to every off-floor account."""
        from bot import party_engine as PE
        accs = [PE.AnhAcc("leader", la_leader=True, map_id=12925, kenh=1,
                           so_member=1, trong_event=True),
                PE.AnhAcc("member", map_id=12924, kenh=1, so_member=1,
                           trong_event=True)]
        jobs = PE.quyet_dinh(PE.AnhParty(0, accs, can_bao_nhieu=1,
                                         pha=PE.PHA_EVENT, tang_gom=12924))
        self.assertEqual(jobs["leader"], PE.VIEC_FC_GOM)
        self.assertEqual(jobs["member"], PE.VIEC_NGHI)

    def test_nhanh_con_lai_gom_ve_TANG_THAP_NHAT(self):
        src = _doc("run_party_digioi.py")
        self.assertIn("def _chot_tang_gom(", src)
        self.assertIn('kh["tang_gom"] = _chot_tang_gom(', src)

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
