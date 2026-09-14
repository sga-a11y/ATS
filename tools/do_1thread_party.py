"""DO: mot LUONG QUYET DINH cho ca party co kip 5 acc cung danh tran khong?

Cau hoi nay chan duong huong "1 thread quyet dinh / party" (user 14/09). Neu khong kip thi ca
huong sap, nen do TRUOC khi viet mot dong nao.

Do hai thu:
  1. CHI PHI CPU cua mot quyet dinh danh (`combat.decide_char` / `decide_pet`) - phan nang nhat
     trong mot luot.
  2. So sanh voi NGAN SACH: bot tu cho `submit_delay` giay truoc khi gui lenh, va 5 acc cung
     party nhan luot gan nhu dong thoi -> luong party phai lam 5 quyet dinh trong ngan sach do.

Chay:  python tools/do_1thread_party.py
"""
from __future__ import annotations

import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.disable(logging.CRITICAL)   # log trong luc do lam nhieu ket qua

from bot import combat, config
from bot.state import BattleState, Unit


def _dung_state():
    """Tran 5v5 day du: ta 5 slot (char+pet), dich 5 slot - kich co that cua party train."""
    st = BattleState()
    st.my_atype = 2
    st.in_battle = True
    st.party_idx = 0
    st.char = Unit(); st.char.hp, st.char.hp_max = 900, 1000
    st.char.sp, st.char.sp_max = 300, 400
    st.pet = Unit(); st.pet.hp, st.pet.hp_max = 800, 900
    st.pet.sp, st.pet.sp_max = 250, 400
    st.skills_char = [0x2711, 0x2712, 0x2713, 0x36b1, 0x36c7]
    st.skills_pet = [0x32d1, 0x32d2, 0x32d5]
    # DICH: 5 quai (`enemy_slots` + `enemy_hp` - dung ten truong that cua BattleState).
    st.enemy_slots = [0, 1, 2, 3, 4]
    st.enemy_hp = {i: (120 if i == 2 else 1400) for i in range(5)}
    st.enemy_names = {"Quai Thu", "Son Tac"}
    st.enemy_pos_names = {i: {"Quai Thu"} for i in range(5)}
    st.mobs = [1400] * 5
    # DONG MINH: 4 member khac, moi dua char(b1=3) + pet(b1=2). Mot dua sap chet -> kich duong
    # chon skill ho tro / hoi sinh (duong DAI nhat cua ham quyet dinh).
    for i in range(5):
        for b1 in (3, 2):
            u = Unit("ally")
            u.hp, u.hp_max = (80 if i == 1 else 900), 1000
            u.sp, u.sp_max = 120, 400
            st.allies[(b1, i)] = u
            st.ally_hpmax[(b1, i)] = 1000
            st.ally_spmax[(b1, i)] = 400
    return st


def _options():
    """`available` tu goi 0x35: (atype, target) duoc phep danh."""
    return [(2, (0, i)) for i in range(5)]


def do_mot_quyet_dinh(lan=400):
    st = _dung_state()
    opts = _options()
    # ham lam nong (import lazy, cache noi bo)
    # KIEM TRUOC: ham phai ra quyet dinh THAT. State dung thieu truong -> ham tra som -> do ra
    # mot con so dep nhung VO NGHIA (da dinh mot lan: `st.enemies` khong ton tai, try/except nuot).
    _dc, _dp = combat.decide_char(st, opts), combat.decide_pet(st, opts)
    if _dc is None or _dp is None:
        return None, "decide tra None -> state dung sai, so do se vo nghia"
    for _ in range(20):
        combat.decide_char(st, opts)
        combat.decide_pet(st, opts)
    mau = []
    for _ in range(lan):
        t0 = time.perf_counter()
        combat.decide_char(st, opts)
        combat.decide_pet(st, opts)
        mau.append((time.perf_counter() - t0) * 1000.0)
    mau.sort()
    return mau, None


def main():
    print("=" * 72)
    print("DO: mot luong quyet dinh / party co kip 5 acc cung danh khong")
    print("=" * 72)

    mau, loi = do_mot_quyet_dinh()
    if loi:
        print("KHONG DO DUOC:", loi)
        return 1

    tb = statistics.mean(mau)
    p50, p95, p99 = mau[len(mau)//2], mau[int(len(mau)*0.95)], mau[int(len(mau)*0.99)]
    print()
    print("1) CHI PHI MOT QUYET DINH (char + pet), %d mau:" % len(mau))
    print("   trung binh %.3f ms | p50 %.3f | p95 %.3f | p99 %.3f | max %.3f"
          % (tb, p50, p95, p99, mau[-1]))

    n_acc = 5
    dinh = p99 * n_acc
    ngan_sach = 500.0        # submit_delay = 0.5s (bot TU cho tung nay truoc khi gui)
    print()
    print("2) DINH: %d acc cung party nhan luot DONG THOI" % n_acc)
    print("   %d x p99 = %.1f ms" % (n_acc, dinh))
    print("   ngan sach (submit_delay) = %.0f ms" % ngan_sach)
    print("   -> dung %.2f%% ngan sach" % (100.0 * dinh / ngan_sach))

    print()
    print("3) TAI LIEN TUC (do tu log that: 26.4 luot/giay toan he / 54 party):")
    luot_giay_party = 26.4 / 54
    tai = luot_giay_party * tb / 1000.0
    print("   %.2f luot/giay/party x %.3f ms = %.4f%% mot loi CPU" % (
        luot_giay_party, tb, tai * 100))

    print()
    print("KET LUAN:")
    if dinh < ngan_sach * 0.5:
        print("  KIP. Dinh %.1f ms < mot nua ngan sach %.0f ms." % (dinh, ngan_sach))
        print("  Nut co chai KHONG phai quyet dinh danh - no la I/O + GIL giua cac party.")
    elif dinh < ngan_sach:
        print("  KIP NHUNG SAT: %.1f / %.0f ms." % (dinh, ngan_sach))
    else:
        print("  KHONG KIP: %.1f ms > ngan sach %.0f ms -> huong 1-thread/party SAP." % (
            dinh, ngan_sach))
    return 0


if __name__ == "__main__":
    sys.exit(main())
