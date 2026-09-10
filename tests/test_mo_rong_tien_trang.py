"""TU MO RONG TIEN TRANG - tick moi trong "Don dep tui do", ngay duoi tick mo rong tui do.

User 10/09: "trong don dep tui do them tick 'tu mo rong tien trang den xxx vang' ngay duoi tick tu
mo rong tui do, khi di cat do vao tien trang thi mo rong luon vi chi mo rong dc khi mo tien trang"
-> "mac dinh la ko tick nhe".

GIAO THUC (doc tu crack client, KHONG doan):
  `UIBank.OnClick_Unlock()` (`_lua_dec/UI/UIBank.lua:333`):
      if currentTag == EUIBankTag.Bank then UISell.Launch(1);        -- TIEN TRANG
      elseif currentTag == EUIBankTag.Storage then UISell.Launch(56); -- kho khac, KHONG dung
  `UISell` (`_lua_dec/Logic/UISell.lua`):
      hoi gia: Network.Send(84, 1, [sellId u16])       -> `0x54 [01 00][sellId 2B]`
      mua:     Network.Send(84, 2, [02][sellId u16])   -> `0x54 [02 00][02][sellId 2B]`
  Y HET duong tui do dang chay, chi khac `sellId` (tui = 3, xem `UIBag.lua:259`).
  So o: `ERoleCount.Bank_1 = 101` (錢莊開啟格數1), song song `Bag_1 = 103`.

CHO DE VO NHAT: `_on_bag_slot` truoc day KHONG XET `sellId` - moi goi `0x54` sub01/sub02 deu ghi
vao `_bag_slot_price`. Mot loai thi khong sao; hai loai dung chung mot o nho thi gia cai nay de len
cai kia -> mua nham hoac dung nham nguong.
"""
from __future__ import annotations

import io
import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import client as C


def _goi(sub: bytes, sell: int, than: bytes) -> bytes:
    """Dung goi S2C 0x54 nhu tren day: [7 byte header][sub 2B][sellId 2B][...]."""
    return b"\x00" * 7 + sub + struct.pack("<H", sell) + than


class _Cli:
    """Chi cac thu duong mo rong dung den."""

    SELL_TUI = C.GameClient.SELL_TUI
    SELL_TIEN_TRANG = C.GameClient.SELL_TIEN_TRANG
    BAG_EXPAND_MAX_LAN = C.GameClient.BAG_EXPAND_MAX_LAN
    _on_bag_slot = C.GameClient._on_bag_slot
    bank_slot_maxed = C.GameClient.bank_slot_maxed
    tu_mo_rong_tien_trang = C.GameClient.tu_mo_rong_tien_trang

    def __init__(self, gia=None, toi_da=False):
        self.running = True
        self._label = "acc"
        self._bag_slot_price = None
        self._bag_slot_price_seq = 0
        self._bag_slot_buy_seq = 0
        self._bag_slot_buy_result = 0
        self._bank_slot_price = None
        self._bank_slot_price_seq = 0
        self._bank_slot_buy_seq = 0
        self._bank_slot_buy_result = 0
        self.role_counts = {101: (30, 30) if toi_da else (10, 60)}
        self._gia = list(gia or [])       # gia tung lan mo, theo thu tu
        self.da_mua = 0

    # -- gia lap server --
    def query_bank_slot_price(self, wait=2.0):
        if not self._gia:
            return None
        return (self._gia[0], 1)

    def buy_bank_slot(self, wait=2.0):
        if self.bank_slot_maxed() or not self._gia:
            return False
        self._gia.pop(0)
        self.da_mua += 1
        return True


