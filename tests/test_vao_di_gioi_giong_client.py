"""VAO DI GIOI: roi to doi truoc, va DOC ma ly do cua server thay vi doan.

Client `UITeleport.OnClick_LimitFightArea` (`_lua_dec/UI/UITeleport.lua:501`) chan TRUOC khi gui:

    if Role.player.war ~= EWar.None then ... return true; end      -- dang danh
    if not Team.IsAlone(Role.playerId) then ... return true; end   -- DANG TO DOI
    Network.Send(97, 1, sendBuffer);                               -- C:097-001 <進入限時副本>

Va server tra ly do ro rang - `protocal.lua:14111`:

    S:097-001 <進入結果> +結果(1)
      0 成功 | 1 等級不足 | 2 時間已滿 | 3 戰鬥中 | 4 事件中 | 5 組隊中 | 6 已在該場景

Bot khong doc goi nay (`grep "opcode == 0x61"` ra rong) nen ban 12 lan roi DOAN. Ca that 07/09
party 17, hai dong lien nhau tu to cao:

    00:37:20 [chutam] SOAT LAI thay CON 120 phut DG (server: da dung 0/120)
    00:38:31 [chutam] VAO DI GIOI THAT BAI sau 12 lan -> nhieu kha nang HET GIO DI GIOI hom nay

Con nguyen 120/120 phut. That ra no la `(member)` - ma 5 DANG TO DOI. Doan sai -> danh dau "xong
DG" -> ca party ket cheo:

    01:04:05 [chutam] xong DG, DUNG YEN cho party (1/5)
    01:04:00 [chusau] (LEADER) CHO ca party ve Tuong Duong (1/5)
    01:03:29 [chusau] (LEADER) chu708 KET 91s khong ve duoc Tuong Duong -> EP RELOGIN de cuu party
    01:04:19 [chubay] Di Gioi con lai: 1h20m (da o 39 phut)

Cung mot goc voi bug teleport (tests/test_tele_phai_roi_doi_truoc.py): ca hai deu la luat
`Team.IsAlone` cua client ma bot chua chep.
"""
from __future__ import annotations

import io
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import client as C          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def _than(ten):
    s = _src("bot", "client.py")
    i = s.find("    def %s(" % ten)
    assert i > 0, ten
    j = s.find("\n    def ", i + 10)
    return s[i:j if j > 0 else len(s)]


class _Gia:
    """Ban sao toi thieu cua GameClient cho enter_di_gioi()."""

    _label = "gia"
    di_gioi_level = 2
    DI_GIOI_LEVELS = [10, 25, 40, 55, 70, 85, 100, 110, 120, 130, 140, 150, 160, 170, 180]

    def __init__(self, members=()):
        self.party_members = list(members)
        self.da_roi_doi = 0
        self.da_gui = []
        self.pos = (0, 0)
        self._dg_enter_result = None
        self._dg_enter_event = threading.Event()

    def leave_party(self):
        self.da_roi_doi += 1
        self.party_members = []

    def send(self, opcode, payload):
        self.da_gui.append((opcode, payload, self.da_roi_doi))


def _enter(c):
    from unittest import mock
    from bot import client as C
    with mock.patch.object(C.time, "sleep", lambda *_a, **_k: None):
        return C.GameClient.enter_di_gioi(c)


class TestRoiDoiTruocKhiVaoDG(unittest.TestCase):
    def test_dang_to_doi_thi_ROI_DOI_roi_moi_gui(self):
        c = _Gia([b"\x01\x02\x03\x04", b"\x05\x06\x07\x08"])
        _enter(c)
        self.assertEqual(c.da_roi_doi, 1)
        self.assertTrue(c.da_gui)
        self.assertTrue(all(g[2] == 1 for g in c.da_gui),
                        "moi goi vao DG phai gui SAU khi da roi doi")

    def test_khong_o_doi_thi_KHONG_goi_roi_doi(self):
        c = _Gia([])
        _enter(c)
        self.assertEqual(c.da_roi_doi, 0)
        self.assertTrue(c.da_gui)

    def test_xoa_ma_cu_truoc_moi_lan_thu(self):
        """Con giu ma cua lan truoc thi `enter_di_gioi_safe` doc nham ma cu roi dung han."""
        c = _Gia([])
        c._dg_enter_result = 2
        _enter(c)
        self.assertIsNone(c._dg_enter_result)


