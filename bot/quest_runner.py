"""Mode "Lam quest": chu party lam chuoi quest, cac acc khac trong party ho tro.

Data: quests.json (tools/build_quests.py <- marks.json <- .dat client, xem KNOWLEDGE.md muc
"NHIEM VU (Mark)"). Moi quest: `id` = ma CHAN (mission dang lam trong 0x18 sub06), `bit` = co DA
XONG (`client.mark_flag_get`).

Luat user chot 03/10/2026 (documents/QUEST_CHUYEN_SINH.md):
  - luon chay theo party, user CHI DINH chu party (khong mac dinh slot 0)
  - chu party xong het chuoi -> chi dinh acc DAU TIEN (theo thu tu danh sach) chua xong lam chu
  - ca party xong het -> thoat game
Quest `gainWay = 0` (do duoc tu data ca 8 quest Cu Thu): chi NGUOI KICH HOAT duoc tinh, member
di theo khong xong quest -> bat buoc xoay vong chu party.
"""
from __future__ import annotations

import time

_quests = None


def _load_all():
    global _quests
    if _quests is None:
        try:
            from .client import _load_json_data_file
            _quests = _load_json_data_file("quests.json") or {}
        except Exception:
            _quests = {}
    return _quests


def chuoi(key):
    """Chuoi quest theo key (vd 'cs1_cu_thu'), None = khong co."""
    return _load_all().get(key or "")


def danh_sach_chuoi():
    """[(key, label)] cho GUI."""
    return [(k, v.get("label", k)) for k, v in _load_all().items()]


def da_xong(client, ch):
    """{quest_id: True/False} hoac None khi acc CHUA NHAN co nhiem vu (vua login).

    None phai duoc coi la "chua biet", KHONG phai "chua xong" - doan bua la xoay chu party oan.
    """
    if client is None or not ch:
        return None
    if not getattr(client, "_mark_flags_loaded", False) or not getattr(client, "mark_flags", None):
        return None
    return {int(q["id"]): bool(client.mark_flag_get(int(q["bit"]))) for q in ch["quests"]}


def xong_het(client, ch):
    """True = xong ca chuoi, False = con quest, None = chua biet."""
    st = da_xong(client, ch)
    if st is None:
        return None
    return all(st.values())


def chon_chu_party(thu_tu, trang_thai, chu_hien_tai):
    """Quyet dinh chu party cho mode quest.

    thu_tu      : username theo thu tu danh sach user dat
    trang_thai  : {username: True (xong het) / False (con quest) / None (chua biet)}
    Tra (hanh_dong, username):
      ("giu", chu)   chu hien tai con quest -> lam tiep
      ("cho", None)  chua du thong tin de quyet
      ("doi", u)     chu xong het -> chi dinh u (acc dau tien con quest)
      ("thoat", None) ca party xong het
    """
    cur = trang_thai.get(chu_hien_tai)
    if cur is False:
        return ("giu", chu_hien_tai)
    con = [u for u in thu_tu if u != chu_hien_tai and trang_thai.get(u) is False]
    if con:
        # Chu chua biet (dang login) ma da co acc chac chan con quest: van CHO chu - chua biet
        # khong co nghia la xong.
        return ("cho", None) if cur is None else ("doi", con[0])
    if cur is None or any(trang_thai.get(u) is None for u in thu_tu):
        return ("cho", None)
    return ("thoat", None)


def quest_tiep_theo(client, ch):
    """(quest, step) chu party lam tiep. step = None khi chua nhan quest.

    Uu tien quest DANG LAM (co trong `mission_steps` server gui o 0x18 sub06) - lam tiep tu dung
    buoc server bao. Khong co thi lay quest dau tien chua xong MA DA CO KICH BAN (quest chua capture
    thi khong lam - chon sai ma la server ngat ket noi). (None, None) = khong con gi lam duoc.
    """
    st = da_xong(client, ch)
    if st is None:
        return (None, None)
    steps = getattr(client, "mission_steps", None) or {}
    for q in ch["quests"]:
        if not st.get(int(q["id"])) and int(q["id"]) in steps:
            return (q, int(steps[int(q["id"])]))
    for q in ch["quests"]:
        if not st.get(int(q["id"])) and q.get("kich_ban"):
            return (q, None)
    return (None, None)


def con_thieu_kich_ban(client, ch):
    """Ten cac quest chua xong ma CHUA CO kich ban (cho user capture tiep)."""
    st = da_xong(client, ch) or {}
    return [q["name"] for q in ch["quests"]
            if not st.get(int(q["id"])) and not q.get("kich_ban")]