class TestPhanBietSellId(unittest.TestCase):
    """Gia tui va gia tien trang KHONG duoc de len nhau."""

    def setUp(self):
        self.c = _Cli()

    def test_goi_TIEN_TRANG_vao_o_tien_trang(self):
        self.c._on_bag_slot(_goi(b"\x01\x00", C.GameClient.SELL_TIEN_TRANG,
                                 b"\x01" + struct.pack("<I", 250)))
        self.assertEqual(self.c._bank_slot_price, (250, 1))
        self.assertIsNone(self.c._bag_slot_price, "gia tien trang de len o cua TUI")

    def test_goi_TUI_vao_o_tui(self):
        self.c._on_bag_slot(_goi(b"\x01\x00", C.GameClient.SELL_TUI,
                                 b"\x01" + struct.pack("<I", 700)))
        self.assertEqual(self.c._bag_slot_price, (700, 1))
        self.assertIsNone(self.c._bank_slot_price)

    def test_sellId_LA_KHONG_PHAI_CUA_BOT_thi_bo_qua(self):
        """56 = tab Storage (kho khac). Nuot no vao la doc nham gia."""
        self.c._on_bag_slot(_goi(b"\x01\x00", 56, b"\x01" + struct.pack("<I", 9)))
        self.assertIsNone(self.c._bag_slot_price)
        self.assertIsNone(self.c._bank_slot_price)
        self.assertEqual(self.c._bank_slot_price_seq, 0)

    def test_ket_qua_mua_cung_tach_theo_sellId(self):
        self.c._on_bag_slot(_goi(b"\x02\x00", C.GameClient.SELL_TIEN_TRANG, b"\x01"))
        self.assertEqual(self.c._bank_slot_buy_result, 1)
        self.assertEqual(self.c._bag_slot_buy_seq, 0, "ket qua tien trang bump seq cua TUI")

    def test_goi_cut_khong_lam_no(self):
        self.c._on_bag_slot(b"\x00" * 7 + b"\x01\x00")
        self.assertIsNone(self.c._bank_slot_price)


class TestNguongDung(unittest.TestCase):
    """Nguong tinh y het tui do: so dien la NGUONG BAO GOM."""

    def setUp(self):
        self._sleep = C.time.sleep
        C.time.sleep = lambda *_a, **_k: None    # vong mua ngu 0.4s/lan -> test cho 12 giay

    def tearDown(self):
        C.time.sleep = self._sleep

    def test_mua_toi_khi_gia_KE_TIEP_vuot_nguong(self):
        c = _Cli(gia=[100, 200, 250, 260, 300])
        self.assertEqual(c.tu_mo_rong_tien_trang(250), 3, "dien 250 thi mua xong lan gia 250")
        self.assertEqual(c.da_mua, 3)

    def test_gia_BANG_nguong_thi_VAN_mua(self):
        c = _Cli(gia=[250, 999])
        self.assertEqual(c.tu_mo_rong_tien_trang(250), 1)

    def test_gia_dau_tien_da_vuot_thi_khong_mua_gi(self):
        c = _Cli(gia=[500])
        self.assertEqual(c.tu_mo_rong_tien_trang(250), 0)

    def test_nguong_0_la_TAT(self):
        """Mac dinh khong tick -> nguong 0 -> tuyet doi khong gui goi nao."""
        c = _Cli(gia=[1, 1, 1])
        self.assertEqual(c.tu_mo_rong_tien_trang(0), 0)
        self.assertEqual(c.da_mua, 0)

    def test_DA_TOI_DA_o_thi_dung(self):
        c = _Cli(gia=[1], toi_da=True)
        self.assertEqual(c.tu_mo_rong_tien_trang(9999), 0)

    def test_khong_hoi_duoc_gia_thi_dung(self):
        c = _Cli(gia=[])
        self.assertEqual(c.tu_mo_rong_tien_trang(9999), 0)

    def test_co_TRAN_so_lan_mua(self):
        """Cau hinh sai (nguong khong lo) khong duoc lam bot mua tron doi."""
        c = _Cli(gia=[1] * 500)
        self.assertLessEqual(c.tu_mo_rong_tien_trang(10 ** 9), C.GameClient.BAG_EXPAND_MAX_LAN)


