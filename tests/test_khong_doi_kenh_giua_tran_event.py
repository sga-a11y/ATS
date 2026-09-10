"""KHONG DOI KENH khi party dang danh EVENT - doi kenh giua tran = dut ket noi ma 47.

Doi kenh = doi INSTANCE, va no keo theo hai thu chet nguoi giua event:
  - `switch_channel` phai ROI DOI truoc (luat `Team.IsAlone` cua client, `UIServerArea.lua:97`),
  - doi scene thi bot chay `scene_resume` -> gui `C:020-006 <事件下一步>`.
Gui goi EVENT luc server chua giai xong tran = `S:000-000` ma 47 `戰鬥未結束事件先結束`.

Ca that 07/09 (user: "vao tran van vang", "cai nay truoc chay ok ma sao may lam hong no"):

    21:25:49 [thsau] (LEADER) 40NPC: ca party da hoi phuc -> mo tran tiep
    21:25:53 [thsau] SERVER NGAT KET NOI: ma la 47
    21:24:07 [xGAx]  (LEADER) sync kenh: 4/5 acc da sang kenh 41      <- doi kenh GIUA 40NPC

thsau / thmo / tonba / lbumot / xGAx cung dis ma 47 trong 32 giay.

DUNG la loi cua ban sua hom nay: truoc day lenh kenh CHI doc o keepalive (mot cho), sau khi tach
`_nghe_lenh_kenh()` thi no duoc goi o CHIN vong - tan suat doi kenh tang han nen trung vao giua
tran event thuong xuyen hon nhieu. Sua bang cach chan dung cho, KHONG quay lai kieu "chi keepalive
moi nghe lenh" (do la cai lam leader dung mot kenh suot).
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestChanDoiKenhGiuaTranEvent(unittest.TestCase):
    """Ba moc an toan gio nam o `_kenh_doi_duoc_ngay` - MOT nguon cho ca hai duong doi kenh.

    Duong thu hai sinh ra 09/09 (party 3): dieu phoi TU GUI lenh doi kenh thay vi cho acc di
    ngang qua diem nghe. Neu moi duong tu kiem an toan mot kieu thi som muon lech nhau, va cai
    lech do la dut ket noi ma 47 - nen ca hai deu goi chung ham nay.
    """

    def setUp(self):
        s = _src()
        i = s.find("def _kenh_doi_duoc_ngay(c, st):")
        self.assertGreater(i, 0)
        j = s.find("\ndef ", i + 10)
        self.than = s[i:j]
        # Ca hai duong gui lenh deu phai di qua ham tren, khong duong nao tu kiem lay.
        for _ham, _het in (("def _nghe_lenh_kenh():", "\n    has_leader ="),
                           ("def _dieu_phoi_thi_hanh_kenh(", "\ndef _dieu_phoi_chot_kenh")):
            a = s.find(_ham)
            self.assertGreater(a, 0, _ham)
            b = s.find(_het, a)
            self.assertIn("_kenh_doi_duoc_ngay(", s[a:b], _ham)

    def test_chan_khi_event_battle_dang_chay(self):
        self.assertIn('st.get("event_battle_active")', self.than,
                      "doi kenh giua tran event -> ma 47")
        i = self.than.find('st.get("event_battle_active")')
        self.assertIn("return False", self.than[i:i + 120])

    def test_chan_TRUOC_khi_gui_lenh_doi(self):
        s = _src()
        for _ham, _het in (("def _nghe_lenh_kenh():", "\n    has_leader ="),
                           ("def _dieu_phoi_thi_hanh_kenh(", "\ndef _dieu_phoi_chot_kenh")):
            a = s.find(_ham)
            khoi = s[a:s.find(_het, a)]
            i_chan = khoi.find("_kenh_doi_duoc_ngay(")
            i_gui = khoi.find("switch_channel(")
            if i_gui < 0:      # duong dieu phoi gui trong thread rieng
                i_gui = khoi.find("threading.Thread(")
            self.assertGreater(i_gui, 0, _ham)
            self.assertLess(i_chan, i_gui, _ham)

    def test_xet_ca_state_in_battle(self):
        """`in_combat` la idle-based nen NGAY SAU khi tran vua mo no con False."""
        self.assertIn('getattr(c.state, "in_battle", False)', self.than)

    def test_xet_ca_grace_ket_tran(self):
        """Server con dang giai tran sau `0x14 sub0700` - gui luc do van dinh ma 47."""
        self.assertIn("_in_battle_end_grace()", self.than)

    def test_VAN_giu_in_combat(self):
        self.assertIn("c.in_combat()", self.than)


class TestDangCoDoiThiThoiDoiKenh(unittest.TestCase):
    """User chot 07/09: "du pt va di danh roi van di doi kenh tiep, m co can code ngu the ko".

    Doi kenh BAT BUOC phai roi doi truoc (luat `Team.IsAlone`), ma DOI TRUONG roi la server GIAI
    TAN CA DOI. Nen ra lenh doi kenh luc dang co doi = tu tay pha cai vua gom. Thu tu dung: gom
    kenh TRUOC, moi party SAU.

    Vong lap that party 52 (07/09) - 38 phut duoc 14 tran, quay qua lai bai train <-> Cu Loc:
        23:37:27 DOI chua du (qv804=0 qv808=4 qv809=4 qv810=4 qv811=4)
    `qv804` la LEADER, roster = 0 vi no vua `leave_party()` DE DOI KENH. Bon member con thay `4`
    chi vi chua kip nhan goi cap nhat - do la so CU. -> `_thieu_doi` bao thieu -> lap lai party ->
    chot kenh -> roi doi -> ... gen 130 -> 137 trong hai phut."""

    def setUp(self):
        s = _src()
        i = s.find("DANG CO DOI (du la do dang) -> THOI DOI KENH")
        self.assertGreater(i, 0, "dieu phoi van ra lenh doi kenh khi dang co doi")
        # cat den HET nhanh (dong `return None` cua no), khong cat theo so ky tu: chu thich trong
        # khoi dai ra la cua so co dinh truot mat phan dieu kien.
        j = s.find("return None", s.find("_co_party = any(", i))
        self.assertGreater(j, i)
        self.khoi = s[i:j + 20]

    def test_chan_khi_CO_acc_nao_dang_o_doi(self):
        """Khong doi MOI acc phai thay du: acc vua roi doi co roster 0 trong vai giay, va acc chua
        nhan goi cap nhat thi giu so CU - ca hai deu khong dang tin. Chi can CON AI o trong doi la
        du de biet "dang co doi"."""
        self.assertIn('len(getattr(_c, "party_members", None) or ()) > 0', self.khoi)

    def test_XOA_luon_kenh_dich_dang_treo(self):
        """Con `kenh_dich` cu thi acc van tu chuyen o vong sau -> van pha party."""
        self.assertIn('st["kenh_dich"] = None', self.khoi)

    def test_DOI_DO_DANG_va_KHONG_ai_dang_doi_kenh_thi_VAN_PHAI_GOM(self):
        """Guard nay chi duoc im khi doi DA DU, hoac khi co acc dang DO VIEC doi kenh (ca party 52).

        Party do dang ma khong ai dang doi kenh = PARTY HONG -> L0 bat gom lai bang duoc, khong
        duoc lay "co doi" lam co de dung im.

        Ca that 09/09 party 1 (user: "p1"): chihao + sieugaaa vao duoc doi (roster 1), ba acc kia
        ket kenh khac -> co `_co_party` bat -> dieu phoi IM 35 PHUT:
            01:45:51 [party 1] DANG CO DOI (brubb46677=0 chihao188=1 minhminhmq=0 sieugaaa=1
                               tuyetdo=0) -> thoi lenh doi kenh (kenh_dich 52)
            02:20:51 [xGAx] (LEADER) chua moi 3 member: ['lech kenh live 52!=12', ...]
        """
        self.assertIn("_thieu_doi(pidx, song)", self.khoi,
                      "khong xet doi da du chua -> party 2/5 cung bi coi la 'dang co doi'")
        self.assertIn("_dang_doi_kenh(song)", self.khoi,
                      "khong loai tru ca 'vua leave_party de doi kenh' -> tai phat bug party 52")

    def test_chan_TRUOC_khi_chot_kenh(self):
        s = _src()
        i = s.find("DANG CO DOI (du la do dang) -> THOI DOI KENH")
        j = s.find("hong, _ma3, _ma2 = _doc_ket_qua_doi_kenh(song)", i)
        self.assertGreater(j, i, "chan phai nam TRUOC phan chot kenh")

    def test_KHONG_dung_so_nho_current_channel_de_quyet(self):
        """`current_channel` la so bot tu nho va no SAI duoc - roster moi la su that."""
        self.assertNotIn("current_channel", self.khoi)


class TestKhongQuayLaiKieuCu(unittest.TestCase):
    """Chan dung cho, KHONG duoc quay lai "chi keepalive moi nghe lenh" - do la cai lam leader
    dung mot kenh suot trong khi member da sang kenh dich (party 1, 20:39-20:42)."""

    def test_van_goi_o_nhieu_vong(self):
        s = _src()
        n = s.count("_nghe_lenh_kenh()")
        self.assertGreaterEqual(n, 5, "lenh kenh lai chi doc o mot cho -> leader diec nhu cu")


if __name__ == "__main__":
    unittest.main()