def _diem(q, step):
    """Diem can toi cho buoc nay: dict scene/x/y/kieu/idx/chon/truoc, None = khong lam duoc."""
    if step is None:
        n = q.get("nhan_tai")
        if not n:
            return None
        # Nhan quest co the qua NPC hoac CUA AN (capture 10328: cua 4 o Dong Bach Son).
        kieu, idx = ("cua", n["cua"]) if n.get("cua") else ("npc", n["npc"])
        return {"scene": n["scene"], "x": n["x"], "y": n["y"], "kieu": kieu, "idx": idx,
                "chon": list(n.get("chon") or ()), "truoc": [], "ten": "nhan quest"}
    s = (q.get("steps") or {}).get(str(step))
    if not s:
        return None
    if s.get("ev_kind") in (1, 2):
        kieu, idx = ("npc" if s["ev_kind"] == 1 else "cua"), s["ev_id"]
    elif s.get("cua"):
        # ev_kind 0 = data chi ghi toa do. Capture 10324: do la CUA SU KIEN AN o dung toa do,
        # so cua lay tu capture (kich ban `cua`).
        kieu, idx = "cua", s["cua"]
    else:
        cua = _cua_cung_cho(q, s)
        if cua is None:
            return None      # chua capture buoc nay
        kieu, idx = "cua", cua
    return {"scene": s["scene"], "x": s["x"], "y": s["y"], "kieu": kieu, "idx": idx,
            "chon": list(s.get("chon") or ()), "truoc": list(s.get("truoc") or ()),
            "ten": "buoc %s" % step}


def _cua_cung_cho(q, s):
    """Buoc GOP (binh thuong server lam luon trong su kien buoc truoc) ma char lo KET o day: dung
    lai cua da co kich ban cua buoc khac CUNG QUEST, CUNG map + toa do.

    [nghi - chua capture] Ca that party 13, 04/10: su kien B1 Phan No Cua Bien (cua 2, Bot Hai) bi
    huy giua chung luc server bao len buoc 2 -> ket buoc 2 (data: ev_kind 0 tai DUNG (2207,282) cua
    B1) -> ca party dung im ~30 phut. Cham cua khong co su kien thi server chi tra `S:020-008`
    kind 0x23 (vo hai, capture 10528); server bat CHON thi `quest_hoi_thoai` dung, khong doan.
    """
    for k, s2 in (q.get("steps") or {}).items():
        if s2 is s or not s2.get("cua"):
            continue
        if (int(s2["scene"]), int(s2["x"]), int(s2["y"])) == (int(s["scene"]), int(s["x"]),
                                                              int(s["y"])):
            return int(s2["cua"])
    return None


def diem_ke_tiep(client, ch):
    """(quest, step, diem) chu party sap lam; diem = None khi khong co gi lam duoc."""
    q, step = quest_tiep_theo(client, ch)
    if q is None:
        return (None, None, None)
    return (q, step, _diem(q, step))


def dang_su_kien(client):
    """Worker chua nhan xong ket qua hoi thoai; khong bao gom di bo/cho retry.

    P40 05/10 00:57:07: het=True nhung worker chua doc -> doi chu huy no truoc khi tra xong.
    quest_hoi_thoai tu xoa _qev trong finally sau khi da chon ket qua.
    """
    return getattr(client, "_qev", None) is not None


def _toi(client, scene, x, y, abort, log):
    """Di bo toi (x, y) TRONG map `scene`. Chuyen map KHONG lam o day: engine da dua ca doi toi map
    nay bang lenh "DI MAP" co san (run_party_digioi `_quest_den_dich`)."""
    label = getattr(client, "_label", "?")
    if int(getattr(client, "current_map", 0) or 0) != int(scene):
        if log is not None:
            log.info("[%s] QUEST: chua o map %s (dang %s) -> cho lenh DI MAP dua doi toi", label,
                     scene, getattr(client, "current_map", None))
        return False
    if abort is not None and abort():
        return False
    arrived = client.navigate_to(int(x), int(y), abort=abort, flee=True)
    return (bool(arrived) and bool(client.running)
            and int(getattr(client, "current_map", 0) or 0) == int(scene)
            and not (abort is not None and abort()))