class TestDocMaCuaServer(unittest.TestCase):
    def test_co_doc_S097_001(self):
        s = _src("bot", "client.py")
        self.assertIn("opcode == 0x61", s, "van chua doc S:097-001 -> lai di doan")

    def test_du_bay_ma(self):
        d = _than("_dispatch") + _src("bot", "client.py")
        i = _src("bot", "client.py").find("_dg_enter_result = pkt[9]")
        self.assertGreater(i, 0)
        khoi = _src("bot", "client.py")[i:i + 900]
        for ma, chu in ((1, "CAP KHONG DU"), (2, "HET GIO"), (3, "DANG CHIEN DAU"),
                        (4, "SU KIEN"), (5, "DANG TO DOI"), (6, "DA O TRONG DI GIOI")):
            self.assertIn(chu, khoi, "thieu ma %d" % ma)

    def test_KHONG_con_doan_het_gio(self):
        """Cau `nhieu kha nang HET GIO` chinh la cho da danh dau sai acc con 120/120 phut."""
        t = _than("enter_di_gioi_safe")
        self.assertNotIn("nhieu kha nang", t, "van con doan thay vi doc ma server")

    def test_chi_ma_1_va_2_moi_dung_han(self):
        """3/4/5 la tam thoi - dung han o day la bo phi luot DG con nguyen gio."""
        t = _than("enter_di_gioi_safe")
        self.assertIn("if ma in (1, 2):", t)
        self.assertIn("ma = self._dg_enter_result", t)


class TestKhongBanDON(unittest.TestCase):
    """CHO server tra loi roi moi ban lai - khong ngu mot nhip roi ban bat ke da dap chua.

    Ca that 15/09: bo cua hoan viec vat lam 40 acc cay pho ban don dung luc 65 acc dang vao DG.
    Server cham lai (do duoc: [trumuoi] gui 00:31:40, server DONG Y 00:32:06 - tre 26 GIAY), ma
    vong cu chi ngu 3s roi ban tiep -> moi acc ban 24 goi thay vi 1, cang ban server cang cham:
        dot 10:14-10:18 (server ranh) : 68 acc, 349 goi,  1 acc that bai
        dot 00:29-00:32 (server tai)  : 65 acc, 629 goi, 26 acc that bai
    Ca party.log truoc do chi 2 lan `VAO DI GIOI THAT BAI`; rieng 6 phut do la 264 lan. Cac dong
    `DA O TRONG DI GIOI (ma 6)` (762 lan) chinh la tieng vong cua chinh nhung goi thua do.
    """

    def test_co_CHO_goi_tra_loi(self):
        t = _than("enter_di_gioi_safe")
        self.assertIn("self._dg_enter_event.wait(", t,
                      "van ban lai mu, khong cho S:097-001")

    def test_server_im_thi_GIAN_RA_chu_khong_ban_tiep(self):
        t = _than("enter_di_gioi_safe")
        i = t.find("_dg_enter_event.wait(")
        self.assertGreater(i, 0)
        khoi = t[i:i + 700]
        self.assertIn("DG_GIAN_KHI_IM_SEC", khoi, "server im ma van ban ngay -> lam nghen nang hon")
        self.assertIn("continue", khoi)

    def test_han_cho_du_dai_cho_luc_server_tai(self):
        """Do that: tre toi 26 giay. Han cho phai DAI hon moc do, khong thi lai ban thua."""
        self.assertGreaterEqual(C.GameClient.DG_CHO_TRA_LOI_SEC, 26.0)
        self.assertGreater(C.GameClient.DG_GIAN_KHI_IM_SEC, 0)

    def test_xoa_co_truoc_khi_gui(self):
        """Con co cu thi `wait()` ve ngay, doc phai ma cua lan truoc."""
        t = _than("enter_di_gioi")
        self.assertIn("self._dg_enter_event.clear()", t)

    def test_ma_6_coi_nhu_vao_duoc(self):
        """`DA O TRONG DI GIOI` nghia la DA VAO - ban lai nua la vo nghia."""
        t = _than("enter_di_gioi_safe")
        self.assertIn("if ma in (0, 6):", t)


if __name__ == "__main__":
    unittest.main()
