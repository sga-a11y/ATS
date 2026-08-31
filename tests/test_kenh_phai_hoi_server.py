"""KENH: game KHONG co lenh hoi "toi dang o kenh nao" -> phai DOI KENH THAT de biet chac.

Tra crack client (30/08):
  - Kenh hien tai cua client = `SceneManager.instanceId`, chi doi khi CO DOI SCENE:
    `S:012-000 <玩家更換場景> ... +區號(2)` -> `RoleController:ChangeScene` -> `SceneManager.ChangeScene`.
  - `S:007-001 <分區列表>` chi liet ke cac kenh + so nguoi, KHONG noi minh dang o kenh nao.
  - `0x0c 0100` la `C:012-001 <換場景完畢>` - goi THONG BAO, KHONG phai cau hoi.
=> Khong ton tai truy van. Coi "server khong tra loi = chua ro" lam TREO ca dong bo kenh
   (30/08 20:01: moi acc `hoi lai kenh: server KHONG tra loi` -> leader thay
   `{'sga002': None, 'sga003': None, ...}` = CHUA sang -> party khong bao gio dong bo).

Cach DUY NHAT xac minh: `switch_channel` (`0x07 0200` -> ack co ket qua; dang o san kenh do thi
server tra result=1 <cung kenh>, van tinh la thanh cong). Nen switch_channel KHONG duoc bo qua
theo gia tri nho san - bo qua la bo dung lan doi kenh that su can:
user kiem chung 30/08: bot hien ca 5 nick party 3 kenh 12, vao game xem la 12/12/12/2/1.
"""
from __future__ import annotations

import os
import re
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient  # noqa: E402


def _doc():
    with open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
        return fh.read()


def _bot(current_channel=None):
    c = GameClient.__new__(GameClient)
    c._label = "test"
    c.running = True
    c.current_channel = current_channel
    c.current_channel_at = time.time()
    return c


class TestKenhThat(unittest.TestCase):
    def test_tra_gia_tri_server_day_den_lan_cuoi(self):
        self.assertEqual(_bot(5).kenh_that(), 5)

    def test_chua_biet_thi_None(self):
        self.assertIsNone(_bot(None).kenh_that())

    def test_KHONG_di_hoi_server(self):
        """Khong co lenh hoi; ep hoi roi coi im lang la 'chua ro' lam treo dong bo kenh."""
        c = _bot(5)
        c.refresh_current_channel = lambda *a, **k: self.fail("khong duoc di hoi server")
        self.assertEqual(c.kenh_that(), 5)

    def test_ghi_chu_neu_ro_ly_do(self):
        s = _doc()
        i = s.find("def kenh_that(")
        than = s[i:s.find("\n    def ", i + 10)]
        self.assertIn("C:012-001", than, "phai ghi ro vi sao khong hoi duoc")
        self.assertIn("switch_channel", than, "phai chi ra nguon dang tin duy nhat")