def lam_buoc(client, q, step, abort=None, log=None, du_party=None):
    """Lam mot buoc; chi thanh cong khi su kien da dong VA server bao len buoc/xong."""
    def dung_di():
        return (not client.running or (abort is not None and abort())
                or (du_party is not None and not du_party()))

    label = getattr(client, "_label", "?")
    d = _diem(q, step)
    if d is None or dung_di():
        return False
    if log is not None:
        log.info("[%s] QUEST: %s %s -> map %s (%s,%s) %s %s", label, q["name"], d["ten"],
                 d["scene"], d["x"], d["y"], d["kieu"], d["idx"])
    if not client._wait_combat_clear(idle=1.0, cap=120.0):
        return False
    if not _toi(client, d["scene"], d["x"], d["y"], dung_di, log):
        return False
    for t in d["truoc"]:
        # Cua su kien rieng cua quest (vd 18506 cua 3, Thai Ho buoc 2) - client that cham truoc NPC.
        if not _toi(client, d["scene"], t["x"], t["y"], dung_di, log) or dung_di():
            return False
        client.quest_kich_hoat("cua", int(t["cua"]))
        kq = client.quest_hoi_thoai(abort=abort, im_lang=15.0)
        if log is not None:
            log.info("[%s] QUEST: cham cua %s truoc -> %s", label, t["cua"], kq)
        if kq != "xong" or not _toi(client, d["scene"], d["x"], d["y"], dung_di, log):
            return False
    qid = int(q["id"])
    truoc = int((getattr(client, "mission_steps", None) or {}).get(qid, 0))
    # Review 04/10: roster co the tut ngay sau khi di toi, truoc nhip engine ke tiep.
    if dung_di():
        return False
    client.quest_kich_hoat(d["kieu"], d["idx"])
    kq = client.quest_hoi_thoai(chon=d["chon"], abort=abort)
    sau = int((getattr(client, "mission_steps", None) or {}).get(qid, 0))
    xong = bool(client.mark_flag_get(int(q["bit"])))
    ok = kq == "xong" and (xong or sau > truoc)
    sig = (qid, step)
    if ok:
        client._quest_khong_tien = None
    elif kq == "xong":
        # mhmmot 05/10 00:50..00:58: 15 lan thoai xong nhung buoc van 0. Khong doan ma chon.
        cu = getattr(client, "_quest_khong_tien", None)
        lan = cu[1] + 1 if cu and cu[0] == sig else 1
        client._quest_khong_tien = (sig, lan)
        if lan == 3 and log is not None:
            log.warning("[%s] QUEST: %s buoc %s - 3 lan hoi thoai xong nhung KHONG LEN BUOC; "
                        "DUNG THU LAI buoc nay. Chua biet dieu kien thieu/ly do server tu choi; "
                        "kiem tra trong game/capture, khoi dong lai acc de thu lai.", label,
                        q["name"], step)
    if log is not None:
        (log.info if ok else log.warning)(
            "[%s] QUEST: %s %s -> su kien %s, buoc %d -> %d%s", label, q["name"], d["ten"], kq,
            truoc, sau, " (XONG QUEST)" if xong else ("" if ok else " -> KHONG LEN BUOC"))
    return ok


def chay(client, key, abort=None, log=None, cho=30.0, du_party=None):
    """Chu party lam 1 nhip quest: lam mot buoc cua quest tiep theo.

    Khong lam duoc gi (chua nhan co, quest con lai chua co kich ban, buoc hong) -> log MOT lan roi
    dung yen `cho` giay. Khong tra ve ngay: viec chay xong ngay ma khong doi gi la engine giao lai
    moi giay (CORE_FLOW: "giao lai N lan lien tiep").
    """
    ch = chuoi(key)
    label = getattr(client, "_label", "?")
    if not ch:
        if log is not None:
            log.warning("[%s] QUEST: khong co chuoi quest '%s' trong quests.json", label, key)
        return False
    q, step = quest_tiep_theo(client, ch)
    if q is not None:
        try:
            client.ensure_pet_role("quest")
        except Exception:
            pass
        sig = (q["id"], step)
        cu = getattr(client, "_quest_khong_tien", None)
        bi_chan = cu is not None and cu[0] == sig and cu[1] >= 3
        if not bi_chan and lam_buoc(client, q, step, abort=abort, log=log, du_party=du_party):
            client._quest_hong = None
            return True
        if getattr(client, "_quest_hong", None) != sig:
            client._quest_hong = sig
            if log is not None:
                log.warning("[%s] QUEST: %s buoc %s CHUA lam duoc -> dung yen %.0fs roi thu lai",
                            label, q["name"], step, cho)
    else:
        thieu = con_thieu_kich_ban(client, ch)
        if thieu and getattr(client, "_quest_log_thieu", None) != tuple(thieu):
            client._quest_log_thieu = tuple(thieu)
            if log is not None:
                log.info("[%s] QUEST: con %d quest CHUA CO KICH BAN (cho capture): %s -> dung yen",
                         label, len(thieu), thieu)
    het = time.time() + float(cho)
    while time.time() < het:
        if abort is not None and abort():
            break
        time.sleep(0.5)
    return True
