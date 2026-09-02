"""Tu mo rong tui do: mua slot toi khi GIA LAN KE TIEP vuot nguong.

User chot 02/09: "them cai tick 'Tu mo rong tui do den xxx vang' -> xxx la o dien so duoc.
Neu tick thi tu mo rong tui do den khi vang yeu cau lon hon so duoc dien, vi du dien 250 thi mua
den khi mua xong lan 250 (lan tiep theo can 260 thi dung). O tick nam o dau tien, truoc cai tu ban
noi dat."

=> nguong la BAO GOM: gia == nguong thi VAN MUA, gia > nguong moi dung.
Goi da co san: `query_bag_slot_price` (0x54 sub01 sellId=3) va `buy_bag_slot` (0x54 sub02).
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient        # noqa: E402


class _Bot:
    tu_mo_rong_tui = GameClient.tu_mo_rong_tui
    BAG_EXPAND_MAX_LAN = GameClient.BAG_EXPAND_MAX_LAN

    def __init__(self, gia_list, maxed_sau=None, mua_loi_o=None):
        self._label = "t"
        self.running = True
        self._gia = list(gia_list)          # gia cua tung lan mua ke tiep
        self._maxed_sau = maxed_sau         # da mua bao nhieu slot thi coi la MAX
        self._mua_loi_o = mua_loi_o         # lan thu may thi buy tra False
        self.da_mua = 0
        self.hoi_gia = 0

    def bag_slot_maxed(self):
        return self._maxed_sau is not None and self.da_mua >= self._maxed_sau

    def bag_capacity(self):
        return 50 + self.da_mua * 5

    def query_bag_slot_price(self, wait=2.0):
        self.hoi_gia += 1
        if self.da_mua >= len(self._gia):
            return None
        return (self._gia[self.da_mua], 1)

    def buy_bag_slot(self, wait=2.0):
        if self._mua_loi_o is not None and self.da_mua == self._mua_loi_o:
            return False
        self.da_mua += 1
        return True


class TestNguongBaoGom(unittest.TestCase):
    def test_dung_khi_gia_VUOT_nguong(self):
        """Vi du cua user: dien 250 -> mua xong lan 250, lan sau 260 thi dung."""
        b = _Bot([230, 240, 250, 260, 270])
        self.assertEqual(b.tu_mo_rong_tui(250), 3)

    def test_gia_BANG_nguong_thi_VAN_MUA(self):
        b = _Bot([250, 260])
        self.assertEqual(b.tu_mo_rong_tui(250), 1)

    def test_gia_dau_tien_da_vuot_thi_KHONG_mua_gi(self):
        b = _Bot([300])
        self.assertEqual(b.tu_mo_rong_tui(250), 0)

    def test_nguong_0_thi_KHONG_lam_gi(self):
        """Tick nhung de trong o so -> khong duoc mua bua."""
        b = _Bot([10, 10, 10])
        self.assertEqual(b.tu_mo_rong_tui(0), 0)
        self.assertEqual(b.hoi_gia, 0, "khong duoc hoi gia khi chua dat nguong")

    def test_nguong_am_cung_khong_lam_gi(self):
        self.assertEqual(_Bot([10]).tu_mo_rong_tui(-5), 0)


class TestDungDungLuc(unittest.TestCase):
    def test_DA_TOI_DA_thi_dung(self):
        b = _Bot([10] * 10, maxed_sau=3)
        self.assertEqual(b.tu_mo_rong_tui(999999), 3)

    def test_mua_THAT_BAI_thi_dung_ngay(self):
        """Het tien / server tu choi -> dung, khong lap vo ich."""
        b = _Bot([10] * 10, mua_loi_o=2)
        self.assertEqual(b.tu_mo_rong_tui(999999), 2)

    def test_khong_hoi_duoc_gia_thi_dung(self):
        b = _Bot([10, 10])          # het gia -> query tra None
        self.assertEqual(b.tu_mo_rong_tui(999999), 2)

    def test_acc_STOP_thi_dung(self):
        b = _Bot([10] * 10)
        _buy = b.buy_bag_slot

        def _mua_roi_stop(wait=2.0):
            b.running = False
            return _buy(wait)
        b.buy_bag_slot = _mua_roi_stop
        self.assertEqual(b.tu_mo_rong_tui(999999), 1)

    def test_co_CAP_CUNG_so_lan(self):
        """Cau hinh sai (nguong khong lo) khong duoc lam bot mua tron doi."""
        b = _Bot([1] * 500)
        self.assertEqual(b.tu_mo_rong_tui(10 ** 9), GameClient.BAG_EXPAND_MAX_LAN)


class TestNoiDayDu(unittest.TestCase):
    def setUp(self):
        def _doc(p):
            with io.open(os.path.join(ROOT, p), encoding="utf-8") as fh:
                return fh.read()
        self.cfg = _doc("bot/config.py")
        self.rpd = _doc("run_party_digioi.py")
        self.gui = _doc("gui.py")

    def test_config_doc_tu_accounts_json(self):
        self.assertIn('"auto_bag_expand": bool(_party.get("auto_bag_expand", False))', self.cfg)
        self.assertIn('"bag_expand_gold": int(_party.get("bag_expand_gold", 0) or 0)', self.cfg)

    def test_mac_dinh_TAT(self):
        """Mua slot ton nguyen bao/vang cua user -> khong duoc bat san."""
        i = self.cfg.find('"auto_bag_expand"')
        self.assertIn("False", self.cfg[i:i + 80])

    def test_chay_luc_login_va_CHI_khi_tick_va_co_nguong(self):
        i = self.rpd.find("c.tu_mo_rong_tui(")
        self.assertGreater(i, 0, "khong goi luc login")
        khoi = self.rpd[max(0, i - 300):i]
        self.assertIn('pcfg.get("auto_bag_expand")', khoi)
        self.assertIn('int(pcfg.get("bag_expand_gold", 0) or 0) > 0', khoi)

    def test_gui_luu_ca_hai_khoa(self):
        self.assertEqual(self.gui.count('"auto_bag_expand": bool(self.auto_bag_expand_var.get())'), 2,
                         "thieu mot trong hai cho luu (party rieng / ap cho tat ca)")
        self.assertEqual(self.gui.count('"bag_expand_gold": _parse_int('), 2)

    def test_o_tick_nam_TRUOC_tu_ban_noi_dat(self):
        i_mr = self.gui.find('text="Tự mở rộng túi đồ đến"')
        i_nd = self.gui.find('text="Tự bán Nồi đất"')
        self.assertGreater(i_mr, 0)
        self.assertLess(i_mr, i_nd, "o tick phai nam DAU TIEN")


class TestAPK(unittest.TestCase):
    def _kt(self, ten):
        with io.open(os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot",
                                  "android", ten), encoding="utf-8") as fh:
            return fh.read()

    def test_party_co_truong_va_luu_json(self):
        self.assertIn("val autoBagExpand: Boolean = false", self._kt("Party.kt"))
        self.assertIn("val bagExpandGold: Int = 0", self._kt("Party.kt"))
        st = self._kt("PartyStore.kt")
        self.assertIn('o.optBoolean("auto_bag_expand", false)', st)
        self.assertIn('o.optInt("bag_expand_gold", 0)', st)
        self.assertIn('o.put("auto_bag_expand", p.autoBagExpand)', st)
        self.assertIn('o.put("bag_expand_gold", p.bagExpandGold)', st)

    def test_truyen_xuong_python_o_CUOI(self):
        """`setup_party_runtime` nhan theo VI TRI -> chen giua la lech het tham so sau."""
        s = self._kt("BotForegroundService.kt")
        i = s.find("party.loanDauMotTran,")
        self.assertGreater(i, 0)
        self.assertIn("party.autoBagExpand, party.bagExpandGold,", s[i:i + 260])

    def test_python_nhan_tham_so_o_CUOI(self):
        with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            s = fh.read()
        i = s.find("def setup_party_runtime(")
        than = s[i:s.find("):", i)]
        self.assertIn("auto_bag_expand=False", than)
        self.assertIn("bag_expand_gold=0", than)
        self.assertLess(than.find("loandau_mot_tran"), than.find("auto_bag_expand"))

    def test_UI_co_tick_va_o_so_dat_TRUOC_noi_dat(self):
        s = self._kt("MainActivity.kt")
        i_mr = s.find('Text("Tự mở rộng túi đồ đến")')
        i_nd = s.find('Text("Tự bán Nồi đất")')
        self.assertGreater(i_mr, 0)
        self.assertLess(i_mr, i_nd)
        self.assertIn("bagExpandGoldText", s)


if __name__ == "__main__":
    unittest.main()
