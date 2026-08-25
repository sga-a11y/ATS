"""Tui do trong GUI phai sap GIONG CLIENT GAME, khong phai theo so o.

Client: `Item.GetBagByCategory` (_lua_dec/Logic/Item.lua:364) goi `table.sort(bagCategory,
Item.Sort)`, va `Item.Sort` (Item.lua:369) so sanh:
    sort ASC  ->  neu bang thi  Id ASC
voi `sort` = truong 排序 cua ItemData (--[45]), luu thanh "st" trong items_gamedata.json.
"""
from __future__ import annotations

import json
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# gui -> run_party_digioi doc sys.argv[1] lam so PHUT ngay luc import; ten module cua unittest
# nam o do se lam vo int(). Che argv trong luc import roi tra lai nguyen trang.
_argv = sys.argv
sys.argv = [_argv[0]]
try:
    import gui  # noqa: E402
finally:
    sys.argv = _argv


def _bag(slots):
    """Stub du de goi BagDialog._rows - khong can dung Tk."""
    st = types.SimpleNamespace()
    st.c = types.SimpleNamespace(bag_slots=dict(slots))
    st._tab = gui._BAG.ALL
    st._items_db = gui._load_json("items_gamedata.json")
    st._item = lambda tid: gui.BagDialog._item(st, tid)
    return [(slot, tid) for slot, tid, _cnt, _d in gui.BagDialog._rows(st)]


class TestThuTuTuiDo(unittest.TestCase):
    def test_sap_theo_sort_chu_khong_theo_slot(self):
        # 3 mon co `sort` 106 / 5 / 11 -> thu tu client NGUOC voi thu tu o.
        got = _bag({1: (0x69ab, 5), 2: (0xb22c, 1), 3: (0x799d, 2)})
        self.assertEqual([t for _s, t in got], [0xb22c, 0x799d, 0x69ab])

    def test_cung_sort_thi_theo_id(self):
        """Hai mon cung `sort` (=5) -> client so tiep theo Id tang dan."""
        db = gui._load_json("items_gamedata.json")
        cung = [int(k, 16) for k, v in db.items()
                if k.startswith("0x") and v.get("st") == 5][:2]
        self.assertEqual(len(cung), 2, "khong tim du 2 mon cung sort de kiem")
        a, b = max(cung), min(cung)          # nap o SAI thu tu id
        got = _bag({1: (a, 1), 2: (b, 1)})
        self.assertEqual([t for _s, t in got], [b, a])

    def test_cung_id_hai_o_thi_theo_slot(self):
        """Client de tuy y (table.sort khong on dinh) - minh chot theo slot cho on dinh."""
        got = _bag({7: (0x69ab, 1), 3: (0x69ab, 1)})
        self.assertEqual([s for s, _t in got], [3, 7])

    def test_item_thieu_gamedata_thi_xuong_cuoi(self):
        """Khong co "st" -> phai xuong CUOI, khong duoc nhay len dau."""
        la = 0xfffe
        self.assertNotIn("0x%04x" % la, gui._load_json("items_gamedata.json"))
        got = _bag({1: (la, 1), 2: (0x69ab, 1)})
        self.assertEqual([t for _s, t in got], [0x69ab, la])


class TestBangDuLieu(unittest.TestCase):
    def test_items_gamedata_co_truong_st(self):
        with open(os.path.join(ROOT, "items_gamedata.json"), encoding="utf-8") as fh:
            g = json.load(fh)
        co = sum(1 for v in g.values() if isinstance(v, dict) and "st" in v)
        self.assertGreater(co, 25000, "thieu truong sort -> tui do lai bay sai thu tu")

    def test_st_nam_trong_dai_hop_le(self):
        with open(os.path.join(ROOT, "items_gamedata.json"), encoding="utf-8") as fh:
            g = json.load(fh)
        for k, v in g.items():
            if isinstance(v, dict) and "st" in v:
                self.assertTrue(1 <= v["st"] <= 254, "%s co st=%s" % (k, v["st"]))


if __name__ == "__main__":
    unittest.main()
