"""Exercise the engine's party rule with a controlled runner snapshot."""
from __future__ import annotations

from bot import party_engine


def quyet_party(runner, pidx, st, song, lech_tu=None):
    """Return the old test tuple while using the new single decision path.

    Tests provide `song` explicitly to model server observations. Production obtains it through
    the party engine's `doc_party` callback; both paths use the same snapshot and pure rule.
    """
    anh = runner._chup_anh_cap_party(pidx, st, song, lech_tu)
    viec, ly_do, hu = party_engine.quyet_dinh_cap_party(anh)
    runner._thi_hanh_hieu_ung(pidx, st, song, hu, viec, anh)
    kh = {
        "pha": "train" if hu.doi_pha_train else anh.pha,
        "map": sorted(anh.maps, key=lambda m: -len(anh.maps[m]))[0] if anh.maps else None,
        "kenh": sorted(anh.kenhs)[0] if len(anh.kenhs) == 1 else None,
        "thanh": anh.thanh_cu,
        "viec": viec,
    }
    if hu.chot_tang_gom:
        kh["tang_gom"] = runner._chot_tang_gom(pidx, st, song)
    if hu.chot_2k_xong:
        runner._engine_chot_2k_xong(pidx, st, song)
    return kh, ly_do, hu.lech_tu
