"""A stale per-account waiting report must not trigger party recovery."""
from __future__ import annotations

import pathlib
import unittest

from bot import party_engine as PE

ROOT = pathlib.Path(__file__).resolve().parents[1]


class _Client:
    running = True
    current_map = 12001
    current_channel = 1
    party_members = ("member",)

    def __init__(self, old_report=None):
        self.old_report = old_report


class TestBaoCaoCuKhongQuyetDinh(unittest.TestCase):
    def _decision(self, old_report):
        leader = _Client(old_report)
        member = _Client(old_report)
        engine = PE.PartyEngine(
            0, lambda: [("leader", leader, True), ("member", member, False)],
            can_bao_nhieu=1, map_dich=21001,
        )
        return PE.quyet_dinh(engine.chup())

    def test_bao_cao_cho_cu_khong_doi_lenh(self):
        stale = {"task": "reform: da ve thanh, cho ca party", "phase": "wait", "age": 600}
        self.assertEqual(self._decision(stale), self._decision(None))

    def test_khong_con_watcher_ra_lenh_theo_bao_cao(self):
        src = (ROOT / "run_party_digioi.py").read_text(encoding="utf-8")
        self.assertFalse("def _party_watcher(" in src)
        self.assertFalse("target=_party_watcher" in src)


if __name__ == "__main__":
    unittest.main()
