"""Ap dung cai dat nang cao cho party khac: doi qua event chi ap cho party CUNG nha phat hanh."""
import ast
import os
import types
import unittest
from unittest import mock

_SRC = os.path.join(os.path.dirname(__file__), "..", "gui.py")


def _load():
    """Tach 2 ham can test tu gui.py (khong import gui vi can Tk)."""
    tree = ast.parse(open(_SRC, encoding="utf-8").read())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ConfigDialog")
    fns = [n for n in cls.body if isinstance(n, ast.FunctionDef)
           and n.name in ("_entry_game", "_apply_advanced_to_all")]
    for f in fns:
        f.decorator_list = []
    ns = {"_EVENT_EXCHANGE_KEYS": ("auto_event_exchange", "event_exchange_items",
                                   "event_exchange_sig"),
          "_game_of_server": lambda k: "tsm",
          "messagebox": mock.MagicMock()}
    exec(compile(ast.Module(body=fns, type_ignores=[]), _SRC, "exec"), ns)
    return ns


class _Cfg:
    def __init__(self, game, ev):
        self.game, self.ev, self.applied = game, ev, None

    def _game_key(self):
        return self.game

    def _advanced_settings_data(self):
        return dict(self.ev)

    def apply_advanced_settings(self, d):
        self.applied = d


class ApplyAdvancedEventTest(unittest.TestCase):
    def test_khac_nha_phat_hanh_giu_doi_qua_cu(self):
        ev_tsm = {"auto_event_exchange": False, "event_exchange_items": ["x"], "event_exchange_sig": "t"}
        src = {"cfg": _Cfg("vtc", {}), "preset": {}}
        vtc = {"cfg": _Cfg("vtc", {}), "preset": {}}
        tsm = {"cfg": _Cfg("tsm", ev_tsm), "preset": {}}
        tsm_closed = {"cfg": None, "preset": {"server": "s_tsm", "event_exchange_items": ["y"]}}
        data = {"do_daily": True, "auto_event_exchange": True,
                "event_exchange_items": ["a"], "event_exchange_sig": "v"}
        ns = _load()
        dlg = types.SimpleNamespace(frames=[src, vtc, tsm, tsm_closed], _entry_game=ns["_entry_game"])
        ns["_apply_advanced_to_all"](dlg, src, data)
        self.assertEqual(vtc["cfg"].applied, data)
        self.assertTrue(tsm["cfg"].applied["do_daily"])
        self.assertEqual(tsm["cfg"].applied["event_exchange_items"], ["x"])
        self.assertFalse(tsm["cfg"].applied["auto_event_exchange"])
        self.assertTrue(tsm_closed["preset"]["do_daily"])
        self.assertEqual(tsm_closed["preset"]["event_exchange_items"], ["y"])
        self.assertNotIn("auto_event_exchange", tsm_closed["preset"])


if __name__ == "__main__":
    unittest.main()
