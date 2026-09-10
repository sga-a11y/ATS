"""CANH GAC: khong con bang ACC TU KHAI o cap party. Bot dieu khien acc thi bot BIET.

User chot 07/09, nhieu lan:
    "bot la nguoi dieu khien acc, thi co cai gi ma ko biet duoc?"
    "acc noi cai lon nua, bot tu thay cac acc dang o dau, acc noi lam cai lon gi nua"
    "may lam on bo het may vu acc bao cao di"

Hai cach luu KHAC HAN nhau:

  SAI - bang cap party:  st["<ten>"][username] = <gia tri>
        Nguoi doc phai CHO du nguoi khai. Acc ban viec khac / vua relogin / ket o vong khac thi
        khong bao gio khai -> dem thieu -> cho mai. Va bang con om STALE qua cac lan relogin.

  DUNG - dau vet tren CHINH CLIENT:  c._<ten> = <gia tri>   roi doc account_clients[u]._<ten>
        Bot dieu khien acc nen no ghi ngay tai luc ra lenh; nguoi doc doc thang, khong cho ai.

Cac bang DA BO (07/09) va thay bang gi:

    reform_arrived        -> current_map            (leader dem ai da ve thanh)
    presync_maps          -> current_map            (ca party co cung map truoc khi sync kenh)
    map_results           -> current_map            (co o train map khong)
    member_maps           -> XOA HAN (khong ai doc, ghi moi vong cho vui)
    event_start_map       -> current_map            (2K: resume hay vao lai)
    char_level_by         -> c.char_level           (du cap vao PB chua)
    rally_done            -> c._rally_gen_da_lam    (da thi hanh lenh gom chua)
    dt_done               -> c._dg_da_xong          (da xong Di Gioi chua)
    ready_members         -> c._san_sang_party      (member xong viec vat dau phien chua)
    o5_done_by            -> c._o5_da_xong          (daily o5 xong chua)
    team_dungeon_done_by  -> c.team_dungeon_remaining(level)

Kem theo do la 6 vong CHO bam vao chung cung bi bo.

Ca that dat nhat - party 1 (07/09), dong log TU MAU THUAN trong chinh no:
    19:09:00 [xGAx] (LEADER) reform: CHO ca party ve Giang Lăng (4/5) -
             THIEU: tuyetdo[map=21011, reform: ve Giang Lăng (dang o map 21836) 2s truoc]
Giang Lang = 21011. `map=21011` doc thang tu client - tuyetdo DA DUNG o Giang Lang. Chi bang khai
bao la chua co ten no, va leader lap lai "THIEU" moi 30 giay.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DA_BO = (
    "reform_arrived", "presync_maps", "map_results", "member_maps", "event_start_map",
    "char_level_by", "rally_done", "dt_done", "ready_members", "o5_done_by",
    "team_dungeon_done_by",
)


def _src(ten="run_party_digioi.py"):
    with io.open(os.path.join(ROOT, ten), encoding="utf-8") as fh:
        return fh.read()


def _code():
    """Chi cac dong CODE - chu thich lich su van duoc phep nhac ten bang cu."""
    return chr(10).join(d for d in _src().splitlines()
                        if d.strip() and not d.strip().startswith("#"))


class TestCacBangDaBo(unittest.TestCase):
    def test_khong_con_dung_lai(self):
        code = _code()
        for ten in DA_BO:
            self.assertNotIn('st["%s"]' % ten, code, ten)
            self.assertNotIn('st.get("%s"' % ten, code, ten)
            self.assertNotIn('st.setdefault("%s"' % ten, code, ten)

    def test_khong_con_khai_bao_trong_state(self):
        code = _code()
        for ten in DA_BO:
            self.assertNotIn('"%s":' % ten, code, ten)


class TestKhongThemBangMoi(unittest.TestCase):
    """Neo CHUNG: cam moi dang `st[...][username] = ...` - do la acc tu khai o cap party."""

    # `reconnecting` la SU KIEN (acc dang relogin), khong phai acc tu khai trang thai cua no;
    # `manual_route_*` la che do TAY, user tu dieu khien tung buoc.
    MIEN = ("reconnecting", "manual_route_source_results", "manual_route_city_arrived",
            "invited", "stop_leader_done")

    def test_khong_co_bang_khai_bao_moi(self):
        xau = []
        pat = re.compile(r'st(?:\.setdefault)?\(?\["?([a-z0-9_]+)"?\]?[^=\n]*\)?\[username\]\s*=')
        for i, d in enumerate(_src().splitlines(), 1):
            t = d.strip()
            if not t or t.startswith("#"):
                continue
            m = pat.search(d)
            if m and m.group(1) not in self.MIEN:
                xau.append("%d: %s" % (i, t[:90]))
        self.assertEqual(xau, [], "acc tu khai o cap party:" + chr(10) + chr(10).join(xau))

    def test_khong_co_add_username_vao_set_cap_party(self):
        xau = []
        pat = re.compile(r'st\["([a-z0-9_]+)"\]\.add\(username\)')
        for i, d in enumerate(_src().splitlines(), 1):
            t = d.strip()
            if not t or t.startswith("#"):
                continue
            m = pat.search(d)
            if m and m.group(1) not in self.MIEN:
                xau.append("%d: %s" % (i, t[:90]))
        self.assertEqual(xau, [], "acc tu ghi ten vao set cap party:" + chr(10) + chr(10).join(xau))


class TestDauVetNamTrenClient(unittest.TestCase):
    """Thay the phai la dau vet tren CHINH CLIENT + co cho DOC THANG."""

    def test_co_ghi_va_co_doc(self):
        code = _code()
        for attr in ("_rally_gen_da_lam", "_dg_da_xong", "_san_sang_party", "_o5_da_xong"):
            self.assertIn(attr, code, "thieu dau vet thay the cho bang cu: " + attr)
            self.assertIn("getattr(", code)

    def test_doc_qua_account_clients(self):
        code = _code()
        for attr in ("_rally_gen_da_lam", "_dg_da_xong", "_san_sang_party", "_o5_da_xong"):
            i = code.find(attr)
            self.assertGreater(i, 0, attr)
        # moi thay the deu phai co it nhat mot cho doc qua account_clients / client object
        self.assertIn("account_clients.get(", code)


if __name__ == "__main__":
    unittest.main()