class TestSwitchChannelKhongBoQua(unittest.TestCase):
    def test_KHONG_con_duong_tat_theo_gia_tri_nho_san(self):
        s = _doc()
        i = s.find("def switch_channel(")
        than = s[i:i + 2200]
        self.assertNotIn("if self.current_channel == channel:", than,
                         "bo qua theo so nho san = bo dung lan doi kenh that su can")
        self.assertNotIn("Da o san kenh", than)

    def test_van_gui_0x07_khi_tuong_da_o_dung_kenh(self):
        """Dang o san kenh do -> server tra result=1, `_on_channel_switch_result` coi la OK."""
        s = _doc()
        i = s.find("def switch_channel(")
        than = s[i:i + 2200]
        i_gui = than.find('self.send(0x07, b"\\x02\\x00"')
        self.assertGreater(i_gui, 0)
        i_for = than.find("for attempt in range(")
        self.assertLess(i_for, i_gui, "phai vao thang vong gui, khong chan truoc")

    def test_ma_1_la_TU_CHOI_vi_TRUNG_khu_dang_o(self):
        """`S:007-002 ket qua 1 = 不可換到同一區` - THONG BAO LOI cua client, khong phai
        "server xac nhan da doi xong". Nhung no suy ra duoc: dich trung khu dang o."""
        s = _doc()
        i = s.find("def _on_channel_switch_result(")
        than = s[i:s.find("\n    def ", i + 10)]
        self.assertIn("elif result == 1:", than)
        self.assertIn("TRUNG khu dang o", than, "phai noi dung ban chat ma 1")

    def test_ma_3_DANG_TO_DOI_phai_roi_party_roi_thu_lai(self):
        """`ket qua 3 = 組隊不可換分區`. Vong luan quan lam party khong bao gio du:
        ket trong party -> khong doi duoc kenh -> khac kenh leader -> khong nhan duoc loi moi ->
        van ket. Truoc day bot `return False` IM LANG nen ca vong nay vo hinh trong log."""
        s = _doc()
        i = s.find("def switch_channel(")
        than = s[i:i + 4200]
        i3 = than.find("if result == 3:")
        self.assertGreater(i3, 0)
        khoi = than[i3:i3 + 900]
        self.assertIn("DANG TO DOI (ma 3)", khoi, "phai LOG ro, khong duoc im lang")
        self.assertIn("self.leave_party(server_bao_dang_o_party=True)", khoi,
                      "khong bat co thi guard 'roster rong' chan luon -> quet kenh vo han "
                      "(party 7, 31/08 14:45-14:55: 67 luot ma 3 ma khong lan nao gui 013-004)")
        self.assertIn("continue", khoi, "phai THU LAI sau khi roi party")

    def test_bang_ma_loi_chep_dung_client(self):
        s = _doc()
        i = s.find("CHANNEL_SWITCH_ERRORS = {")
        khoi = s[max(0, i - 400):i + 400]
        self.assertIn("protocal.lua", khoi, "phai ghi nguon de doi chieu")
        self.assertIn("DANG TO DOI", khoi)


class TestLeaderTuKiemKenh(unittest.TestCase):
    """Member co vong retry nen 60s lai `switch_channel` mot lan -> kenh cua ho luon duoc server
    tra loi. LEADER chi doi kenh MOT LAN luc sync roi thoi -> bi day sang kenh khac ma
    `current_channel` van giu so cu. User log nick vao game xem 30/08: kenh 10 KHONG co nanam,
    trong khi bot bao no o 10, va member thi rui nhau sang 10 het."""

    def _src(self):
        with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            return fh.read()

    def test_co_ham_leader_tu_kiem_kenh(self):
        s = self._src()
        self.assertIn("def _leader_tu_kiem_kenh(", s)
        i = s.find("def _leader_tu_kiem_kenh(")
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertIn("c.switch_channel(int(ch)", than,
                      "khong gui lenh thi khong co cach nao biet leader dang o dau")

    def test_KHONG_chan_viec_moi_party_khi_doi_kenh_hong(self):
        """Doi kenh hong la chuyen rieng; chan luon viec moi la party dung hinh."""
        s = self._src()
        i = s.find("def _leader_tu_kiem_kenh(")
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertIn("van moi, vong sau kiem lai", than)

    def test_cho_ack_NGAN_thoi(self):
        """Log 30/08 21:09: 2 luot x 6s TIMEOUT moi 30s -> chan ca vong gom party."""
        s = self._src()
        i = s.find("def _leader_tu_kiem_kenh(")
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertIn("wait=2.5, retries=1", than)

    def test_goi_TRUOC_khi_moi_party(self):
        s = self._src()
        i = s.find("def _invite_party_participants(")
        than = s[i:i + 1400]
        i_kiem = than.find("_leader_tu_kiem_kenh(")
        i_moi = than.find("invite_train_party_participants(")
        self.assertGreater(i_kiem, 0, "khong kiem kenh leader truoc khi moi")
        self.assertLess(i_kiem, i_moi, "kiem SAU khi moi thi vo nghia")

    def test_co_tiet_che_khong_ban_goi(self):
        """Vong moi party chay moi vai giay; moi luot deu cho ack (toi 6s) la cham gom party."""
        s = self._src()
        i = s.find("def _leader_tu_kiem_kenh(")
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertIn("_leader_kiem_kenh_at", than)
        self.assertIn("< 30.0", than)

    def test_LOG_RO_khi_leader_lech_kenh(self):
        s = self._src()
        i = s.find("def _leader_tu_kiem_kenh(")
        than = s[i:s.find("\ndef ", i + 10)]
        self.assertIn("chu KHONG phai", than, "lech ma khong bao thi lai khong ai biet")


