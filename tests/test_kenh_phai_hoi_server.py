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


def _than_switch(s):
    """Than DAY DU cua duong doi kenh: `switch_channel` (cua khoa) + `_switch_channel_locked`.

    10/09 tach lam hai ham de ep "mot lenh mot luc" - neo theo cua so ky tu co dinh la truot
    ngay, va truot kieu do bao "code sai" trong khi code khong doi gi.
    """
    i = s.find("def switch_channel(")
    assert i > 0
    k = s.find("def _switch_channel_locked(", i)
    assert k > i
    j = s.find(chr(10) + "    def ", k + 10)
    return s[i:j]


class TestSwitchChannelKhongBoQua(unittest.TestCase):
    def test_KHONG_con_duong_tat_theo_gia_tri_nho_san(self):
        s = _doc()
        than = _than_switch(s)
        self.assertNotIn("if self.current_channel == channel:", than,
                         "bo qua theo so nho san = bo dung lan doi kenh that su can")
        self.assertNotIn("Da o san kenh", than)

    def test_van_gui_0x07_khi_tuong_da_o_dung_kenh(self):
        """Dang o san kenh do -> server tra result=1, `_on_channel_switch_result` coi la OK."""
        s = _doc()
        than = _than_switch(s)
        i_gui = than.find('self.send(0x07, b"\\x02\\x00"')
        self.assertGreater(i_gui, 0)
        i_for = than.find("for attempt in range(")
        self.assertLess(i_for, i_gui, "phai vao thang vong gui, khong chan truoc")

    def test_PHAI_ROI_DOI_truoc_khi_doi_kenh(self):
        """Client game chan thang, KHONG gui goi nao (`_lua_dec/UI/UIServerArea.lua:97`):

            function UIServerArea.OnClick_Area(uiEvent)
              if not Team.IsAlone(Role.playerId) then ShowCenterMessage(...); return; end
              Network.Send(7, 2, sendBuffer);   -- C:007-002 <切換分區>

        Cung mot luat `Team.IsAlone` voi `teleport()` va `enter_di_gioi()` - hai cho do sua 07/09,
        rieng cho nay bo sot. Hau qua (40NPC 07/09): acc doi kenh mai khong duoc, dieu phoi cu chot
        lai kenh dich, leader "chua moi N member vi chua xac nhan live dung map/kenh"."""
        s = _doc()
        than = _than_switch(s)
        i_roi = than.find("self.leave_party()")
        self.assertGreater(i_roi, 0, "doi kenh ma khong roi doi -> server tra ma 3")
        i_for = than.find("for attempt in range(")
        self.assertLess(i_roi, i_for, "phai roi doi TRUOC vong gui")
        self.assertIn("UIServerArea.lua", than, "thieu vien dan crack client")

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
        than = _than_switch(s)
        i3 = than.find("if result == 3:")
        self.assertGreater(i3, 0)
        khoi = than[i3:than.find(chr(10) + "            if result ==", i3 + 5)]
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
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys, inspect
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot
        engine = E.PartyEngine(0, lambda: [("a", NS(), True)], doc_kenh_dich=lambda: 2)
        result = engine._giao_kenh_dich(snapshot([account(so_member=0)]), {"a": E.VIEC_LAP_PARTY})
        self.assertEqual(result, {"a": E.VIEC_DOI_KENH})

    def test_RA_SAFE_TRUOC_khi_doi_kenh(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys, inspect
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot
        with mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.dict(R.account_clients, {"a": NS(pos=(1000, 1000))}, clear=True), \
                mock.patch.object(R, "_map_train_dich", return_value=100), \
                mock.patch.object(R, "_safe_map_dich_engine_moi", return_value=[(20, 30)]):
            self.assertEqual(R._engine_rally_decisions(0, snapshot([account()]), {"a": "doi_kenh"}),
                             {"a": "ve_safe"})

    def test_KHONG_CON_khai_niem_kenh_hong(self):
        """User chot 22/09: instance voi kenh la MOT -> khong co "kenh hong".

        Ban cu: "cung so kenh ma khong thay nhau" -> danh dau kenh do HONG -> picker tranh no ->
        ca party keo nhau sang kenh khac hin. Do la chua trieu chung, va no lam party 3 chay
        long vong 19 phut (22/09). So den chi duoc chua kenh SERVER TU CHOI (ma 2 = khong co khu,
        ma 4 = day) - xem `documents/CORE_FLOW.md` muc "Su that ve game".
        """
        s = self._src()
        self.assertNotIn("kenh_hong", s, "kenh khong hong - dung dung lai co nay")

    def test_picker_van_TRU_kenh_1(self):
        from types import SimpleNamespace as NS
        from unittest import mock
        import sys, inspect
        with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
            import run_party_digioi as R
        from bot import party_engine as E
        from tests.party_engine_scenarios import account, snapshot
        import time
        from tests.test_chon_kenh_it_nguoi_du_cho import _C
        with mock.patch.dict(R._party_state, {}, clear=True), \
                mock.patch.object(R, "_mode_can_lap_doi", return_value=True), \
                mock.patch.object(R, "_party_40npc_ngoai_gio", return_value=False):
            st = R._pstate(0)
            c = _C(1, {1: (0, 20), 2: (5, 20)})
            c._chan_switch_target = 1
            c._chan_switch_result = 4
            c._chan_switch_luc = time.time()
            self.assertEqual(R._engine_chot_kenh(0, st, [("a", c), ("b", _C(2))]), 2)


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
        # Neo tu CHINH nhanh S:001-001, khong neo theo "cach nhanh 0x10 bao nhieu ky tu": giua
        # chung con cac nhanh 0x01 khac (S:001-020/021 chuyen server vo gioi, them 05/09) day no
        # ra xa, cua so co dinh se dut oan trong khi code van dung.
        i = s.find('if opcode == 0x01 and len(pkt) >= 17 and pkt[7:9] == b"\\x01\\x00":')
        self.assertGreater(i, 0, "khong xu ly S:001-001")
        khoi = s[i:i + 500]
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