class TestNoiVaoLuotCatDo(unittest.TestCase):
    """Chi mo duoc luc kho DANG MO -> phai nam trong `cat_do_tien_trang`, SAU khi `bank_open`."""

    def setUp(self):
        with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
            self.cli = fh.read()

    def test_goi_trong_cat_do_tien_trang(self):
        i = self.cli.find("def cat_do_tien_trang(")
        self.assertGreater(i, 0)
        j = self.cli.find("\n    def ", i + 10)
        self.assertIn("tu_mo_rong_tien_trang(", self.cli[i:j])

    def test_goi_SAU_khi_kho_da_mo(self):
        i = self.cli.find("def cat_do_tien_trang(")
        than = self.cli[i:self.cli.find("\n    def ", i + 10)]
        i_mo = than.find('kq["bo_qua"] = "tien trang khong mo"')
        i_goi = than.find("tu_mo_rong_tien_trang(")
        self.assertGreater(i_mo, 0)
        self.assertGreater(i_goi, i_mo, "goi truoc khi xac nhan kho mo = gui goi vo ngu canh")

    def test_loi_mo_rong_KHONG_lam_hong_viec_cat_do(self):
        # Neo vao CHO GOI (`self.tu_mo_rong_tien_trang(`), khong phai dong `def`.
        i = self.cli.find("self.tu_mo_rong_tien_trang(")
        self.assertGreater(i, 0)
        khoi = self.cli[max(0, i - 400):i + 400]
        self.assertIn("except Exception", khoi)
        self.assertIn("van cat do", khoi)

    def test_mac_dinh_TAT(self):
        """User chot: "mac dinh la ko tick nhe"."""
        i = self.cli.find("self.bank_expand_gold = 0")
        self.assertGreater(i, 0, "thuoc tinh phai mac dinh 0 = TAT")


class TestCauHinhXuyenSuot(unittest.TestCase):
    """Tick o GUI -> config -> client. Dut mot mat xich la tick bam khong an gi."""

    def _doc(self, *p):
        with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
            return fh.read()

    def test_gui_co_tick_va_o_so(self):
        g = self._doc("gui.py")
        self.assertIn("Tự mở rộng tiền trang đến", g)
        self.assertIn("auto_bank_expand_var", g)
        self.assertIn('"bank_expand_gold": _parse_int(self.bank_expand_gold_var.get(), 0)', g)

    def test_gui_mac_dinh_KHONG_tick(self):
        g = self._doc("gui.py")
        i = g.find("self.auto_bank_expand_var = tk.BooleanVar(")
        self.assertGreater(i, 0)
        self.assertIn('self._preset.get("auto_bank_expand", False)', g[i:i + 200])

    def test_config_doc_hai_key(self):
        cf = self._doc("bot", "config.py")
        self.assertIn('"auto_bank_expand": bool(_party.get("auto_bank_expand", False))', cf)
        self.assertIn('"bank_expand_gold": int(_party.get("bank_expand_gold", 0) or 0)', cf)

    def test_khong_tick_thi_nguong_ve_0(self):
        r = self._doc("run_party_digioi.py")
        i = r.find("c.bank_expand_gold = ")
        self.assertGreater(i, 0)
        khoi = r[i:i + 300]
        self.assertIn('pcfg.get("auto_bank_expand", False)', khoi,
                      "khong xet tick -> bam nguong la chay du chua tick")

    def test_APK_co_du_mat_xich(self):
        """PC/APK lech la tick tren dien thoai bam khong an gi."""
        J = ("android", "app", "src", "main", "java", "com", "tsbot", "android")
        self.assertIn("val autoBankExpand: Boolean = false", self._doc(*J, "Party.kt"))
        ps = self._doc(*J, "PartyStore.kt")
        self.assertIn('o.optBoolean("auto_bank_expand", false)', ps)
        self.assertIn('o.put("auto_bank_expand", p.autoBankExpand)', ps)
        self.assertIn("party.autoBankExpand, party.bankExpandGold",
                      self._doc(*J, "BotForegroundService.kt"))
        self.assertIn("Tự mở rộng tiền trang đến", self._doc(*J, "MainActivity.kt"))

    def test_setup_party_runtime_nhan_tham_so_moi_O_CUOI(self):
        """Kotlin goi THEO VI TRI - chen vao giua la lech het tham so phia sau."""
        r = self._doc("run_party_digioi.py")
        i = r.find("def setup_party_runtime(")
        chuoi = r[i:r.find("):", i)]
        self.assertIn("auto_bank_expand=False, bank_expand_gold=0", chuoi)
        self.assertLess(chuoi.find("auto_cat_do=False"), chuoi.find("auto_bank_expand=False"))


if __name__ == "__main__":
    unittest.main()