class TestKhongThayThiLamGi(unittest.TestCase):
    """Thay ra roi thi phai LAM GI: coi la LECH CHO -> di theo dung luat cu (khac cho thi ve
    thanh gom lai), chu khong phai chi log roi moi tiep vao hu khong."""

    def _src(self):
        with open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
            return fh.read()

    def _ham(self):
        s = self._src()
        i = s.find("def _party_khong_thay_nhau(")
        self.assertGreater(i, 0, "khong co cho nao xu ly 'cung so ma khong thay nhau'")
        return s, s[i:s.find("\ndef ", i + 10)]

    def test_co_GRACE_khong_ket_luan_voi(self):
        """Vua toi map thi chua kip nhan 0x03 cua nhau - ket luan ngay la pha party oan."""
        _s, than = self._ham()
        self.assertIn("grace=30.0", than)
        self.assertIn("_chua_thay_tu", than)

    def test_thay_lai_thi_XOA_moc(self):
        _s, than = self._ham()
        self.assertIn("_mem.pop(bytes(ent), None)", than, "thay lai ma van giu moc = pha party oan")

    def test_KHONG_xet_khi_lech_map(self):
        """Lech map da co nhanh rieng noi ro ly do - dung de bi nhanh nay nuot mat."""
        _s, than = self._ham()
        self.assertIn('getattr(mc, "current_map", None) != lead_map', than)

    def test_KHONG_VE_THANH_ma_DOI_KENH_MOI(self):
        """User chot 30/08: "ve thanh cai ma me may a, leader chon kenh moi dong bo lai"."""
        s = self._src()
        i = s.find("_party_khong_thay_nhau(c, pidx)")
        self.assertGreater(i, 0)
        khoi = s[i:i + 1800]
        self.assertIn("_party_tai_cho_xu_ly(", khoi)
        self.assertIn("ep_doi_kenh=True", khoi, "khong ep thi picker thay 'cung kenh' roi bo qua")
        self.assertNotIn("_bump_reform", khoi, "ve thanh la SAI rule")
        self.assertNotIn("_do_reform", khoi)

    def test_RA_SAFE_TRUOC_khi_doi_kenh(self):
        """User chot 30/08: "quan trong la bon no phai da o diem an toan, chu dung o diem quai
        thi van loi". `_party_tai_cho_xu_ly` bao ca party ra rally + CHO xac nhan roi moi lam tiep."""
        s = self._src()
        i = s.find("def _party_tai_cho_xu_ly(")
        than = re.sub(r"#.*", "", s[i:i + 5200])
        i_rally = than.find("_cho_ca_party_ve_rally(")
        i_sync = than.find("do_channel_sync()")
        self.assertGreater(i_rally, 0)
        self.assertGreater(i_sync, 0)
        self.assertLess(i_rally, i_sync, "doi kenh TRUOC khi ca party ra safe = van hong")

    def test_picker_TRANH_kenh_hong(self):
        """Chon lai dung cai kenh vua khong thay nhau thi lam lai cung the."""
        s = self._src()
        self.assertIn('"kenh_hong": None,', s)
        self.assertIn('_hong = st.get("kenh_hong")', s)
        self.assertIn("exclude=tuple(sorted(_tru))", s)

    def test_sang_kenh_khac_thi_XOA_co_kenh_hong(self):
        s = self._src()
        self.assertIn('st["kenh_hong"] = None', s, "giu mai se can dan het kenh de chon")


