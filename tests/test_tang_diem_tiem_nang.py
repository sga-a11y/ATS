"""TU CONG DIEM TIEM NANG cho nhan vat (KHONG quan tam pet).

Giao thuc: `C:008-001 <設定屬性> +武將索引(2) +種類(1) +數值(4) +參數(1)` - xem KNOWLEDGE.md muc 7o.
Cau truc da duoc capture xac nhan (`int.pcap`, tang INT id=0x1b).

Luat user chot 31/08:
  - Dong dau CO DINH "Point de danh: N" -> LUON giu lai N diem, chi tieu phan VUOT qua N.
  - Cac dong sau la MUC DICH tung chi so, duyet TU TREN XUONG: chua dat thi cong cho du roi moi
    xuong dong tiep; dat roi thi bo qua.
  - Duyet het bang ma van du hon so de danh -> BAO o man "Chu y", khong tu tieu.
  - Acc moi: dung 1 dong "de danh 999" -> khong cong gi.

Rule chot theo diem GOC (khong phai tong co trang bi): cong diem lam tang diem goc, con tong thi
thao/deo do la doi -> chot theo tong se lam bot do diem theo bo do.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# run_party_digioi doc sys.argv[1] lam so PHUT ngay luc import; ten module cua unittest lot vao
# do -> ValueError. Cung cach cac test khac dang lam (vd test_bag_sap_giong_client.py).
_argv = sys.argv
sys.argv = [_argv[0]]
try:
    import run_party_digioi as rpd                   # noqa: E402
finally:
    sys.argv = _argv

from bot.client import GameClient, ATTR_POINT        # noqa: E402


def _bot(du, goc):
    c = GameClient.__new__(GameClient)
    c._label = "t"
    c.char_attrs = {ATTR_POINT: du}
    c.attr_point = du
    c.char_base = dict(goc)
    c.sent = []
    c.send = lambda op, b: c.sent.append((op, b.hex()))
    c.in_combat = lambda **k: False
    return c


class TestGoiTangDiem(unittest.TestCase):
    def test_dung_cau_truc_capture(self):
        """`int.pcap`: 01 00 | 00 00 | 1b | 01 00 00 00 | 00"""
        c = _bot(10, {27: 100})
        self.assertTrue(c.add_attr_point(27, 1))
        self.assertEqual(c.sent[-1], (0x08, "010000001b0100000000"))

    def test_add_0_hoac_am_thi_KHONG_gui(self):
        """Client cung `if add > 0` moi gui (Logic/Status.lua:389)."""
        c = _bot(10, {27: 100})
        self.assertFalse(c.add_attr_point(27, 0))
        self.assertFalse(c.add_attr_point(27, -3))
        self.assertEqual(c.sent, [])

    def test_DANG_TRAN_thi_KHONG_gui(self):
        """Client chan san (UI/UIStatus.lua:2009)."""
        c = _bot(10, {27: 100})
        c.in_combat = lambda **k: True
        self.assertFalse(c.add_attr_point(27, 1))
        self.assertEqual(c.sent, [])

    def test_KHONG_tieu_qua_so_diem_du(self):
        c = _bot(3, {27: 100})
        self.assertFalse(c.add_attr_point(27, 5))
        self.assertEqual(c.sent, [])

    def test_TRU_NGAY_tai_cho(self):
        """Server gui lai `0x08 sub0100` khong tuc thi, ma caller cong lien tiep nhieu o."""
        c = _bot(10, {27: 100})
        c.add_attr_point(27, 4)
        self.assertEqual(c.attr_point_left(), 6)
        self.assertEqual(c.char_diem_goc()[27], 104, "diem goc phai tang ngay cho rule dong sau")


class TestBangRule(unittest.TestCase):
    def _chay(self, du, goc, cfg):
        c = _bot(du, goc)
        da, thua = rpd.auto_cong_diem(c, cfg)
        return c, da, thua

    def test_GIU_LAI_so_de_danh(self):
        c, da, _t = self._chay(35, {30: 0},
                               {"reserve": 30, "rules": [{"stat": "agi", "target": 42}]})
        self.assertEqual(da, 5, "chi duoc tieu phan VUOT qua so de danh")
        self.assertEqual(c.attr_point_left(), 30)

    def test_du_KHONG_qua_so_de_danh_thi_khong_cong_gi(self):
        c, da, thua = self._chay(30, {30: 0},
                                 {"reserve": 30, "rules": [{"stat": "agi", "target": 42}]})
        self.assertEqual((da, thua), (0, 0))
        self.assertEqual(c.sent, [])

    def test_duyet_TU_TREN_XUONG_dat_roi_thi_bo_qua(self):
        """Vi du user: de danh 30 | agi 42 | hpx 10 | int 64. AGI da 50 -> nhay sang HPx."""
        cfg = {"reserve": 0, "rules": [{"stat": "agi", "target": 42},
                                       {"stat": "hpx", "target": 10},
                                       {"stat": "int", "target": 64}]}
        c, da, _t = self._chay(100, {30: 50, 31: 0, 27: 60}, cfg)
        self.assertEqual(da, 10 + 4)
        self.assertEqual(len(c.sent), 2, "AGI da dat ma van gui -> tieu oan diem")

    def test_cong_DU_muc_roi_moi_xuong_dong(self):
        cfg = {"reserve": 0, "rules": [{"stat": "agi", "target": 42},
                                       {"stat": "hpx", "target": 10}]}
        c, _d, _t = self._chay(100, {30: 40, 31: 0}, cfg)
        self.assertEqual(c.char_diem_goc()[30], 42)
        self.assertEqual(c.char_diem_goc()[31], 10)

    def test_HET_DIEM_giua_chung_thi_dung(self):
        cfg = {"reserve": 0, "rules": [{"stat": "agi", "target": 100},
                                       {"stat": "int", "target": 100}]}
        c, da, thua = self._chay(10, {30: 0, 27: 0}, cfg)
        self.assertEqual((da, thua), (10, 0))
        self.assertEqual(c.char_diem_goc()[27], 0, "het diem ma van cong dong sau")

    def test_duyet_HET_bang_ma_con_DU_thi_bao_lai(self):
        cfg = {"reserve": 10, "rules": [{"stat": "agi", "target": 5}]}
        _c, da, thua = self._chay(100, {30: 0}, cfg)
        self.assertEqual(da, 5)
        self.assertEqual(thua, 85, "khong bao so du -> user khong biet ma them dong")

    def test_acc_MOI_khong_cong_gi(self):
        c, da, thua = self._chay(500, {30: 0}, rpd.diem_rules_mac_dinh())
        self.assertEqual((da, thua), (0, 0))
        self.assertEqual(c.sent, [], "acc chua config ma da tieu diem = khong lay lai duoc")

    def test_CHUA_biet_diem_goc_thi_KHONG_doan(self):
        c = _bot(100, {})
        cfg = {"reserve": 0, "rules": [{"stat": "agi", "target": 9}]}
        self.assertEqual(rpd.auto_cong_diem(c, cfg), (0, 0))
        self.assertEqual(c.sent, [])

    def test_cfg_rac_khong_lam_sap(self):
        _c, da, _t = self._chay(100, {30: 0},
                                {"reserve": "x", "rules": [{"stat": "khong_co"}, "rac", None]})
        self.assertEqual(da, 0)


class TestDangTranThiXEP_HANG(unittest.TestCase):
    """Cong TAY luc dang danh -> XEP HANG y het lenh tui do, het tran bot tu gui.

    User 31/08: "lam nhu cai doi trang bi ay, de khi het tran moi gui len cong di" - truoc do
    dialog bao loi "Khong cong duoc 20 vao HPx" roi thoi, user phai tu canh luc het tran.
    """

    def test_dang_tran_thi_tra_queued_va_KHONG_gui(self):
        c = _bot(100, {31: 0})
        c.in_combat = lambda **k: True
        c.state = type("S", (), {"in_battle": True})()
        c._bag_queue = []
        rpd.account_clients["accX"] = c
        try:
            self.assertEqual(rpd.add_point("accX", "hpx", 20), "queued")
            self.assertEqual(c.sent, [], "gui giua tran -> server nuot")
            self.assertEqual(len(c._bag_queue), 1, "khong xep hang -> mat lenh cua user")
        finally:
            rpd.account_clients.pop("accX", None)

    def test_KHONG_trong_tran_thi_gui_NGAY(self):
        c = _bot(100, {31: 0})
        c.state = type("S", (), {"in_battle": False})()
        c._bag_queue = []
        rpd.account_clients["accX"] = c
        try:
            self.assertIs(rpd.add_point("accX", "hpx", 20), True)
            self.assertEqual(len(c.sent), 1)
            self.assertEqual(c._bag_queue, [])
        finally:
            rpd.account_clients.pop("accX", None)

    def test_lenh_xep_hang_chay_dung_khi_xa(self):
        """Ham xep hang phai la lenh cong diem THAT, khong phai closure rong."""
        c = _bot(100, {31: 0})
        c.in_combat = lambda **k: True
        c.state = type("S", (), {"in_battle": True})()
        c._bag_queue = []
        rpd.account_clients["accX"] = c
        try:
            rpd.add_point("accX", "hpx", 20)
            _ten, fn = c._bag_queue[0][0], c._bag_queue[0][1]
            self.assertIn("HPx", _ten, "ten lenh phai noi ro cong gi (hien o log xa hang doi)")
            c.in_combat = lambda **k: False          # gia lap het tran
            self.assertTrue(fn())
            self.assertEqual(c.char_diem_goc()[31], 20)
        finally:
            rpd.account_clients.pop("accX", None)

    def test_GUI_bao_da_xep_hang_chu_khong_bao_LOI(self):
        with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def _cong_tay(self):")
        than = s[i:i + 1800]
        self.assertIn('kq == "queued"', than, "khong phan biet -> van bao loi nhu cu")
        self.assertIn("đã xếp hàng", than)
        self.assertNotIn("KHÔNG trong trận", than,
                         "con cau bao loi cu -> user tuong that bai trong khi da xep hang")


class TestCacheBangDiem(unittest.TestCase):
    """Acc TAT van XEM duoc bang diem (user 31/08: "them cache chi so de xem point va luc off acc,
    ko cong diem duoc thoi"). Dung chung file `account_skills_cache.json` y het cach cache pet nha
    tro (`save_inn_cache`) - file do da co san duong nap o ca PC lan APK."""

    def test_ghi_va_doc_lai_duoc(self):
        from bot.client import save_point_cache, load_point_cache
        diem = {"left": 64, "stats": [{"key": "agi", "ten": "AGI", "ma": 30,
                                       "goc": 28, "tong": 29}]}
        save_point_cache("acc_cache_test", diem)
        doc, ts = load_point_cache("acc_cache_test")
        self.assertEqual(doc, diem)
        self.assertGreater(ts, 0)

    def test_acc_khong_co_cache_thi_tra_None(self):
        from bot.client import load_point_cache
        self.assertEqual(load_point_cache("acc_chua_bao_gio_chay_xyz"), (None, 0))

    def test_acc_TAT_thi_point_info_doc_CACHE(self):
        diem = {"left": 7, "stats": [{"key": "int", "ten": "INT", "ma": 27,
                                      "goc": 5, "tong": 9}]}
        from bot.client import save_point_cache
        save_point_cache("acc_tat_test", diem)
        rpd.account_clients.pop("acc_tat_test", None)
        out = rpd.point_info("acc_tat_test")
        self.assertTrue(out.get("cache"), "khong danh dau cache -> user tuong so dang live")
        self.assertEqual(out.get("left"), 7)

    def test_acc_CHAY_thi_GHI_cache(self):
        from bot.client import load_point_cache
        c = _bot(42, {27: 11, 28: 0, 29: 0, 30: 0, 31: 0, 32: 0})
        c.char_stat_full = lambda: {27: 99}
        rpd.account_clients["acc_chay_test"] = c
        try:
            out = rpd.point_info("acc_chay_test")
            self.assertFalse(out.get("cache"))
            self.assertEqual(out["left"], 42)
        finally:
            rpd.account_clients.pop("acc_chay_test", None)
        doc, _ts = load_point_cache("acc_chay_test")
        self.assertEqual(doc["left"], 42, "acc chay ma khong ghi cache -> tat di la mat so")

    def test_GUI_noi_ro_dang_xem_so_da_luu(self):
        with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("class PointDialog(")
        than = s[i:s.find("\nclass ", i + 10)]
        self.assertIn('info.get("cache")', than, "khong phan biet -> user bam cong mai khong an")
        self.assertIn("đang TẮT", than)


class TestThongBaoDuDiem(unittest.TestCase):
    def test_co_ham_cho_man_chu_y(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn("def diem_du_notify_items(pidx):", s)
        self.assertIn("def diem_du_notify_skip(username):", s)

    def test_GUI_PC_co_dong_hien_thi(self):
        with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn("ctrl.diem_du_notify_items(pidx)", s, "khong gop vao man Chu y")
        i = s.find('if it.get("_diem_du"):')
        self.assertGreater(i, 0)
        khoi = s[i:i + 900]
        self.assertIn("còn dư", khoi)
        self.assertIn("ctrl.diem_du_notify_skip(_u)", khoi)
        self.assertIn("_skips.append", khoi, "khong vao _skips thi 'Bo qua tat ca' khong phu")


class TestChayLucLogin(unittest.TestCase):
    def test_goi_TRUOC_buoc_nang_skill_pet(self):
        """User chot 31/08: cho vao viec vat, truoc cai check nang skill cho pet."""
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        i_diem = s.find("_tu_cong_diem(c, username, label)")
        i_pet = s.find('pcfg.get("auto_pet_skill", True)')
        self.assertGreater(i_diem, 0, "khong goi luc login")
        self.assertGreater(i_pet, i_diem, "phai chay TRUOC buoc nang skill pet")

    def test_acc_chua_config_dung_mac_dinh_KHONG_CONG(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def _tu_cong_diem(")
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertIn("diem_rules_mac_dinh()", than)


class TestGUIPointDialog(unittest.TestCase):
    def setUp(self):
        with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            self.src = fh.read()
        i = self.src.find("class PointDialog(")
        self.assertGreater(i, 0)
        self.than = self.src[i:self.src.find("\nclass ", i + 10)]

    def test_co_nut_Point_BEN_PHAI_tui_do(self):
        """User chot 31/08: nut Point dat BEN PHAI nut tui do."""
        self.assertIn('text="Point"', self.src)
        self.assertIn("self._open_point_dialog(row)", self.src)
        i_bag = self.src.find("_bag_btn.pack(side=")
        i_point = self.src.find('ttk.Button(fr, text="Point"')
        self.assertGreater(i_bag, 0)
        self.assertGreater(i_point, i_bag, "nut Point phai nam SAU nut tui do")

    def test_hien_CA_GOC_LAN_TONG(self):
        """User chot: hien diem goc VA ca diem sau khi tong hop trang bi/thu cuoi."""
        self.assertIn('("Gốc", 8), ("Tổng", 8)', self.than)
        self.assertIn("self.lbl_goc", self.than)
        self.assertIn("self.lbl_tong", self.than)

    def test_hien_diem_DU(self):
        self.assertIn("Điểm dư:", self.than)

    def test_cong_TAY_duoc(self):
        self.assertIn("ctrl.add_point(self.username, key, add)", self.than)

    def test_bang_rule_them_xoa_dong(self):
        self.assertIn("+ Thêm dòng", self.than)
        self.assertIn("def _xoa():", self.than)
        self.assertIn("Point để dành:", self.than)

    def test_mac_dinh_999(self):
        self.assertIn('tk.StringVar(value="999")', self.than)

    def test_luu_va_ap_LIVE(self):
        self.assertIn('settings["point"] = cfg', self.than)
        self.assertIn("ctrl.apply_point_config(self.username, cfg)", self.than)

    def test_config_doc_settings_point(self):
        with io.open(os.path.join(ROOT, "bot", "config.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn("ACCOUNT_POINT = {}", s)
        self.assertIn('_pt = _s.get("point")', s)


if __name__ == "__main__":
    unittest.main()
