"""Va lai cac cap safe-bai QUA XA trong train_maps.json (do fallback cu).

VAN DE: mob_scanner.compute_regions cu, khi 1 bai khong tim duoc safe rieng, roi thang ve
`fallback_safe` = MOT diem duy nhat cho ca map (cho bot dung quan sat, thuong o goc map). Moi bai
hong deu nhan cung diem do -> train o bai do la cu moi lan nghi lai chay ca nua map.

DAU HIEU CHAC CHAN (khong phai doan): safe hop le do ground.nearest_walkable_outside tra ve, bi
rang buoc max_path=600. Duong DI luon >= duong chim bay, nen cap nao co khoang cach chim bay
> 600 thi KHONG THE do ham do tra ve -> chac chan la fallback.
(Nguoc lai, safe TRUNG NHAU chua chac la loi: 2 bai sat nhau tim ra cung 1 diem la hop le - vd
map 23861 trung nhau nhung chi cach 380. Nen tool KHONG dung dau hieu trung.)

CACH VA: dung dung luat moi cua compute_regions - bai hong muon safe cua bai HANG XOM gan nhat
(trong so cac bai CO safe that, tuc cap <= 600). Map nao khong con bai nao co safe that thi BO
QUA, khong tu bia (phai scan lai map do).

Chay:  python tools/fix_far_safes.py           # chi BAO CAO, khong ghi
       python tools/fix_far_safes.py --ghi     # ghi that vao train_maps.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MAX_PATH = 600.0          # phai KHOP voi max_path trong mob_scanner.compute_regions


def _pt(p):
    return (int(p[0]), int(p[1]))


def va_mot_map(safes, mobs, khong_cuu, van_xa):
    """Tra (safes_moi, danh_sach_sua). safes/mobs la list toa do, cung do dai.
    Cac cap xa ma KHONG cai thien duoc se duoc nhet vao `khong_cuu`."""
    cap = list(zip(safes, mobs))
    tot = [s for s, b in cap if math.dist(s, b) <= MAX_PATH]
    if not tot:
        return safes, []                      # khong co moc nao that -> khong bia
    moi, sua = [], []
    for s, b in cap:
        d = math.dist(s, b)
        if d <= MAX_PATH:
            moi.append(s)
            continue
        gan = min(tot, key=lambda p: math.dist(b, p))
        moi.append(gan)
        # "Va duoc" = safe muon duoc GAN HON safe cu. KHONG doi <= MAX_PATH: nguong 600 la rang
        # buoc cua ham TIM safe rieng cho bai do, khong phai dieu kien de muon safe hang xom -
        # muon o 688 van hon han fallback o 2189. Cai nao con > MAX_PATH sau khi va thi bao rieng
        # o "VAN XA" de biet map nao nen scan lai.
        dmoi = math.dist(b, gan)
        if _pt(gan) != _pt(s) and dmoi < d:
            sua.append((_pt(b), _pt(s), round(d), _pt(gan), round(dmoi)))
            if dmoi > MAX_PATH:
                van_xa.append((_pt(b), round(dmoi)))
        else:
            khong_cuu.append((_pt(b), _pt(s), round(d), round(dmoi)))
    return moi, sua


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ghi", action="store_true", help="ghi that (mac dinh chi bao cao)")
    args = ap.parse_args()

    path = os.path.join(ROOT, "train_maps.json")
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    maps = raw.get("maps", raw)

    tong_sua = 0
    bo_qua, khong_cuu, bai_trung, van_xa = [], [], [], []
    for mid, m in sorted(maps.items(), key=lambda kv: int(kv[0])):
        safes = [list(map(int, p)) for p in (m.get("safe") or []) if len(p) == 2]
        mobs = [list(map(int, p)) for p in (m.get("mobs") or []) if len(p) == 2]
        if not mobs or len(safes) != len(mobs):
            continue
        # 2 bai cung 1 cho KHONG phai loi: luat hien hanh la "1 trace (1 con quai) = 1 bai"
        # (324228a), nen 2 con chay CHUNG mot vong tuan tra thi ra bbox y het nhau -> tam y het
        # nhau. Thuc te bai sat nhau rat pho bien: tren 655 bai co 21 cap cach <=300, 4 cap <=100.
        # Chi liet ke cho biet, KHONG dung toi.
        trung = [_pt(b) for b in mobs if mobs.count(b) > 1]
        if trung:
            bai_trung.append((mid, m.get("name", "?"), sorted(set(map(tuple, trung)))))
        kc, vx = [], []
        moi, sua = va_mot_map(safes, mobs, kc, vx)
        if kc:
            khong_cuu.append((mid, m.get("name", "?"), kc))
        if vx:
            van_xa.append((mid, m.get("name", "?"), vx))
        if not sua:
            if not [x for x in zip(safes, mobs) if math.dist(*x) <= MAX_PATH] and any(
                    math.dist(s, b) > MAX_PATH for s, b in zip(safes, mobs)):
                bo_qua.append((mid, m.get("name", "?")))
            if args.ghi:
                m["safe"] = moi
            continue
        tong_sua += len(sua)
        print("\n%s  %s" % (mid, m.get("name", "?")))
        for b, cu, dcu, gan, dmoi in sua:
            print("   bai %-14s  %s (%d)  ->  %s (%d)" % (str(b), str(cu), dcu, str(gan), dmoi))
        if args.ghi:
            m["safe"] = moi

    if khong_cuu:
        print("\nKHONG CUU DUOC bang cach nay (trong map khong con safe that nao gan hon "
              "-> phai SCAN LAI map):")
        for mid, ten, kc in khong_cuu:
            print("   %s  %s" % (mid, ten))
            for b, cu, dcu, dmoi in kc:
                print("      bai %-14s safe %-14s cach %d (tot nhat co the: %d)"
                      % (str(b), str(cu), dcu, dmoi))
    if van_xa:
        print("\nVA ROI NHUNG VAN > %d (nen SCAN LAI map de co safe that):" % MAX_PATH)
        for mid, ten, vx in van_xa:
            print("   %s  %s  ->  %s" % (mid, ten, vx))
    if bai_trung:
        print("\nBAI TRUNG CHO (BINH THUONG, khong phai loi - chi bao de biet):")
        for mid, ten, pts in bai_trung:
            print("   %s  %s  ->  %s" % (mid, ten, pts))
    if bo_qua:
        print("\nBO QUA (khong con bai nao co safe that -> phai SCAN LAI map):")
        for mid, ten in bo_qua:
            print("   %s  %s" % (mid, ten))

    print("\n=> %d cap can va" % tong_sua)
    if args.ghi and tong_sua:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(raw, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        os.replace(tmp, path)
        print("=> DA GHI %s" % path)
    elif tong_sua:
        print("   (chua ghi - them --ghi de ghi that)")


if __name__ == "__main__":
    main()