class TestSoKenhKhiMoiParty(unittest.TestCase):
    def test_CO_kiem_kenh_chu_khong_chi_map(self):
        s = _doc()
        i = s.find("def _bot_member_is_on_current_scene(")
        self.assertGreater(i, 0)
        than = s[i:s.find("\n    def ", i + 10)]
        self.assertIn("self.kenh_that()", than, "log ghi 'dung map/kenh' ma khong he kiem kenh")
        self.assertIn("peer.kenh_that()", than)
        self.assertIn("lech kenh live", than)

    def test_bao_khi_server_CHUA_HE_cho_thay_nguoi_do(self):
        """`0x03 PlayerAppear` chi gui cho nguoi CUNG SCENE + CUNG INSTANCE -> chua thay bao gio
        = gan nhu chac chan khac instance. Log de doi chieu, chua dung lam cong."""
        s = _doc()
        i = s.find("def invite_members(")
        than = s[i:s.find("\n    def ", i + 10)]
        self.assertIn("self.da_thay_tan_mat(e)", than)
        self.assertIn("SERVER CHUA HE cho thay", than)

    def test_KHONG_het_han_theo_THOI_GIAN(self):
        """`0x03` chi ban khi nguoi ta XUAT HIEN trong tam nhin - dung yen canh nhau ca tieng
        cung khong co goi moi. Het han theo thoi gian la ket toi oan ca party dang dung o rally
        (log 30/08 21:09: ca 4 member "lan cuoi thay ... 450s truoc" trong khi dang dung im)."""
        s = _doc()
        i = s.find("def da_thay_tan_mat(")
        than = s[i:s.find("\n    def ", i + 10)]
        self.assertNotIn("THAY_TAN_MAT_MAX_AGE", than, "van het han theo thoi gian")
        self.assertIn("chua co 0x03", than, "chi ket luan khi CHUA HE thay")
        self.assertIn("lan cuoi thay o map", than, "hoac lan cuoi thay o MAP KHAC")

    def test_server_bao_ROI_TAM_NHIN_thi_HUY_co_da_thay(self):
        """`S:001-001 <玩家離線> +玩家ID(8)` la ve con lai cua cap voi `0x03 PlayerAppear`.
        Khong xu ly thi "da thay" khong bao gio bi huy -> bot tuong ho con dung canh minh mai."""
        s = _doc()
        i = s.find('if opcode == 0x01 and len(pkt) >= 17')
        self.assertGreater(i, 0, "khong xu ly S:001-001")
        khoi = s[i:i + 500]
        self.assertIn('pkt[7:9] == b"\\x01\\x00"', khoi)
        self.assertIn('_m["appear_at"] = 0.0', khoi)

    def test_nguoi_khac_doi_scene_thi_HUY_co_da_thay(self):
        """Client Lua lam dung the: `if roleId ~= playerId and sceneId ~= SceneManager.sceneId`."""
        s = _doc()
        i = s.find("NGUOI KHAC doi scene")
        self.assertGreater(i, 0, "chi xu ly 0x0c cho CHINH MINH, bo qua nguoi khac doi map")
        khoi = s[i:i + 700]
        self.assertIn('ent != self.self_entity', khoi)
        self.assertIn('_m["appear_at"] = 0.0', khoi)

    def test_da_thay_tan_mat_KHONG_dung_co_nearby(self):
        """`0x27/0900` (danh sach ten quanh map) cung set `nearby` -> co do khong ket luan duoc."""
        s = _doc()
        i = s.find("def da_thay_tan_mat(")
        self.assertGreater(i, 0)
        than = s[i:s.find("\n    def ", i + 10)]
        self.assertIn('meta.get("appear_at")', than)
        self.assertNotIn('meta.get("nearby")', than)
        j = s.find('if source == "0x03":')
        self.assertGreater(j, 0, "chi 0x03 moi duoc ghi moc appear_at")
        self.assertIn('meta["appear_at"]', s[j:j + 300])

    def test_chua_ro_kenh_thi_KHONG_coi_la_dat(self):
        s = _doc()
        i = s.find("def _bot_member_is_on_current_scene(")
        than = s[i:s.find("\n    def ", i + 10)]
        self.assertIn("chua ro kenh live", than, "khong ro ma van moi = doan mo")


if __name__ == "__main__":
    unittest.main()
