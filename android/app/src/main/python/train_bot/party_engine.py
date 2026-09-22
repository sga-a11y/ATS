"""ENGINE PARTY MOI - MOT luong quyet dinh cho ca party (thiet ke: documents/ENGINE_PARTY_MOI.md).

VI SAO CO FILE NAY
------------------
Engine cu cho moi acc mot thread chay kich ban rieng (`run_account`, 5.690 dong). Do trong chinh
ham do: 39 vong CHO, 21 vong KHONG CO HAN, va **14 vong diec voi `reform_gen`**. Moi vong cho phai
TU NHO nghe 4 loai lenh (kenh / reform / rally / cmd) => 84 o phai nho, lap duoc ~11. Moi lan user
bao loi la MOT O TRONG.

Ca de ra file nay - party 11, 15/09 (`luumuoi` treo 64 phut, party ket 22 phut):
    11:25:22 [luumuoi] (member) ca party xong dungeon      <- IM TUYET DOI tu day, 0 dong/64 phut
    12:27:51 [luusau]  (LEADER) -> REFORM party (gen 30)   <- leader lam dung, lan thu 8 lien tiep
    12:27:51 [luusau]  reform: dieu phoi bao GOM -> thoi moi
`do_daily_dungeon()` phai `leave_party()` (PB don bat buoc solo) -> party vo -> `luumuoi` roi vao
vong `while not st["invited"].is_set()`, vong do nghe lenh KENH va `rally_gen` nhung KHONG nghe
`reform_gen` - ma lenh gom map lai di bang `reform_gen`. Ba ben deu "dung luat" nen ket vinh vien.

GOC KHONG PHAI "moi acc mot thread". Goc la: **moi acc tu quyet dinh luc nao thi nghe lenh.**

CACH CHUA
---------
Luong quyet dinh KHONG CO VONG CHO NAO. Moi nhip: doc anh chup trang thai 5 client -> `quyet_dinh()`
(ham THUAN, khong I/O, khong sleep) -> giao viec cho worker. Vi khong chan, moi lenh deu duoc xu ly
o nhip ke tiep - tre toi da mot nhip. Khong ton tai khai niem "vong cho diec".

Viec CHAN (di duong, vao Di Gioi, danh pho ban) chay o worker rieng tung acc va HUY duoc giua chung
=> giu duoc cach ly loi cua engine cu: mot acc treo khong lam dung ca party.

KHONG NOI LUAT NAO trong documents/RULE_DIEU_PHOI.md. Dieu phoi quyet, acc thi hanh (L1); du party
roi lam gi thi lam, party hong thi gom bang duoc (L0).
"""
from __future__ import annotations

import threading
import time

# ---------------------------------------------------------------- viec (lenh cho worker)

VIEC_NGHI = "nghi"                # khong co viec - dung yen
VIEC_VE_MAP = "ve_map"            # di ve map chung (dong bo map)
VIEC_DOI_KENH = "doi_kenh"        # chuyen sang kenh chung
VIEC_LAP_PARTY = "lap_party"      # leader moi, member cho nhan
VIEC_TRAIN = "train"              # du doi, cung cho -> danh
VIEC_VIEC_VAT = "viec_vat"        # PB don / boss the gioi / daily - acc nam han trong client
VIEC_DAILY = "daily"              # NHIEM VU NGAY: PB don (o1) + claim 9 o (keo theo o2 boss, o5 PB doi)
VIEC_LOGIN_CHORE = "login_chore"  # viec vat sau login (PB don, boss TG, nhiem vu ngay, van tieu)
VIEC_DI_GIOI = "di_gioi"          # vao Di Gioi (mode digioi / digioi_train pha DG)
VIEC_RA_SPOT = "ra_spot"          # du party, dung map -> keo ra bai quai
VIEC_PB_DOI = "pb_doi"            # LEADER chay pho ban to doi (lv20/50/80/110)
VIEC_PB_DOI_THEO = "pb_doi_theo"  # member: mo cua nhan loi moi + DUNG YEN cho leader keo vao
VIEC_THOAT = "thoat"              # mode `digioi` thuan: xong DG la THOAT GAME (khong dung im)
VIEC_VE_THANH = "ve_thanh"        # GOM: teleport ve THANH TAP KET (khong phai di bo qua cong)
VIEC_VAO_EVENT = "vao_event"      # mode event: VAO MAP EVENT truoc (chua vao thi chua lap party)
VIEC_DANH_EVENT = "danh_event"    # da vao map event + du party -> LEADER mo vong battle
VIEC_RESYNC = "resync"            # member: ROI PARTY + sync kenh lai NGAY TAI CHO (`resync_gen`)
VIEC_DOI_THUONG = "doi_thuong"    # event xong / ngoai gio -> di doi thuong roi THOAT GAME
VIEC_FC_GOM = "fc_gom"            # 2K lech tang: DI BO ve tang gom (trong thap KHONG teleport duoc)
VIEC_LENH_TAY = "lenh_tay"        # GUI ra lenh (teleport thanh / di map): thi hanh NGAY, truoc moi thu
# 2K leo thap - LEADER lam tung buoc, member dinh party TU THEO (trong thap chi leader di chuyen).
VIEC_2K_DANH = "2k_danh"          # di toi diem quai cua tang roi kich MOT tran
VIEC_2K_LEN_TANG = "2k_len_tang"  # danh het diem + DU PARTY -> di toi cong va qua tang tren

# Buoc ke tiep cua 2K, do `floor_crawl.tinh_buoc()` chot (ten buoc giu giong ham do tra ve).
FC_DANH = "danh"
FC_LEN_TANG = "len_tang"

# Thu tu uu tien, dung y chuoi user chot tu dau:
#   "lech map thi dong bo map / lech kenh thi dong bo kenh / cung kenh cung map thi lap pt /
#    du pt thi chay di train"
THU_TU = (VIEC_LOGIN_CHORE, VIEC_DAILY, VIEC_DI_GIOI, VIEC_VE_MAP, VIEC_DOI_KENH, VIEC_LAP_PARTY,
          VIEC_LENH_TAY,
          VIEC_PB_DOI, VIEC_PB_DOI_THEO, VIEC_VE_THANH, VIEC_VAO_EVENT, VIEC_FC_GOM,
          VIEC_2K_LEN_TANG, VIEC_2K_DANH, VIEC_DANH_EVENT, VIEC_DOI_THUONG, VIEC_RESYNC,
          VIEC_RA_SPOT, VIEC_TRAIN, VIEC_VIEC_VAT, VIEC_THOAT, VIEC_NGHI)

# Viec CHAN - acc dang lam mot trong nhung viec nay thi ENGINE KHONG RA LENH DE LEN, cho no xong.
# `train` / `nghi` tra ve ngay lap tuc nen khong bao gio "ban" lau -> khong nam trong day.
BAN_THI_CHO = (VIEC_VE_MAP, VIEC_VE_THANH, VIEC_DOI_KENH, VIEC_LAP_PARTY, VIEC_RA_SPOT,
               VIEC_DI_GIOI, VIEC_PB_DOI, VIEC_PB_DOI_THEO, VIEC_LOGIN_CHORE, VIEC_VIEC_VAT,
               VIEC_DAILY,
               VIEC_VAO_EVENT, VIEC_DANH_EVENT, VIEC_DOI_THUONG, VIEC_RESYNC, VIEC_FC_GOM,
               VIEC_2K_DANH, VIEC_2K_LEN_TANG, VIEC_LENH_TAY)

# ---------------------------------------------------------------- viec CAP PARTY cua engine cu
#
# `_dieu_phoi_quyet` ra MOT trong nhung viec nay cho CA party. Engine moi chi DICH chung sang viec
# thi hanh, KHONG tu nghi ra chuoi lenh rieng - ban tu viet cua no chi co 4 bac trong khi chuoi
# that co 11 nhanh va 15 phep thu, va moi nhanh thieu la mot loi user phai di tim ho
# (user 16/09: "sao may ko tham khao cai cu da co ma cu thich bia ra cai moi").
DP_GOM = "gom"            # lech map/kenh -> gom ve mot cho
DP_MOI = "moi"            # cung map+kenh, thieu doi -> leader moi
DP_DONG_BO = "dong_bo"    # cung map, lech kenh -> dong bo kenh
DP_DI_TRAIN = "di_train"  # du doi, chua o map train -> di toi map train
DP_RA_QUAI = "ra_quai"    # da o map train, con o safe -> ra diem quai
DP_LAM = "lam"            # khong vuong gi -> lam viec chinh

# viec cap party -> viec cua tung acc
DICH_VIEC = {
    # `gom` KHONG dich thanh viec thi hanh: `_dieu_phoi_thi_hanh` bien no thanh MOT nhat
    # `_bump_reform` (co cooldown 180s), roi ca party ve thanh tap ket theo `reform_gen`.
    # Dich thang thanh `ve_thanh` la giao lai MOI NHIP, bo qua cooldown -> acc bi dap qua dap lai
    # giua thanh va map train, ma moi lan teleport la mot lan `leave_party()` xe party.
    # Ca that 16/09 party 43 (user: "p43 lap pt o Ng thanh"):
    #   22:41:15 roster DU 4/4 tai 12061
    #   22:41:16 roster 0/4        <- lenh `ve_thanh` tele len 12001, tan doi
    #   22:41:18 lai `ve_thanh`, 22:41:20 `ve_thanh`, 22:41:21 `ve_thanh` ...
    DP_GOM: VIEC_NGHI,
    # `dong_bo` KHONG dich thanh viec thi hanh: nguoi gui lenh doi kenh la
    # `_dieu_phoi_thi_hanh_kenh` cua engine cu (dieu phoi TU GUI cho tung acc lech, khong cho acc
    # di ngang qua diem nghe). Engine moi ma cung gui nua la HAI NGUON ra lenh cho mot party.
    DP_DONG_BO: VIEC_NGHI,
    DP_MOI: VIEC_LAP_PARTY,
    DP_DI_TRAIN: VIEC_VE_MAP,
    DP_RA_QUAI: VIEC_RA_SPOT,
    DP_LAM: VIEC_TRAIN,
}


# PHA cua party mode `digioi_train` (giong `st["dt_phase"]` cua engine cu)
PHA_DG = "digioi"        # con gio Di Gioi -> ca party vao DG danh
PHA_TRAIN = "train"      # het gio DG -> ra map thuong gom party + train

# MUA HP/SP giua phien: moi 2 TIENG mot lan (y flow cu `next_buy_hpsp` trong `run_account`).
# Chuyen mua DOI MAP (Trac Quan -> map NPC -> ve lai), nen goi day hon la keo acc ra khoi bai
# train lien tuc; con `buy_hp_sp` thi da TU kiem nguong du tru truoc khi di.
BUY_HPSP_MOI_SEC = 7200.0

# DI GIOI HO PHU: check moi 3 phut trong luc DANG O TRONG DG (y `HO_PHU_CHECK_SEC` cua flow cu).
# `client.use_di_gioi_ho_phu` TU kiem "con < 15 phut moi dung" nen day chi la nhip hoi.
HO_PHU_CHECK_SEC = 180.0

# HAI THANH TRUNG GIAN cua `client.pre_route_town_hop` (Trac Quan / Nghiep Thanh). Ve CHINH mot
# trong hai thanh nay thi khong hop nua - do la them mot lan tele vo ich.
# Chep so o day vi `party_engine` CO Y khong import `client` (engine phai thuan, test duoc thang).
# `tests/test_pre_route_truoc_khi_ve_thanh.py` ep hai noi luon khop nhau.
_PRE_ROUTE_CITY_IDS = frozenset({12001, 12061})
PHA_EVENT = "event"      # mode event (40NPC...): vao map event -> gom party -> danh -> doi thuong


class AnhAcc:
    """ANH CHUP trang thai mot acc tai MOT khoanh khac.

    Vi sao phai chup thay vi doc thang `client` trong luc quyet dinh: engine cu doc map/kenh cua
    tung acc o nhung thoi diem KHAC NHAU nen sinh ra ba thuc tai lech nhau (ca party 11: leader
    "biet" minh o thanh gom, member "biet" minh o bai train, dieu phoi thay 2 map). Chup mot lan
    roi quyet dinh tren anh do => ca party dung chung MOT su that.
    """

    __slots__ = ("username", "la_leader", "song", "map_id", "kenh", "dang_danh",
                 "so_member", "viec_dang_lam", "xong_chore", "xong_daily", "trong_dg", "trong_pb",
                 "con_gio_dg", "dang_ban", "trong_event", "lenh_tay_da_lam")

    def __init__(self, username, la_leader=False, song=True, map_id=None, kenh=None,
                 dang_danh=False, so_member=0, viec_dang_lam=VIEC_NGHI,
                 xong_chore=True, xong_daily=True, trong_dg=False, trong_pb=False,
                 con_gio_dg=False,
                 dang_ban=False,
                 trong_event=False, lenh_tay_da_lam=0):
        self.username = username
        self.la_leader = bool(la_leader)
        self.song = bool(song)
        self.map_id = map_id
        self.kenh = kenh
        self.dang_danh = bool(dang_danh)
        self.so_member = int(so_member or 0)
        self.viec_dang_lam = viec_dang_lam
        self.xong_chore = bool(xong_chore)      # da lam xong viec vat sau login chua
        self.xong_daily = bool(xong_daily)      # da lam NHIEM VU NGAY chua (PB don o1 + claim 9 o)
        self.trong_dg = bool(trong_dg)          # dang o trong map Di Gioi
        self.trong_pb = bool(trong_pb)          # dang o trong map PHO BAN TO DOI (instance)
        self.con_gio_dg = bool(con_gio_dg)      # server bao con phut Di Gioi hom nay
        self.dang_ban = bool(dang_ban)          # worker dang chay mot viec CHUA XONG
        self.trong_event = bool(trong_event)    # dang o TRONG map event
        # Gen lenh tay (GUI) ma acc NAY da thi hanh xong. Nho tren client nen relogin la lam lai -
        # dung, vi acc moi vao chua he chay lenh do.
        self.lenh_tay_da_lam = int(lenh_tay_da_lam or 0)

    def __repr__(self):
        return "<%s map=%s k=%s%s %s>" % (self.username, self.map_id, self.kenh,
                                          " danh" if self.dang_danh else "", self.viec_dang_lam)


class AnhParty:
    """Anh chup ca party + dich ma engine dang nham toi."""

    __slots__ = ("pidx", "accs", "can_bao_nhieu", "map_dich", "luc", "pha", "co_spot",
                 "pb_doi_level", "co_pha_train", "thanh_di_ngang", "cho_ly_do",
                 "dp_viec", "event_xong", "reform_moi", "resync_moi", "nguoi_keo",
                 "thanh_dich", "thieu_acc_song", "tang_gom", "fc_buoc", "lenh_tay_gen")

    def __init__(self, pidx, accs, can_bao_nhieu=0, map_dich=None, luc=None,
                 pha=PHA_TRAIN, co_spot=False, pb_doi_level=None, co_pha_train=True,
                 thanh_di_ngang=False, cho_ly_do="", dp_viec=None, event_xong=False,
                 reform_moi=False, resync_moi=False, nguoi_keo="*", thanh_dich=None,
                 thieu_acc_song=False, tang_gom=None, fc_buoc=None, lenh_tay_gen=0):
        self.pidx = int(pidx)
        self.accs = list(accs)
        self.can_bao_nhieu = int(can_bao_nhieu or 0)   # so member can (khong ke leader)
        self.map_dich = map_dich                       # map train / diem tap ket da chot
        self.luc = float(luc if luc is not None else time.time())
        self.pha = pha                                 # PHA_DG / PHA_TRAIN
        self.co_spot = bool(co_spot)                   # da chot duoc tam bai quai chua
        self.pb_doi_level = pb_doi_level               # level PB to doi con luot (None = het)
        self.co_pha_train = bool(co_pha_train)         # mode `digioi` thuan: xong DG la THOAT
        self.thanh_di_ngang = bool(thanh_di_ngang)     # dang o thanh TRUNG GIAN -> chua lap party
        self.cho_ly_do = cho_ly_do or ""               # != "" -> chua nen ra lenh, ca party cho
        self.dp_viec = dp_viec                         # viec CAP PARTY do `_dieu_phoi_quyet` chot
        self.event_xong = bool(event_xong)             # event da xong / ngoai gio -> di doi thuong
        # 2K: TANG GOM do `_tang_gom_2k` cua engine cu chot (tang thap nhat ca doi dang o, hoac
        # `dest_map` khi con dua ngoai thap). None = khong phai 2K / khong ai trong thap.
        self.tang_gom = int(tang_gom) if tang_gom else None
        # 2K: buoc ke tiep cua leader (`danh` / `len_tang`), do `floor_crawl.tinh_buoc()` chot.
        # None = khong phai 2K, hoac tang da xong/het duong (luc do dieu phoi chot "2K het").
        self.fc_buoc = fc_buoc or None
        # `cmd_gen` cua party (GUI tang moi khi ra lenh tay). 0 = chua co lenh nao.
        self.lenh_tay_gen = int(lenh_tay_gen or 0)
        # HAI LENH CAP PARTY THAT SU cua dieu phoi deu di bang GEN, khong bang `kh["viec"]`:
        #   `reform_gen` (tu `gom`)    -> ca party ve THANH TAP KET gom lai
        #   `resync_gen` (tu `dong_bo`)-> member ROI PARTY + sync kenh lai ngay tai cho
        # Engine moi truoc day diec ca hai - dung cai benh no sinh ra de chua.
        self.reform_moi = bool(reform_moi)
        self.resync_moi = bool(resync_moi)
        # AI DUOC DI DUONG (`dat_nguoi_keo` cua dieu phoi): ten mot acc = chi acc do; "*" = ai cung
        # duoc (dang GOM, hoac party khong co bot-leader).
        #
        # Di ra bai train bat buoc TELEPORT, ma teleport phai ROI DOI truoc - nen viec nay phai
        # giao cho DUNG MOT nguoi, hai acc cung di la party tan. `client.teleport` co san cua chan
        # nay, NHUNG no nam trong `if self.party_members:` - leader roi doi TRUOC khi tele thi doi
        # tan, member khong con `party_members` nen cua khong con hieu luc.
        # Ca that 17/09 party 44, trong DUNG MOT GIAY (00:02:48, ca 5 acc deu duoc giao `ve_map`
        # toi map train 15457, trong khi dieu phoi giao viec di duong cho MOT minh 'tp601'):
        #     tpmot -> hop 12061   tphai -> hop 12061   tpnam -> hop 12061
        #     tpba  -> hop 12001   tpbon -> hop 12001
        # (`pre_route_town_hop` boc ngau nhien 50-50 Trac Quan / Nghiep Thanh tren TUNG acc.)
        # Party vua du 4/4 luc 00:02:48 -> 00:02:49 tan, roi moi dua mot thanh.
        self.nguoi_keo = nguoi_keo or "*"
        # THANH TAP KET da chot (`chot_thanh_tap_ket` -> `st["route_plan"]["city"]`). Acc chua ve
        # toi day thi con phai ve, du no khong duoc lap duong di bai train.
        self.thanh_dich = thanh_dich
        # CHUA DU ACC LOGIN XONG - chua duoc ket luan map/kenh. TU TINH tu chinh anh chup:
        # acc con trong party ma chua vao world (`song=False`) thi party chua du.
        # `_clients_cua_party` da bo acc TAT HAN roi, nen khong so cho vinh vien.
        self.thieu_acc_song = bool(thieu_acc_song) or any(not a.song for a in self.accs)

    # --- doc tinh hinh: CHI tinh acc dang song va KHONG lam viec vat ---
    #
    # Acc dang lam VIEC VAT phai o map khac (ban Noi Dan o Nghiep Thanh, cat tien trang, boss the
    # gioi - user 14/09), nen dem no vao phep do la party LUC NAO cung "lech map". Lenh van chay
    # binh thuong tren so acc con lai; acc kia giu loi moi, xong viec thi nhan.
    #
    # Biet acc nao dang lam viec vat bang CHINH VIEC ENGINE DA GIAO (`viec_dang_lam`), khong hoi
    # co `dang_lam_viec_vat()` cua client - co do nhap nhay va tung lam ca party quay vong.
    def _dem_duoc(self):
        return [a for a in self.accs
                if a.song and a.viec_dang_lam not in (VIEC_LOGIN_CHORE, VIEC_VIEC_VAT,
                                                      VIEC_DAILY)]

    def maps(self):
        return sorted({a.map_id for a in self._dem_duoc() if a.map_id is not None})

    def kenhs(self):
        return sorted({a.kenh for a in self._dem_duoc() if a.kenh})

    def leader(self):
        for a in self.accs:
            if a.la_leader and a.song:
                return a
        return None

    def roster_leader(self):
        """So member LEADER dang thay. Doc cua LEADER chu khong phai ban sao ngheo nhat: moi acc
        giu mot ban roster rieng, ban cua member thuong cu hon (party 11 - leader thay 3/4 trong khi
        co member con thay 1/4) va lay ban ngheo nhat thi engine tuong party hong, gom lai vo ich."""
        lead = self.leader()
        return lead.so_member if lead is not None else 0


# ---------------------------------------------------------------- nhip quyet dinh (HAM THUAN)

def _map_dich(anh: AnhParty, con_lai, maps):
    """Party dang o nhieu map -> DON VE DAU khi engine chua chot diem tap ket.

    Ve map DONG NGUOI NHAT, hoa thi theo LEADER. Lay bua mot map (vd map nho nhat) la co luc bat ba
    dua dang dung dung cho di theo mot dua lac - chinh la kieu "gom" tra gia dat nhat: ca party roi
    bai train de chay theo nguoi chet hoi sinh o thanh.
    """
    if not maps:
        return None
    dem = {}
    for a in con_lai:
        if a.map_id is not None:
            dem[a.map_id] = dem.get(a.map_id, 0) + 1
    if not dem:
        return None
    dong_nhat = max(dem.values())
    ung_vien = [m for m, n in dem.items() if n == dong_nhat]
    if len(ung_vien) > 1:
        lead = anh.leader()
        if lead is not None and lead.map_id in ung_vien:
            return lead.map_id
    return sorted(ung_vien)[0]


def _duoc_di_duong(anh, a):
    """Acc nay co duoc TU DI DUONG khong (`dat_nguoi_keo` cua dieu phoi).

    "*" = ai cung duoc (dang GOM - luc do doi da hong nen ca party phai tu ve diem hen; hoac party
    khong co bot-leader). Ten mot acc = chi acc do.
    """
    _keo = getattr(anh, "nguoi_keo", "*") or "*"
    return _keo == "*" or _keo == a.username


# Viec di bang TELEPORT - trong map event khong teleport duoc nen o trong thap 2K chung la lenh
# RONG (xem nhanh `tang_gom` trong `quyet_dinh`). KHAC voi cua "dang danh" ngay ben duoi.
VIEC_DI_CHUYEN = (VIEC_VE_MAP, VIEC_VE_THANH, VIEC_DOI_KENH, VIEC_RA_SPOT, VIEC_RESYNC,
                  VIEC_VAO_EVENT, VIEC_DI_GIOI, VIEC_DOI_THUONG)

# ================= DANG TRONG TRAN: ALLOWLIST, khong phai blocklist =================
#
# Day la DANH SACH VIEC DUOC PHEP giao khi acc dang danh. MOI viec khac deu bi hoan.
#
# Truoc day cho nay la blocklist (`VIEC_DI_CHUYEN` - "nhung viec KHONG duoc giao"), tuc them viec
# moi thi phai NHO khai bao vao do. Da quen HAI LAN, cung mot kieu hong:
#   17/09 p56: 've_map'  giao lai 260 lan lien tiep trong luc `BATTLE SEND` (user: "sao vua danh
#              vua doi tele ve thanh la sao")
#   21/09 p21: 'pb_doi'  giao lai 3760 lan lien tiep trong luc `BATTLE SEND` -> leader ket trong
#              tran khong vao duoc phong PB, 4 member vao roi ngoi cho -> "roster phong chi 0/4"
#              -> HUY + relogin ca party, lap vo tan (user: "sao 4 dua trong PB, con 1 dua o
#              ngoai" / "tao chan canh va ngu cua may lam roi")
# Lan hai da co san ba viec moi (`2k_danh`, `2k_len_tang`, `fc_gom`) chua ai xet, tuc lan ba chi
# la chuyen som muon. Dao lai thanh allowlist thi viec them sau nay MAC DINH AN TOAN: quen la
# quen theo huong hoan lai, khong phai huong gui goi giua tran.
#
# Duoc phep, va vi sao:
#   NGHI          - khong lam gi
#   TRAIN         - chinh no LA danh
#   PB_DOI_THEO   - chi bat co `auto_accept_party`/`flee_mode`, khong gui goi nao
#   THOAT         - user Stop / het gio: phai thoat duoc ke ca dang danh
VIEC_LAM_DUOC_GIUA_TRAN = frozenset({VIEC_NGHI, VIEC_TRAIN, VIEC_PB_DOI_THEO, VIEC_THOAT})


def quyet_dinh(anh: AnhParty):
    """(anh chup) -> {username: viec}. HAM THUAN: khong I/O, khong sleep, khong doc dong ho.

    Test duoc thang, va vi khong chan nen KHONG THE co "vong cho diec" - do la ca diem cua engine
    nay. Do tren engine cu: mot quyet dinh danh = 0,014ms (p99 0,024ms), 5 acc = 0,1ms tren ngan
    sach `submit_delay` 500ms => nhip 1 giay du cho ca tram party.
    """
    ket = _quyet_dinh_goc(anh)
    # DANG TRONG TRAN thi HOAN het, tru vai viec trong `VIEC_LAM_DUOC_GIUA_TRAN` (allowlist).
    #
    # Gui goi giua tran thi hoac bi TRAN CHAN (teleport/doi kenh - client game chan thang), hoac
    # lam hong chinh viec do (mo phong PB ma leader dang ket trong tran). Ca hai deu that bai NGAY
    # va nhip sau engine giao lai -> vong quay khong lam duoc gi. Engine cu luon
    # `_wait_combat_clear` / `_ra_safe_truoc_khi_doi_kenh` truoc nhung buoc nay.
    #
    # Hai ca that, cung mot kieu hong, cach nhau 4 ngay - xem `VIEC_LAM_DUOC_GIUA_TRAN` de biet
    # vi sao cho nay la ALLOWLIST chu khong phai blocklist:
    #   17/09 p56: 've_map' giao lai 260 lan lien tiep trong luc `BATTLE SEND`
    #   21/09 p21: 'pb_doi' giao lai 3760 lan lien tiep trong luc `BATTLE SEND`
    if ket:
        _dang_danh = {a.username for a in anh.accs if a.song and a.dang_danh}
        if _dang_danh:
            # ALLOWLIST: chi viec trong `VIEC_LAM_DUOC_GIUA_TRAN` moi duoc giao khi acc dang danh,
            # con lai HOAN het (xem chu thich cua hang so do - no ghi ca hai lan da quen).
            for _u in list(ket):
                if _u in _dang_danh and ket[_u] not in VIEC_LAM_DUOC_GIUA_TRAN:
                    ket[_u] = VIEC_NGHI
        # DANG TRONG THAP 2K thi MOI viec DI CHUYEN deu la lenh RONG - trong map event khong
        # teleport duoc, ma `ve_thanh`/`resync`/`ve_map` deu di bang teleport. Muon xe nhau trong
        # thap chi co MOT duong: DI BO (`VIEC_FC_GOM`).
        #
        # Day dung la benh cua engine cu, party 5 (06/09) - leader `thsau` 422.627 dong log, trong
        # do 201.495 cap lap lai:
        #   13:20:58 (LEADER) dieu phoi bao GOM (party lech kenh [1, 5]) -> thoi moi, gom lai
        #   13:20:58 (LEADER) reform: khong co smart/legacy route -> bo qua
        # Vong nong 8.000 vong/giay an GIL, bo doi luon luong dieu phoi.
        if anh.tang_gom:
            _trong_thap = {a.username for a in anh.accs
                           if a.song and a.trong_event and int(a.map_id or 0)}
            for _u in list(ket):
                if _u in _trong_thap and ket[_u] in VIEC_DI_CHUYEN:
                    ket[_u] = VIEC_NGHI
    return ket


def _quyet_dinh_goc(anh: AnhParty):
    """Chuoi quyet dinh that - xem `quyet_dinh` (no chi loc them cua "dang trong tran")."""
    song = [a for a in anh.accs if a.song]
    if not song:
        return {}

    # (0-) LENH TAY CUA USER - CAT TRUOC MOI THU, ke ca cua "chua nen ra lenh".
    #
    # User bam "Teleport ve thanh" / "Di map" tren GUI thi do la lenh ro rang, khong phai thu bot
    # tu suy - de no xep hang sau chuoi gom/train thi co khi khong bao gio toi luot.
    #
    # Truoc 21/09 engine moi KHONG DOC `cmd_gen` mot dong nao: `party_teleport_city` chi dat
    # `st["cmd"]` roi tang gen, va NOI DUY NHAT doc gen do la vong keepalive cua `run_account`
    # (engine cu). Nen voi party tu 21 tro len, lenh tay roi vao hu khong.
    # User 21/09: "P21 dang train -> chon map -> chon thanh thi ko co gi xay ra ca".
    if anh.lenh_tay_gen:
        _chua = [a for a in song if int(a.lenh_tay_da_lam or 0) < int(anh.lenh_tay_gen)]
        if _chua:
            ket = {a.username: VIEC_LENH_TAY for a in _chua}
            for a in song:
                ket.setdefault(a.username, VIEC_NGHI)   # nguoi xong roi thi DUNG YEN cho ca lu
            return ket

    # (0) CHUA NEN RA LENH -> ca party DUNG YEN cho.
    #
    # Engine cu co bon cua nay TRUOC ca chuoi (`_dieu_phoi_quyet`): leader dang rot, co acc dang
    # doi kenh, thieu acc song, lech instance. Bo chung di thi engine ra lenh vao dung luc party
    # dang xao tron - vd bump lenh gom trong khi leader chua login xong.
    if anh.cho_ly_do:
        # "Cho" = khong ra lenh MOI. Acc dang lam viec chan thi de lam not (`giao` tra False khi
        # viec khong doi nen no khong bi huy).
        return {a.username: (a.viec_dang_lam if a.viec_dang_lam in BAN_THI_CHO else VIEC_NGHI)
                for a in song}

    # LENH LA CAP PARTY - MOT viec cho CA LU, khong phai moi acc mot viec.
    #
    # Engine cu ra DUNG MOT viec cho ca party (`_dieu_phoi_quyet` -> VIEC_GOM / VIEC_MOI /
    # VIEC_DONG_BO / VIEC_LAM), roi tung acc thi hanh theo VAI (leader moi, member mo cua nhan).
    #
    # Ban dau engine moi tinh rieng cho tung acc VA loai acc "dang ban" khoi phep do -> moi nhip
    # tinh tren mot tap acc khac nhau -> ra quyet dinh khac nhau -> PARTY BI XE LE.
    # Ca that 16/09 party 41 (user: "3 dua o giang dong 2 dua o trac quan"):
    #   17:37:32 dt806 -> login_chore
    #   17:37:33 dt807 -> lap_party
    #   17:37:42 dt808 -> lap_party
    #   17:37:43 dt809 -> ve_map
    # Ba nhom, ba huong.
    #
    # Acc dang ban thi khong sao: `AccWorker.giao` tra False khi viec khong doi, nen viec dang chay
    # KHONG bi huy. Con acc nao chua lam thi nhan lenh va di theo ca lu.

    ket = {}

    # (0a) Acc dang viec vat: KHONG QUAY RAY (user 14/09 - "khi dang danh PB don va daily quest thi
    # dieu phoi tam thoi ko quay ray"). Xong viec no tu quay lai hang doi o nhip sau.
    #
    # NHUNG: neu chinh ENGINE dang giao `login_chore` cho no thi PHAI GIU NGUYEN viec do. Worker
    # vua bat dau `lam_viec_vat` la `dang_lam_viec_vat()` thanh True -> nhip sau ra `viec_vat` ->
    # giao viec MOI -> HUY chinh viec vat dang chay -> lai False -> lai `login_chore`... Vong nay
    # quay vo tan va viec vat KHONG BAO GIO XONG.
    # Do that 15/09 (lan chay dau tien): 33 lan `-> login_chore` xen ke 31 lan `-> viec_vat` cho
    # cung mot nhom acc trong vai phut.
    # KHONG HOI ACC "MAY DANG BAN GI".
    #
    # Engine la MOT luong nam ca 5 client va CHINH NO giao viec, nen no biet thua acc dang lam gi:
    # `a.viec_dang_lam` la viec no vua giao o nhip truoc. Ban dau o day con doc `c.dang_lam_viec_vat()`
    # - mot co do CLIENT tu gan, NHAP NHAY theo tung pha `task_report` - roi lay no de quyet dinh.
    # Hau qua: nhip ra `viec_vat`, nhip sau ra lai viec cu, moi lan giao la HUY viec dang chay ->
    # acc khong bao gio di toi dau.
    #   15/09: `login_chore` <-> `viec_vat`, 33 lan xen ke 31 lan
    #   16/09 party 41: `ve_map` <-> `viec_vat` moi giay, dung nguyen o Trac Quan ca ngay
    #   16/09 party 51: `pb_doi_theo` <-> `viec_vat`
    # (user: "chay chung 1 thread ma ko biet duoc acc do dang ban lam gi a")
    # (0b) CHUA XONG VIEC VAT SAU LOGIN -> lam cho xong, dung keo di dau.
    #
    # User 14/09: "dang lam may cai viec vat do ko vao pt la dung... vao pt roi bi keo di luon thi
    # no hong viec vat". Va cua hoan cu (bo 14/09) tung lam 96% acc mat luot PB don CA NGAY vi
    # dieu phoi luc nao cung dang gom dung luc acc moi login.
    for a in song:
        if a.username not in ket and not a.xong_chore:
            ket[a.username] = VIEC_LOGIN_CHORE

    # (0b2) CHUA LAM NHIEM VU NGAY -> lam da.
    #
    # Engine moi khong chay `run_account` nen MAT SACH khoi "viec hang ngay" cua no:
    # `do_daily_dungeon()` (o 1) + `claim_daily_quests(heavy=True)` (keo theo o2 boss the gioi,
    # o5 pho ban to doi). Do duoc tren log 17/09: 60 acc thuoc party 41-56 (dung engine moi) KHONG
    # co MOT DONG `Nhiem vu hang ngay` nao ca ngay, trong khi party engine cu deu 8-9/9 o.
    #
    # KHONG lam trong pha DI GIOI: o2 la boss the gioi -> `do_world_boss()` TELEPORT di roi tra ve
    # Trac Quan, tuc VUT acc ra khoi Di Gioi. Flow cu cung hoan toi sau DG vi dung ly do do
    # (`_do_startup_daily` co dieu kien `not is_digioi`).
    #
    # Viec nay KHONG dung toi chuoi lap party: no nam trong danh sach "dang lam viec vat" cua
    # `_dem_duoc`, nen acc dang lam se khong bi tinh vao phep do lech map/kenh - y het `login_chore`.
    if anh.pha != PHA_DG:
        for a in song:
            if a.username not in ket and not a.xong_daily:
                ket[a.username] = VIEC_DAILY

    con_lai = [a for a in song if a.username not in ket]
    if not con_lai:
        return ket

    # (0c1) PHA EVENT (40NPC / 2K...). LAM Y FLOW CU (`run_account`, nhanh `elif mode == "event"`):
    #   1. NGOAI GIO event / da xong  -> di doi thuong roi THOAT GAME
    #   2. CHUA VAO MAP EVENT         -> vao da (`go_to_event`), CHUA VAO THI CHUA LAP PARTY
    #   3. da vao, thieu doi          -> lap party
    #   4. du doi                     -> LEADER mo vong battle, member dung yen theo
    #
    # Ban dau engine moi khong co nhanh nay: party mode event bi xu ly y nhu train -> LAP PARTY
    # NGAY GIUA THANH khi chua vao map event (user 16/09: "p41, mode 40npc -> chua vao map event
    # da thay lap pt").
    def _nhanh_event():
        if anh.event_xong:
            for a in con_lai:
                ket[a.username] = VIEC_DOI_THUONG
            return ket
        _ngoai = [a for a in con_lai if not a.trong_event]
        for a in _ngoai:
            ket[a.username] = VIEC_VAO_EVENT
        _trong = [a for a in con_lai if a.trong_event]
        if _trong:
            # DU PARTY MOI DANH (L0) va phai vao DU NGUOI - bo lai mot dua la no dung ngoai map
            # event ca buoi.
            _du_vao = not _ngoai
            _du_doi = anh.can_bao_nhieu <= 0 or anh.roster_leader() >= anh.can_bao_nhieu
            # 2K LECH TANG -> DI BO ve tang gom TRUOC da. Trong thap KHONG teleport duoc nen
            # `ve_thanh`/`resync` o duoi la lenh RONG (engine cu 06/09: `reform: khong co
            # smart/legacy route -> bo qua` roi quay 201.495 vong).
            # `anh.tang_gom` do `_tang_gom_2k` cua engine cu chot - TANG THAP NHAT ca doi dang o,
            # KHONG phai day thap: tut ve day la mat sach tang da leo. Chi khi con dua o NGOAI
            # thap no moi tra `dest_map` (12922 - cua vao, cho ngoai tele vao duoc).
            if anh.tang_gom:
                _lech = [a for a in _trong if int(a.map_id or 0) != int(anh.tang_gom)]
                if _lech:
                    for a in _lech:
                        ket[a.username] = VIEC_FC_GOM
                    for a in _trong:
                        ket.setdefault(a.username, VIEC_NGHI)
                    return ket
            if _du_vao and _du_doi:
                # 2K: ENGINE giao TUNG BUOC cho leader, khong bam nut roi tha cho mot thread rieng
                # cam lai. Trong thap chi leader di chuyen - member dinh party tu theo - nen ca
                # vong leo thap chi la chuoi buoc CUA MOT ACC.
                #
                # `fc_buoc` do `tinh_buoc()` cua `floor_crawl` chot (ham thuan): "danh" = con diem
                # quai chua danh o tang nay; "len_tang" = danh het roi, va vi da qua duoc cua
                # `_du_doi` o tren nen DU PARTY that su - L0 duoc bao dam bang ANH CHUP, khong con
                # phai nam cho trong callback `du_party()` 60 giay nhu ban cu.
                if anh.fc_buoc in (FC_DANH, FC_LEN_TANG):
                    _viec = VIEC_2K_DANH if anh.fc_buoc == FC_DANH else VIEC_2K_LEN_TANG
                    for a in _trong:
                        ket[a.username] = _viec if a.la_leader else VIEC_NGHI
                    return ket
                for a in _trong:
                    ket[a.username] = VIEC_DANH_EVENT if a.la_leader else VIEC_NGHI
                return ket
            # CHUA DU DOI -> NHUONG cho `_dieu_phoi_quyet` (nhanh `dp_viec` ben duoi), KHONG tu cho
            # `lap_party` o day.
            #
            # Engine cu voi event party goi `do_channel_sync()` NGAY TRUOC khi mo gate moi, vi map
            # event cung chia kenh: lech kenh la KHONG THAY NHAU, leader moi mai khong ai join
            # (bug 40NPC 29/07). `do_channel_sync` la closure trong `run_account` (barrier per-acc)
            # nen thread party khong goi thang duoc - nhung dieu phoi CAP PARTY da lam dung viec do:
            # no chot `dong_bo` kem kenh `pick_best_channel`, DICH_VIEC dich thanh `doi_kenh`.
            #
            # Truoc day nhanh nay cho thang `lap_party` -> NUOT mat `dong_bo` cua dieu phoi: p41
            # 16/09 21:08 ca doi o map event nhung LECH KENH [1,2,3], `lap_party` giao lai 40 lan
            # lien tiep ma khong ai join duoc.
            if _du_vao and DICH_VIEC.get(anh.dp_viec) is not None:
                return None     # KHONG chot gi -> chay tiep xuong nhanh `dp_viec`
            for a in _trong:
                ket[a.username] = VIEC_LAP_PARTY
        return ket

    if anh.pha == PHA_EVENT:
        _kq_ev = _nhanh_event()
        if _kq_ev is not None:
            return _kq_ev
        # _nhanh_event() tra None = "ca doi da vao map event nhung chua du doi" -> NHUONG cho
        # `_dieu_phoi_quyet` gom/dong bo kenh/moi theo dung 11 nhanh cua no.

    # (0c) PHA DI GIOI: con gio thi CA PARTY vao DG. Di Gioi la instance rieng - vao roi thi khong
    # con khai niem lech map/kenh voi nhau, nen cat truoc ca chuoi gom.
    if anh.pha == PHA_DG:
        # HET GIO DG XU LY TRUOC, BAT KE DANG DUNG O DAU.
        #
        # Flow cu (`_cho_party_xong_dg`): `if remain <= 0 ... -> _ket_thuc_pha_dg()` - no KHONG
        # hoi acc dang o trong hay ngoai map DG. Ban dau engine moi chi xet acc CHUA VAO, nen acc
        # dang o trong DG ma het gio thi van duoc cho danh tiep: mode `digioi` thuan KHONG BAO GIO
        # tat acc (user 16/09: "p46 p54, mode Di gioi -> het tiem di gioi roi ma deo tat acc").
        _het_gio = [a for a in con_lai if not a.con_gio_dg]
        for a in _het_gio:
            # Mode `digioi` THUAN: xong DG la THOAT GAME, dung engine cu van lam.
            # Mode `digioi_train`: dung yen cho ca party doi pha sang train.
            ket[a.username] = VIEC_NGHI if anh.co_pha_train else VIEC_THOAT
        _con_gio = [a for a in con_lai if a.con_gio_dg]
        for a in _con_gio:
            if not a.trong_dg:
                ket[a.username] = VIEC_DI_GIOI
        _trong = [a for a in _con_gio if a.trong_dg]
        if _trong:
            # DU PARTY ROI MOI CHAY LONG VONG (L0, user chot 16/09: "DG van phai du pt moi chay
            # long vong chu").
            #
            # Hai dieu kien, thieu mot la CHUA duoc danh:
            #   1. moi acc CON GIO deu da VAO DG   - con dua ngoai thi vao day danh mot minh la bo
            #      no lai, va no vao sau se khong co ai keo
            #   2. roster leader DU               - vao du roi nhung chua lap doi thi danh le
            _du_vao = len(_trong) == len(_con_gio)
            _du_doi = anh.can_bao_nhieu <= 0 or anh.roster_leader() >= anh.can_bao_nhieu
            # DA CO ACC KHAC HET GIO DG -> DUNG YEN, khong chay long vong danh le.
            #
            # Y engine cu (`_start_training`, dong 6368-6375): "Co acc KHAC het gio DG -> party
            # khong gom duoc nua -> KHONG chay long vong danh 1 minh (de chet vi khong co party
            # hoi mau). DUNG YEN burn time trong DG den khi het gio cua chinh minh."
            _co_dua_het_gio = any(not a.con_gio_dg for a in con_lai)
            for a in _trong:
                if _co_dua_het_gio:
                    ket[a.username] = VIEC_NGHI
                else:
                    ket[a.username] = VIEC_TRAIN if (_du_vao and _du_doi) else VIEC_LAP_PARTY
        return ket

    # QUYET DINH CAP PARTY: LAY TU DIEU PHOI CU (`_dieu_phoi_quyet`).
    #
    # DAT SAU hai pha dac thu (EVENT / DI GIOI): dieu phoi cu ra `VIEC_LAM` cho ca hai mode do
    # (no khong biet "vao map event" hay "vao DG" la viec gi), ma `lam` -> `train`. Dat truoc thi
    # nhanh event/DG KHONG BAO GIO chay toi.
    # Ca that 16/09 party 41 mode 40NPC (user: "p41 van ko vao event"):
    #   20:54:45 [party 41] ENGINE: dt806..dt810 -> train    <- dang phai la `vao_event`
    #
    # Engine moi KHONG tu nghi ra chuoi lenh. Chuoi that co 11 nhanh va 15 phep thu
    # (`_leader_dang_rot`, `_dang_doi_kenh`, `_thieu_acc_song`, `_ai_lech_instance`,
    # `_o_thanh_di_qua`, `_thieu_doi`, `_viec_di_train`...); ban tu viet o day chi co 4 bac nen
    # moi nhanh thieu la mot loi user phai di tim ho suot hai ngay
    # (user 16/09: "sao may ko tham khao cai cu da co ma cu thich bia ra cai moi").
    #
    # (0d) PHO BAN TO DOI - dat TRUOC ca chuoi gom VA truoc ca nhanh `dp_viec`.
    #
    # Nhanh `dp_viec` ben duoi `return ket` ngay khi dich duoc viec, nen dat PB o SAU no la
    # KHONG BAO GIO chay toi: party dang train thi dieu phoi ra `lam` -> `VIEC_TRAIN` cho ca
    # lu -> return. Dung cai loi da gap voi nhanh event 16/09.
    # Ca that 17/09 party 45 (user: "p45 van ko danh PB doi"): 23:50 daily xong con 7/9
    # (thieu o5) ma tu do khong mot lan nao duoc giao `pb_doi`, trong khi 23:48 - luc dieu
    # phoi CHUA quyet duoc - thi co.
    #
    # DUONG LAP DOI CUA PB KHAC HAN party thuong (user 15/09: "duong lap pt PB no khac voi lap pt
    # di train"). Theo KNOWLEDGE.md:
    #   - party thuong: moi `0x0d/0900`, member phai mo gate (`set_party_invite_ready`)
    #   - phong PB    : moi `Dungeon.SendInvite` -> `0x2f/0800`; member nhan `0x2f/0f00` roi
    #                   join room `0x2f/0300` + ready `0x2f/0b00` - `_on_dungeon` TU LAM het,
    #                   member khong phai lam gi ca
    # "PB invite KHONG bat buoc check gan nhu party thuong vi server/client cho moi theo roleId da
    # biet" => KHONG can cung map, KHONG can cung kenh, KHONG can du party thuong truoc.
    # Bat party gom du 4/4 roi moi cho danh PB la tu dat them dieu kien ma game khong doi, va moi
    # phut gom la mot phut co the mat luot PB.
    # CHECK PB TO DOI **SAU** khi da check nhiem vu ngay (user chot 20/09: "check PB doi sau daily
    # quest") - tuc nhanh nay dung SAU nhanh (0b2) o tren, chu KHONG doi phai xong daily.
    #
    # CHI SUA ENGINE MOI: `run_account` giu nguyen thu tu cu cua no.
    # PHAI DU NGUOI RANH moi mo phong (L0: du party roi lam gi thi lam).
    #
    # `con_lai` = acc chua bi giao viec le o cac nhanh tren (login_chore / daily). Dua dang lam
    # viec le KHONG nhan `pb_doi_theo`, ma leader thi van moi du 4 nguoi -> server chi cong nhan
    # nhung dua vao duoc, leader do roster thay thieu roi HUY, tao lai, quay vong.
    #
    # Ca that 20/09 party 41 (user: "van thay 3 dua trong PB, 2 dua ben ngoai"):
    #   11:43:23 dtsau@62013(L) dtbay@62013 dt9ch@62013 | dttam@22000* dtmuoi@22000*
    #   11:45:54 (LEADER) lv110 member ready 4/4 sau 2.0s -> START     <- bot TU bao ready
    #   11:46:06 (LEADER) roster phong pho ban chi 2/4 member -> THIEU nguoi, HUY danh de gom lai
    # (`*` = dang lam viec le). Ready 4/4 la bot tu bao, roster moi la so server cong nhan.
    # Ca that 21/09 party 20 - "1 dua dung ngoai PT" suot 4 phut. KHONG phai loi o nhanh nay:
    #   17:11:44 (LEADER) moi 3 member theo entity (live dung map/kenh): [...]   <- chi 3!
    #   17:11:55 TRANG THAI: dieumot@21001(L) dieuhai@21001 dieuba@12001 dieubon@21001 dieunam@21001
    # `invite_members` doi member phai CUNG MAP moi moi, nen dieuba (Trac Quan) khong duoc moi ->
    # khong vao duoc doi. Ma doi nay la doi di PHO BAN TO DOI - thu khong can cung map chut nao.
    # User: "day la pt PB, no ko moi dua khac map la may code ngu". Da sua o `client.py`
    # (`_bot_member_is_on_current_scene`): moi truoc, lech map thi gom sau.
    #
    # (Da thu sua o DAY hai cach, deu SAI, giu lai de khong ai lam lai:
    #  - "giu phien PB" bang `any(viec_dang_lam == pb_doi_theo)`: co TU NUOI CHINH NO -> khoa cung
    #    party vao PB vinh vien;
    #  - hoan PB / day dua lech map di gom: mat luot PB, ma "di PB doi thi co can gom map deo dau".)
    if anh.pb_doi_level is not None and len(con_lai) == len(song):
        # (b2) TAT CA VE THANH TRUOC, khong mo phong khi dang dung o BAI QUAI (user chot 21/09).
        #
        # Dung o bai quai thi acc con bi keo tran giua chung: accept loi moi / bam CHUAN BI khong
        # an, ma leader thi van dem "ready" (bot tu bao) roi START -> server chi cong nhan 2/4.
        # Ca that party 17, 21/09 - leader mo phong luc ca party con o map train va LECH KENH:
        #   06:04:07 TRANG THAI: chusau@12001/k4(L) chubay@12001/k3 ... | roster leader=0/4
        #   06:04:09 (LEADER) === PHO BAN TO DOI LV20: tao + moi 4 member ===
        #
        # VE THANH TAP KET (thanh cua route, user chon 21/09) - danh xong quay lai bai train gan,
        # khong phai di lai tu thanh trung gian. Dung DUNG `VIEC_VE_THANH` san co, khong tu viet
        # duong di moi.
        # DANG O TRONG INSTANCE PHO BAN thi TUYET DOI khong ep ve thanh: `go_to_town` tu chan
        # ("DANG TRONG pho ban to doi -> khong teleport") nen lenh do KHONG LAM GI, chi de lai
        # moi acc 3-4 dong `pre-route: tele trung gian...` moi nhip.
        # Ca that 21/09 party 1 (user: "no co them 1 dong log doi tele kia"):
        #   05:31:26 [nasau] pre-route: tele trung gian ve thanh 12061 truoc
        #   05:31:26 [nasau] go_to_town: DANG TRONG pho ban to doi (map=62012) -> khong teleport
        # Buoc "ve thanh truoc" chi de danh cho luc CHUA vao phong.
        _thanh = anh.thanh_dich
        if _thanh and not any(a.trong_pb for a in con_lai):
            _chua_ve = [a for a in con_lai
                        if a.map_id is not None and int(a.map_id) != int(_thanh)]
            if _chua_ve:
                for a in _chua_ve:
                    ket[a.username] = VIEC_VE_THANH
                for a in con_lai:
                    ket.setdefault(a.username, VIEC_NGHI)   # toi noi roi thi DUNG YEN cho ca lu
                return ket
        for a in con_lai:
            ket[a.username] = VIEC_PB_DOI if a.la_leader else VIEC_PB_DOI_THEO
        return ket

    # LENH THAT CUA DIEU PHOI DI BANG **GEN**, khong bang `kh["viec"]`.
    #
    # `_dieu_phoi_thi_hanh` moi la nguoi phat lenh, va no phat DUNG MOT NHAT roi vao cooldown
    # 180s (`KE_HOACH_GOM_COOLDOWN`) - vi moi lenh gom ABORT moi acc dang di duong, ra lien tuc la
    # ca party khong di xong buoc nao. Hai lenh do:
    #     `gom`     -> `_bump_reform`   -> `reform_gen` -> ca party ve THANH TAP KET
    #     `dong_bo` -> `resync_gen += 1`-> member ROI PARTY + sync kenh lai NGAY TAI CHO
    # `kh["viec"]` thi van bao 'gom'/'dong_bo' deu deu suot ca cooldown - do la TRANG THAI, khong
    # phai lenh. Dich thang no thanh viec = giao lai moi giay, dap chinh lenh dang chay.
    # GOM: acc nao CHUA ve toi diem gom thi con phai ve - giao LAI moi nhip cho toi khi toi noi.
    #
    # Flow cu lap NGAY TRONG hanh dong (`_do_reform`: `while not _ab() and c.current_map !=
    # _target_city: ... time.sleep(10)`), vi ben do `reform_gen` bump MOT NHAT roi cooldown 180s.
    # Engine moi khong co vong do - no giao viec moi nhip - nen phai giao LAI, khong thi acc nao
    # tele fail (dang danh / thanh chua mo / server chan) se dung im tai cho toi 3 phut sau.
    # Ca that 20/09 party 42 (user: "leader o trac quan, member o truong sa"):
    #   13:05:14 gen 20: viec=gom - ca party dam chan o THANH 12001 1095s   <- 18 phut
    #   13:05:14 ENGINE: dieu phoi bump reform_gen -> ca party thi hanh
    #   13:05:26 ENGINE: luu401..luu405 -> nghi   <- leader van 12001, member 23001
    #
    # KHONG quay vong nhu p43 16/09: `giao()` chi HUY viec dang chay khi viec DOI, ma day van la
    # `ve_thanh` voi CUNG mot dich (`chot_thanh_tap_ket` co cache). Cai gay ra p43 la dich NHAY.
    if anh.reform_moi or (anh.dp_viec == DP_GOM and anh.thanh_dich):
        _dich = int(anh.thanh_dich) if anh.thanh_dich else None
        for a in song:
            if a.username in ket:
                continue
            if _dich is not None and a.map_id == _dich:
                continue              # da ve toi noi - de yen, bat tele lai la tu pha party
            ket[a.username] = VIEC_VE_THANH
        if ket:
            return ket
    if anh.resync_moi:
        # CHI member. Leader thay doi tut nguoi thi tu sync + moi lai trong vong moi cua no.
        for a in song:
            if a.username not in ket and not a.la_leader:
                ket[a.username] = VIEC_RESYNC
        return ket

    # Chi tu quyet khi dieu phoi cu KHONG tra loi (chua du du lieu) - va ca hai duong deu ra MOT
    # viec cho CA PARTY.
    if anh.dp_viec:
        _v = DICH_VIEC.get(anh.dp_viec)
        if _v is not None:
            _du_doi = (anh.can_bao_nhieu <= 0
                       or anh.roster_leader() >= anh.can_bao_nhieu)
            for a in song:
                if a.username in ket:
                    continue           # acc dang lam viec vat - de no lam not
                if _v == VIEC_LAP_PARTY and not a.la_leader:
                    ket[a.username] = VIEC_LAP_PARTY     # member mo cua nhan (xem `thi_hanh`)
                elif (_v == VIEC_VE_MAP and anh.thanh_dich and not _du_doi
                      and a.map_id != int(anh.thanh_dich)):
                    # CHUA DU DOI ma con lac khoi diem gom -> VE DA, KE CA NGUOI KEO.
                    #
                    # `_du_doi` LA CUA BAT BUOC: du roi thi nguoi keo PHAI duoc di, va no di la
                    # roi diem gom - ep ve luc do thi thanh vong "du doi -> di -> bi keo ve -> du
                    # doi -> ..." va party KHONG BAO GIO ra toi bai.
                    # Ca that 17/09 party 42 (user: "di ve thanh tap trung dung roi, nhung sau do
                    # ko di ra bai train"):
                    #   18:46:31 gen 38: du doi, cung map/kenh -> DI TRAIN map 26811 (o [23000])
                    #   18:46:33 gen 39: con lech map [23000, 23001]   <- leader vua di, bi keo ve
                    #   18:46:34 gen 40: cung map/kenh nhung DOI chua du
                    #
                    # Flow cu bat MOI acc ve `_target_city` truoc roi moi di tiep:
                    #     _target_city = _gc if _nghiep_fallback_active() else fc
                    # Cho nguoi keo di thang thi no bo party lai: leader da o thanh cua route
                    # (no mo duoc), member thi chua mo nen dung o thanh gom - leader cu the chay
                    # ra bai mot minh.
                    # Ca that 17/09 party 45 (nhanh "thanh chua mo" DA chay dung):
                    #   10:00:01 ENGINE: thanh 15021 CHUA MO voi [cd702..cd705] -> gom o 18021
                    #   10:00:24 chdumot@15021(L) chduhai@18021 chduba@18021 chdubon@18021 ...
                    ket[a.username] = VIEC_VE_THANH
                elif _v == VIEC_VE_MAP and not _duoc_di_duong(anh, a):
                    # CHI NGUOI KEO duoc LAP DUONG di bai train - xem `anh.nguoi_keo`. Giao `ve_map`
                    # cho ca party thi moi acc tu chay route, tu `pre_route_town_hop` boc thanh
                    # rieng -> party chia doi (p44 17/09).
                    #
                    # NHUNG "khong duoc lap duong" KHONG phai "dung im": flow cu van bat member VE
                    # THANH TAP KET (reform -> `go_to_town(route_plan["city"])`), roi leader moi keo
                    # ca doi qua cong. Cho member `nghi` o day thi no nam luon tai thanh cu:
                    # ca that 17/09 p45 09:26:55 - leader DA toi Tho Xuan (15021, thanh cua route)
                    # ma bon member van dung Hoi Ke (18021), roster 0/4 mai.
                    # DU DOI ROI thi member DI THEO LEADER (game keo qua cong) -> DUNG YEN.
                    # Bat no ve thanh luc nay la cat ngang chuyen di: ca party dang tren duong ra
                    # bai, member thi teleport nguoc ve thanh - ma teleport con ROI DOI.
                    # Ca that 17/09 party 56 (user: "sao vua danh vua doi tele ve thanh la sao"):
                    #   19:43:43 gen 20: du doi -> DI TRAIN map 11801 (con o [11539])  roster 4/4
                    #   19:43:54 ENGINE: tik907..tik910 -> ve_thanh   <- dang di giua duong
                    #   19:43:58 gen 21: ... (con o [11532])          <- van dang di
                    # CHUA CHOT DUOC THANH DICH -> NGHI, khong giao `ve_thanh`. Lenh ve thanh ma
                    # khong co thanh nao la LENH RONG (L3: lenh phai co MUC TIEU DO DUOC):
                    # `thi_hanh` gap `dich=None` la `return False` NGAY -> engine giao lai moi
                    # giay, mai mai.
                    # Ca that 21/09 party 5: 've_thanh' giao lai 4320 lan lien tiep (04:02 ->
                    # 05:15, hon MOT TIENG) trong khi party lech map [21011, 21881], roster 0/4.
                    # Party 3 cung the (3780 lan).
                    ket[a.username] = (VIEC_NGHI
                                       if (_du_doi or not anh.thanh_dich
                                           or a.map_id == int(anh.thanh_dich))
                                       else VIEC_VE_THANH)
                else:
                    ket[a.username] = _v
            return ket



    # PHEP DO TINH TREN `con_lai` - acc vua duoc giao viec vat o NHIP NAY da bi loai roi.
    #
    # `anh.maps()` doc `viec_dang_lam` = viec cua nhip TRUOC, nen acc vua nhan `login_chore` o nhip
    # nay van bi dem vao -> party "lech map" gia va ca lu bi keo di theo no.
    maps = sorted({a.map_id for a in con_lai if a.map_id is not None})
    # (1) LECH MAP -> dong bo map. Chua biet map cua ai do (None) cung phai cho, khong ket luan.
    if len(maps) > 1 or any(a.map_id is None for a in con_lai):
        dich = anh.map_dich if anh.map_dich in maps else _map_dich(anh, con_lai, maps)
        for a in con_lai:
            ket[a.username] = VIEC_NGHI if a.map_id == dich and dich is not None else VIEC_VE_MAP
        return ket

    # (2) CUNG MAP roi -> moi xet KENH (user chot: "dong bo map xong moi xem den kenh").
    kenhs = sorted({a.kenh for a in con_lai if a.kenh})
    if len(kenhs) > 1:
        dich = kenhs[0]
        for a in con_lai:
            ket[a.username] = VIEC_NGHI if a.kenh == dich else VIEC_DOI_KENH
        return ket

    # (3) Cung map + cung kenh -> LAP PARTY neu chua du.
    #
    # NHUNG CHI LAP O THANH TAP KET HOAC MAP TRAIN (luat cu, user chot 13/09). Dang o THANH DI
    # NGANG QUA thi di tiep da: buoc ngay sau la TELEPORT, ma teleport bat buoc `leave_party()`
    # -> party vua lap lai tan, ca chuoi quay lai tu dau.
    #
    # Ca that party 4, 13/09 (user: "p4, bon no lap pt o Trac quan lam lon gi the") va party 41
    # 16/09 tren engine moi (user: "party 41 dung lap party o Trac quan"): ban dau engine moi chi
    # hoi "cung map chua", nen ca party dung o thanh cung duoc coi la "cung map" roi lap party
    # ngay tai do.
    # CHUA DU ACC LOGIN XONG -> CHUA duoc ket luan "cung map/kenh", va DUNG lap party.
    #
    # Phep dem map/kenh chi nhin acc DANG SONG, nen khi mot dua chua vao world thi "ca party cung
    # map/kenh" la ket luan tren mau khong day du - dua chua login co the o kenh khac han. Lap doi
    # luc nay la lap thieu nguoi, roi dua kia vao lai phai gom lai tu dau.
    #
    # Flow cu co san cua nay: `_thieu_acc_song` (goi trong `_dieu_phoi_quyet`, ra `VIEC_LAM`) -
    # engine moi hoi lai qua `thieu_acc_song`, KHONG tu dem. Ham do da lo ca "acc TAT han thi
    # khong cho" (cho mot acc da tat la cho vinh vien).
    #
    # Ca that 20/09 party 55 (user: "ca party chua cung map cung kenh ma da lap party"):
    #   12:31:20 ENGINE: tik901/903/904/905 -> lap_party    <- tik902 CHUA vao world
    #   12:33:00 [tik902] === GOI GAN NHAT TRUOC KHI ROT (server dong) ===
    #   12:33:17 [tik902] chua vao world - SERVER CHAN TOC DO DANG NHAP (lan 1)
    if anh.thieu_acc_song:
        for a in con_lai:
            ket[a.username] = VIEC_NGHI
        return ket

    if anh.can_bao_nhieu > 0 and anh.roster_leader() < anh.can_bao_nhieu:
        if anh.thanh_di_ngang:
            for a in con_lai:
                ket[a.username] = VIEC_VE_MAP      # di tiep toi dich roi moi lap party
            return ket
        for a in con_lai:
            ket[a.username] = VIEC_LAP_PARTY
        return ket

    # (4) Du doi, cung map cung kenh -> RA BAI QUAI roi moi danh.
    #
    # Ca that 14/09 (user: "vay la dang o thanh, thay vi chay ra map train may lai tinh la dang o
    # map train va chay ra spot a"): "du party" KHONG co nghia la "dung yen danh o bat cu dau".
    # Chua co tam bai quai thi dung yen cho leader chot, dung bat combat giua thanh.
    if not anh.co_spot:
        for a in con_lai:
            ket[a.username] = VIEC_NGHI
        return ket
    for a in con_lai:
        ket[a.username] = VIEC_TRAIN if a.viec_dang_lam == VIEC_TRAIN else VIEC_RA_SPOT
    return ket


# ---------------------------------------------------------------- worker (thi hanh viec CHAN)

class AccWorker:
    """MOT thread moi acc, chi lam MOT viec tai mot thoi diem, va HUY duoc giua chung.

    Vi sao van can thread rieng thay vi "mot thread lam tat": mot acc mat goi se lam dung ca nhip
    cua party, va mot exception giet luon 5 acc. Tach ra thi giu duoc cach ly loi cua engine cu
    (ca that 15/09: `luumuoi` treo nhung `luusau` van reform deu 8 lan).

    Viec = goi THANG ham co san trong `GameClient` (`do_daily_dungeon`, `enter_di_gioi_safe`,
    `navigate_to`, `switch_channel`...). KHONG viet lai thao tac game - 3030 test dang phu chung.
    """

    def __init__(self, username, client, lam_viec, ve_safe_khi_stop=None, log=None,
                 nhip_acc=None):
        self.username = username
        self.client = client
        self._lam_viec = lam_viec          # (client, viec, huy_fn) -> None
        self._viec = VIEC_NGHI
        self._viec_moi = None
        self._huy = threading.Event()
        self._lock = threading.Lock()
        self._th = None
        self._dung = threading.Event()
        self._nen_dung = None
        self._nhip_acc = nhip_acc   # (client) -> None : nhip keepalive per-acc
        self._dang_ban = False           # dang chay mot viec CHUA XONG
        self._ve_safe_khi_stop = ve_safe_khi_stop
        self._log = log
        self.loi_cuoi = None

    # -- engine goi --
    def giao(self, viec):
        """Giao viec MOI. Viec cu (neu khac) bi HUY - khong xep hang, vi lenh moi luon dung hon.

        SO VOI VIEC MOI NHAT DA XEP (`_viec_moi`), khong chi so voi viec DANG CHAY (`_viec`).
        Worker co the dang KET trong mot viec chan dai (login chores, di duong, PB) nen `_viec` con
        la viec cu hang phut sau khi da xep viec moi. So nham thi MOI NHIP engine lai tuong "viec
        doi" -> set `_huy` lien tuc -> moi viec chan vua bat dau la bi abort ngay.

        Ca that 16/09 party 41 (user: "p41 van dung o trac quan mai"):
            15:52:29 ENGINE: dt806 -> lap_party
            15:52:30 ENGINE: dt806 -> ve_map
            15:52:31 ENGINE: dt806 -> ve_map     <- giao LAI moi giay
            15:52:34 ENGINE: dt806 -> ve_map
        Acc dung nguyen mot cho ca ngay vi khong viec nao song qua duoc mot giay.
        """
        with self._lock:
            _hien = self._viec_moi if self._viec_moi is not None else self._viec
            if viec == _hien:
                return False
            self._viec_moi = viec
            self._huy.set()        # bao viec dang chay dung lai
            return True

    def viec_hien_tai(self):
        with self._lock:
            return self._viec

    def dang_ban(self):
        """Dang chay mot viec CHUA XONG. Engine doc no de KHONG ra lenh de len.

        Chay chung mot luong ma van khong biet acc lam xong viec truoc chua thi moi nhip lai tinh
        lai tu dau va ra lai dung cai lenh do - viec bi giao lai/huy lien tuc, acc dung yen mai
        (user 16/09: "chung 1 thread roi ma bot ko biet acc da lam xong viec truoc do chua").
        """
        return bool(self._dang_ban)

    def start(self):
        """Tao thread RIENG cho worker. Chi dung trong test.

        Ban chay THAT dung `chay_o_day()`: thread cua acc (supervisor) von chi nam ngu cho acc
        chet, de no lam worker luon thi engine moi KHONG THEM mot thread nao - dung muc tieu.
        Do tren may that 15/09: 799 thread, 798 cai ngoi tranh GIL, main thread Tk doi -> GUI
        "not responding". Them 62 worker nua la di nguoc chinh cai dang chua.
        """
        if self._th is not None and self._th.is_alive():
            return
        self._dung.clear()
        self._th = threading.Thread(target=self._vong, name="worker-%s" % self.username,
                                    daemon=True)
        self._th.start()

    def chay_o_day(self, nen_dung=None):
        """Chay vong worker TREN THREAD DANG GOI (thread cua acc). Khong de ra thread moi.

        `nen_dung()` = acc bi STOP / rot / client chet -> NHA THREAD RA cho supervisor. Thieu no
        thi worker cu quay tiep sau khi acc da bi tat: mode `digioi` thuan goi `stop_account` roi
        ma thread van song, acc khong bao gio dung han.
        """
        self._dung.clear()
        self._nen_dung = nen_dung
        self._vong()
        # STOP -> VE SAFE ROI MOI DONG, y flow cu (`run_account` dong 7207-7229):
        #   LEADER train  : chay ve safe GAN NHAT roi bao `stop_leader_done`
        #   member train  : CHO leader ve safe (toi da 60s) roi moi thoat
        # De acc dung ngay tai bai quai thi lan login sau vao la bi danh ngay.
        if self._ve_safe_khi_stop is not None:
            try:
                self._ve_safe_khi_stop(self.client)
            except Exception:
                pass

    def stop(self):
        self._dung.set()
        self._huy.set()

    # -- than worker --
    def _vong(self):
        while not self._dung.is_set():
            if self._nen_dung is not None:
                try:
                    if self._nen_dung():
                        return          # acc STOP/rot -> tra thread cho supervisor
                except Exception:
                    pass
            with self._lock:
                moi, self._viec_moi = self._viec_moi, None
                if moi is not None:
                    self._viec = moi
                viec = self._viec
            self._huy.clear()
            # NHIP KEEPALIVE cua acc - chay CA khi dang nghi.
            #
            # `run_account` co vong keepalive 1080 dong chay lien tuc ben canh viec chinh; engine
            # moi bo han vong do nen MAT SACH viec chay dinh ky trong no (qua online, co Hop May,
            # tra pet ve vai thuong, boss quan doan). Soi bang AST 20/09: keepalive goi 34 method
            # cua client, engine moi thieu 18 (user: "t da bao tu soi code xem cai nao flow cu co
            # ma engine moi ko co").
            #
            # Dat o DAY (truoc ca nhanh `nghi`) vi phan lon thoi gian acc o trang thai nghi/train.
            # Cac ham ben trong deu TU KIEM truoc khi gui goi nen goi moi nhip la re.
            if self._nhip_acc is not None:
                try:
                    self._nhip_acc(self.client)
                except Exception as e:
                    self.loi_cuoi = e
                    if self._log is not None:
                        self._log.debug("[%s] ENGINE: nhip acc loi (bo qua): %s", self.username, e)
            if viec in (None, VIEC_NGHI):
                time.sleep(0.2)
                continue
            _t0 = time.time()
            self._dang_ban = True
            try:
                self._lam_viec(self.client, viec, self._con_lam)
            except Exception as e:      # mot viec loi KHONG duoc giet worker: nhip sau giao lai
                self.loi_cuoi = e
                # PHAI LOG. Truoc day chi luu vao `loi_cuoi` roi im -> acc lap lai mot viec loi
                # hang tieng ma khong mot dong nao bao (party 41, 16/09: `dtsau` im 73 phut sau
                # khi nhan `ve_map`). Im lang la benh nang nhat cua engine cu, engine moi khong
                # duoc phep tai lap.
                if self._log is not None:
                    self._log.warning("[%s] ENGINE: viec '%s' LOI: %s",
                                      self.username, viec, e)
                self._dang_ban = False
                time.sleep(0.5)
                continue
            # NGU BU CHO DU MOT NHIP - KHONG DUOC QUAY NONG.
            #
            # Viec CHAN (di duong, danh PB) an het nhieu giay nen doan nay khong lam cham gi. Nhung
            # `train` / `pb_doi_theo` / `viec_vat` TRA VE NGAY LAP TUC (chi set co roi return), va
            # khong co doan nay thi vong quay vai nghin lan/giay: 62 worker = 62 vong nong an sach
            # CPU, main thread Tk doi -> GUI "not responding" (do that 15/09, lan chay thu thu hai).
            #
            # Repo nay da dinh dung kieu do mot lan (L10, p5 13:15-13:20): "mot vong nong cua acc
            # `continue` khong ngu -> 8.000 vong/giay -> bo doi luong dieu phoi -> ke hoach dong
            # bang 5 phut".
            # XONG VIEC -> NGHI, CHO LENH MOI. Khong tu chay lai chinh viec do.
            #
            # Truoc day `_viec` giu nguyen nen vong sau lam lai y het: chores chay xong la bat dau
            # lai ngay, va vi luc nao cung "dang ban" nen engine KHONG BAO GIO giao duoc viec moi.
            # Ca that 16/09 party 41 (user: "p41 lai dung o trac quan, ko lam gi ca"):
            #   16:49:19 XONG viec vat sau login
            #   16:49:19 bat dau viec vat sau login   <- lap lai ngay
            #   16:49:25 XONG / 16:49:26 bat dau ...
            # Dieu kien chua doi thi nhip sau engine giao lai chinh viec do - do la viec cua ENGINE,
            # khong phai cua worker.
            with self._lock:
                if self._viec_moi is None:
                    self._viec = VIEC_NGHI
            self._dang_ban = False
            _con = NHIP_WORKER_SEC - (time.time() - _t0)
            if _con > 0:
                self._huy.wait(_con)      # co lenh moi -> day ngay, khong phai cho het nhip

    def _con_lam(self):
        """Truyen xuong thao tac chan lam `abort=`: co lenh moi / bi dung / ACC BI STOP -> nha ngay.

        `nen_dung()` PHAI co o day, khong chi o dau vong: viec chan co the dai hang chuc phut
        (di duong, danh PB to doi). Thieu no thi user bam "Stop tat ca" ma acc engine moi van chay
        het viec roi moi dung - nhin nhu KHONG TAT (user 16/09).
        `client.py` da co san duong nay (`navigate_to(..., abort=...)`).
        """
        if self._huy.is_set() or self._dung.is_set():
            return False
        if self._nen_dung is not None:
            try:
                if self._nen_dung():
                    return False
            except Exception:
                pass
        return True


# ---------------------------------------------------------------- anh xa viec -> ham THAT
#
# KHONG viet lai thao tac game: moi viec goi thang ham co san trong `GameClient`, thu da chay that
# hang thang va duoc 3030 test phu. Engine moi chi doi CACH RA LENH, khong doi cach lam.


def _sau_khi_vao_dg(client, log=None):
    """Y FLOW CU (`run_account` dong 5616-5622) ngay sau khi vao Di Gioi.

    `befriend_nearby()` KHONG phai viec phu: loi moi PHONG PB di theo roleId tu friend-list
    (KNOWLEDGE.md - "can cache `name -> roleId` tu nguon nay de PB whitelist moi duoc acc o xa").
    Bo no thi PB to doi co luc khong moi duoc ai.
    """
    for _ten, _args in (("claim_daily_quests", {"heavy": False}), ("befriend_nearby", {})):
        _ham = getattr(client, _ten, None)
        if _ham is None:
            continue
        try:
            _ham(**_args)
        except Exception as e:
            if log is not None:
                log.warning("[%s] ENGINE: %s loi (bo qua): %s",
                            getattr(client, "_label", "?"), _ten, e)


def thi_hanh(client, viec, con_lam, dich=None, log=None, moi_party=None, thoat_acc=None,
             duong_ra_spot=None, chay_pb_doi=None, ho_phu=None, cap_dg=None, chore_fn=None,
             safe_dich=None, kenh_doi_duoc=None, xe_dich=None, ghi_thong_ke=None,
             vao_event=None, danh_event=None, doi_thuong=None, fc_gom=None, fc_buoc_fn=None,
             lenh_tay_fn=None, fc_di_bo=None,
             la_thanh=None, daily_fn=None):
    """Lam mot viec. `con_lam()` False = co lenh moi -> NHA RA ngay (khong lam not).

    `abort=` la duong huy da co san trong `client.py`; day la ly do engine moi khong can vong cho:
    lenh moi khong phai "doi acc nghe thay", ma la CAT NGANG viec dang lam.
    """
    _abort = lambda: not con_lam()
    if viec == VIEC_RESYNC:
        # RESYNC (tu `dong_bo`): member ROI PARTY + sync kenh lai NGAY TAI CHO, roi cho leader moi
        # lai. LAM Y engine cu (`run_account`, nhanh `st["resync_gen"] > resync_gen_handled`).
        #
        # CUA CHAN BAT BUOC: minh DA o trong party roi thi BO QUA. Muc dich cua resync la cuu ca
        # "leader moi mai khong ai vao"; voi dua DA VAO thi lenh do vo nghia, roi ra la TU PHA cai
        # vua lap. Bug that party 15 (06/09): 4 member doc co resync cham 4 giay -> roi party VUA
        # LAP -> leader danh mot minh, ket o cong, ra khoi thap.
        try:
            if bool(getattr(client, "party_members", None) or getattr(client, "party_leader", None)):
                return True
        except Exception:
            pass
        try:
            client.leave_party()
        except Exception:
            pass
        # Roi doi xong moi doi duoc kenh (server cam doi kenh khi con trong doi, tra result=3).
        if dich is not None and int(getattr(client, "current_channel", 0) or 0) != int(dich):
            if kenh_doi_duoc is not None and not kenh_doi_duoc(client):
                return False
            try:
                client.switch_channel(int(dich), wait=4.0, retries=1, theo_lenh=True)
            except Exception:
                return False
        client.flee_mode = False
        return True
    if viec == VIEC_VE_THANH:
        # GOM = TELEPORT VE THANH TAP KET, khong phai di bo qua cong.
        #
        # Engine cu: `_do_reform` -> `_chot_thanh_tap_ket` -> `go_to_town`. Ban dau engine moi lay
        # `kh["map"]` cua dieu phoi lam dich va goi `follow_smart_route` - nhung `kh["map"]` chi la
        # MAP DONG NGUOI NHAT (thong tin trang thai), KHONG phai dich de di. Ket qua: moi acc di
        # mot noi, hoac di toi chinh cho dang dung roi tra ve ngay.
        # Ca that 16/09 party 41 (user: "dua thi o trac quan, dua thi o giang dong"):
        #   18:43:38 dieu phoi chot 'gom' - party dang o 2 MAP khac nhau [12001, 18000]
        #   18:45:01..18:45:13 ENGINE: dt806..dt810 -> ve_map   (lap moi ~10 giay)
        # `dich` = (city_id, flag). FLAG LA BAT BUOC: moi thanh mot flag rieng
        # (`config.TELEPORT_CITIES[city]["flag"]`) - Trac Quan 0, Nghiep Thanh 2, Cu Loc 3,
        # Bac Hai 1, Kien Nghiep 9... Truyen thieu la bay ve NHAM THANH.
        # Ca that 16/09 party 41 (user: "deo gi ma tele lien tuc lai con bi sai flag").
        if not dich:
            return False
        _city, _flag = (int(dich[0]), int(dich[1])) if isinstance(dich, (tuple, list))             else (int(dich), 0)
        if int(getattr(client, "current_map", 0) or 0) == _city:
            return True
        # TELE TRUNG GIAN TRUOC (Trac Quan / Ng.Thanh - `pre_route_town_hop`), roi moi tele thanh
        # tap ket. User bao tu lau: "bay ve thanh route truc tiep tu map la hay bi loi ngay doan
        # tele; qua 1 thanh trung gian truoc thi on dinh" - va `follow_smart_route` van lam dung
        # nhu the truoc moi chuyen di.
        #
        # Duong nay thi truoc 21/09 goi THANG `go_to_town`, nen party engine moi bay mot phat ve
        # thanh gan bai train (user 21/09: "Party 21, t thay no bay ve thanh gan bai train nhat
        # de party di ra bai train, ko co pre tele ve Trac quan/Nghiep thanh").
        #
        # DIEU KIEN LA "DICH LA THANH NAO", khong phai "dang dung o dau" - dung y engine cu:
        #     if _target_city == fc:      # fc = THANH TAP KET (thanh cua route)
        #         c.pre_route_town_hop()  # -> CO hop
        #     else:                       # ve thanh GOM du phong (Nghiep Thanh)
        #         ...                     # -> KHONG hop
        # Ve chinh mot trong hai thanh trung gian thi hop lam gi nua - do la them mot lan tele.
        try:
            if int(_city) not in _PRE_ROUTE_CITY_IDS:
                client.pre_route_town_hop()
        except Exception as e:
            if log is not None:
                log.debug("[%s] ENGINE: pre-route truoc khi ve thanh loi (bo qua): %s",
                          getattr(client, "_label", "?"), e)
        _ok = bool(client.go_to_town(_city, _flag))
        # TELE XONG MA MAP KHONG DOI -> bao that bai de nhip sau khong tele lai vo tan.
        # `go_to_town` co the tra True trong khi server chua doi map (thanh chua mo, dang trong
        # tran...). Khong kiem thi acc tele lien tuc.
        return _ok and int(getattr(client, "current_map", 0) or 0) == _city
    if viec == VIEC_VE_MAP:
        if dich is None or int(getattr(client, "current_map", 0) or 0) == int(dich):
            return True
        # THANH CUA ROUTE CHUA MO -> KEO CA PARTY DI BO TOI DO TRUOC.
        #
        # `follow_smart_route` bat dau bang `go_to_town(route["city"])`, ma thanh chua mo thi
        # `go_to_town` bo cuoc ngay ("thanh %s CHUA MO tele -> bo qua ngay") - acc nam lai thanh cu
        # vinh vien. Flow cu goi buoc di bo nay truoc (`_reform_via_nghiep`):
        #     c.follow_smart_scene_route(c.current_map, fc, None, abort=_ab, flee=not _full)
        # Member trong party TU FOLLOW qua cong (game keo theo leader), nen chi nguoi keo lam buoc
        # nay - va di xong thi ca party da o thanh gan bai, tu do route binh thuong.
        if fc_di_bo and int(getattr(client, "current_map", 0) or 0) != int(fc_di_bo):
            if log is not None:
                log.info("[%s] ENGINE: thanh %s chua mo -> KEO party DI BO toi do truoc",
                         getattr(client, "_label", "?"), fc_di_bo)
            try:
                _ok = client.follow_smart_scene_route(
                    int(getattr(client, "current_map", 0) or 0), int(fc_di_bo), None,
                    abort=_abort, flee=False)
            except Exception:
                _ok = False
            if not _ok or int(getattr(client, "current_map", 0) or 0) != int(fc_di_bo):
                if log is not None:
                    log.warning("[%s] ENGINE: keo di bo toi thanh %s that bai (map=%s, ly do=%s) "
                                "-> de dieu phoi ra lenh gom lai",
                                getattr(client, "_label", "?"), fc_di_bo,
                                getattr(client, "current_map", None),
                                getattr(client, "_smart_route_failure", None) or "khong ro")
                return False
        # LAM Y FLOW CU (`_do_reform`, dong 4356 + 4732): BUILD ROUTE TRUOC, co route moi di, va
        # truyen SAFE DICH - khong goi `follow_smart_route` tran.
        #
        # Goi tran thi khi router khong dung duoc duong, acc di mu va KET trong do. Ca that
        # 16/09 party 41: ca 5 acc nhan `ve_map` luc 12:23:38 roi IM 73 PHUT, khong mot dong log.
        _safe = safe_dich[0] if safe_dich else None
        # DANG O GIUA DUONG (khong dung trong thanh teleport nao) -> DI TIEP TU DAY, dung quay lai.
        #
        # `follow_smart_route` LUON bat dau bang `go_to_town(route["city"])`, tuc quay ve THANH cua
        # route roi di lai tu dau - ma teleport bat buoc ROI DOI. Nen chi can viec bi giao lai mot
        # lan giua chuyen di la leader lon nguoc ve thanh va party vo.
        #
        # Ca that 17/09 party 51 (user: "p51, leader va member lai lech map"):
        #   20:43:24 gen 15: du doi -> DI TRAIN map 18822 (con o [18001])   <- ca party o thanh
        #   20:43:38 gen 16: ...                          (con o [18000])   <- da qua 1 cong
        #   20:44:00 [mhmmot] PARTY: ... roster con 0 nguoi                 <- leader ROI DOI
        #   20:44:02 [mhmmot] Teleport -> city 12001 -> 18001               <- quay NGUOC ve thanh
        # `follow_smart_scene_route` la duong DI BO tu map hien tai - chinh ham flow cu dung de keo
        # party qua cong (`_reform_via_nghiep`).
        #
        # NHUNG chi khi DANG GIUA CHUYEN. Acc VUA LOGIN o mot bai train/map la thi di bo thang
        # sang bai dich la sai duong: flow cu teleport ve thanh TRUNG GIAN (Trac Quan/Ng.Thanh -
        # `pre_route_town_hop`) roi tele thanh TAP KET roi moi di bo ra bai.
        #
        # Ca that 21/09 party 21 (user: "login vao thi ca party dang o trai pham thanh 3, bai
        # train la dam lay tang khau 4 -> sao no ko tele ve thanh gan nhat roi di"):
        # login tai 21814, dich 21844 - ca hai deu KHONG phai thanh, nen cua `not la_thanh(_cur)`
        # cho di bo thang, keo ca party loi bo qua ca vung map.
        #
        # `_pe_dang_di_route` do chinh buoc `follow_smart_route` ben duoi bat len: co no = da
        # xuat phat tu thanh route, dang do duong -> luc do di bo tiep moi dung.
        _cur = int(getattr(client, "current_map", 0) or 0)
        if (_cur and la_thanh is not None and not la_thanh(_cur)
                and getattr(client, "_pe_dang_di_route", False)):
            try:
                if client.follow_smart_scene_route(_cur, int(dich), _safe,
                                                   abort=_abort, flee=True):
                    client._pe_dang_di_route = False
                    return True
            except Exception:
                pass
            if log is not None:
                log.info("[%s] ENGINE: di bo tu map %s toi %s khong duoc -> quay ve thanh di lai",
                         getattr(client, "_label", "?"), _cur, dich)
        try:
            _rt = client.build_smart_route(int(dich), _safe)
        except Exception:
            _rt = None
        if not _rt:
            if log is not None:
                log.warning("[%s] ENGINE: KHONG dung duoc duong toi map %s -> khong di mu",
                            getattr(client, "_label", "?"), dich)
            return False
        # DA XUAT PHAT tu thanh route -> tu day neu viec bi giao lai giua chuyen thi duoc DI BO
        # TIEP (cua o tren), khong quay nguoc ve thanh (p51, 17/09).
        client._pe_dang_di_route = True
        _xong = bool(client.follow_smart_route(int(dich), _safe, abort=_abort, flee=True))
        if _xong:
            client._pe_dang_di_route = False
        return _xong
    if viec == VIEC_DOI_KENH:
        if dich is None or int(getattr(client, "current_channel", 0) or 0) == int(dich):
            return True
        # BA MOC AN TOAN TRUOC KHI DOI KENH - hoi `_kenh_doi_duoc_ngay` cua engine cu.
        #
        # Doi kenh = doi INSTANCE. Gui giua tran thi server BO QUA ma bot tuong da doi; gui giua
        # event thi keo theo `scene_resume` -> `C:020-006` luc server chua giai xong tran ->
        # `S:000-000` ma 47 -> DUT KET NOI (07/09: nam acc dis trong 32 giay).
        # Ba moc: `event_battle_active` | `state.in_battle` | grace ket tran.
        if kenh_doi_duoc is not None and not kenh_doi_duoc(client):
            return False
        # `theo_lenh=True`: bao client day la LENH DIEU PHOI, khong phai acc tu doi (engine cu luon
        # truyen co nay - thieu no thi client xu ly khac han).
        return bool(client.switch_channel(int(dich), wait=4.0, retries=1, theo_lenh=True))
    if viec == VIEC_LAP_PARTY:
        # Leader moi, member mo cua nhan. Member KHONG tu moi ai (L1) va cung khong tu roi doi.
        if not getattr(client, "_pe_la_leader", False):
            client.set_party_invite_ready(True)
            return True
        # GOI THANG `_invite_party_participants` cua engine cu (truyen vao qua `moi_party`).
        #
        # KHONG chep lai logic cua no. Ham do da co: moi WHITELIST truoc roi bot member sau, hai
        # duong khac nhau cho map train / cho khac, va `_leader_tu_kiem_kenh` truoc khi moi - "cua
        # duy nhat ma leader di qua khi moi party (8 cho goi toi)".
        # Chep lai la lech dan: ban chep dau tien cua engine moi da quen ca whitelist lan kiem kenh.
        if moi_party is None:
            return False
        try:
            _trong_dg = bool(client.in_di_gioi())
        except Exception:
            _trong_dg = False
        moi_party(client, not _trong_dg)      # train_on_map=False khi dang trong Di Gioi
        # DAT QUAN SU sau khi moi (engine cu goi `set_party_strategist` 6 cho). Thieu buoc nay thi
        # party khong co quan su -> mat buff/chi huy tran.
        try:
            client.set_party_strategist()
        except Exception:
            pass
        return True
    if viec == VIEC_DI_GIOI:
        # LAM Y FLOW CU (`run_account`, nhanh `elif is_digioi`, dong 5473-5560):
        #   1. Ho Phu khi con < 15 phut   -> `_maybe_use_di_gioi_ho_phu`
        #   2. DAT CAP QUAI DG            -> `c.set_di_gioi_level(_doc_cap_dg(pidx))`
        #   3. vao DG                     -> `enter_di_gioi_safe`
        # Bo buoc 2 la ca party danh cap quai MAC DINH thay vi cap user chon; bo buoc 1 la mat
        # duong keo dai gio DG.
        _cfg = getattr(client, "_pe_pcfg", None) or {}
        if _cfg.get("use_digioi_ho_phu") and ho_phu is not None:
            try:
                ho_phu(client)
            except Exception as e:
                if log is not None:
                    log.warning("[%s] ENGINE: Ho Phu loi (bo qua): %s",
                                getattr(client, "_label", "?"), e)
        if cap_dg:
            try:
                client.set_di_gioi_level(int(cap_dg))
            except Exception:
                pass
        # `enter_di_gioi_safe` da tu doc `S:097-001` va gian ra khi server im (sua 15/09) - khong
        # duoc ban lai o day, ban day chinh la thu da lam 264 acc-lan `VAO DI GIOI THAT BAI`.
        _vao = bool(client.enter_di_gioi_safe())
        if _vao:
            _sau_khi_vao_dg(client, log=log)     # y flow cu: claim nhe + befriend (PB moi theo roleId)
        return _vao
    if viec == VIEC_LOGIN_CHORE:
        return lam_viec_vat(client, log=log, con_lam=con_lam, chore_fn=chore_fn)
    if viec == VIEC_DAILY:
        return lam_nhiem_vu_ngay(client, log=log, con_lam=con_lam, daily_fn=daily_fn)
    if viec == VIEC_PB_DOI:
        # DOC THANG, KHONG CHO AI BAO CAO (L2).
        #
        # Lop `_handle_auto_team_dungeon` cua engine cu co barrier dua tren bao cao: moi acc tu gan
        # `_o5_da_xong` len client, leader doc dau vet do. Voi engine moi co che do vua thua (mot
        # luong nam ca 5 client - doc thang la biet) vua HONG (khong acc nao chay nhanh gan dau vet
        # => leader BO PB moi luot, member ket o `pb_doi_theo`).
        # Ca that 16/09 party 41: quay vong 6 giay/lan tu 09:34, khong danh tran nao.
        #
        # "Con luot hay khong" da doc tu DONG HO SERVER (`team_dungeon_remaining` <- `mission_steps`
        # <- `0x18 sub 06`) - chinh xac hon bao cao giua cac acc.
        #
        # Chan 10-20 phut la BINH THUONG - 5 tran + di duong + thoai. KHONG dat han cho o day:
        # engine cu tung co watchdog 180s va no da keo CA 4 MEMBER ra relogin GIUA pho ban.
        if dich is None:
            return True
        if chay_pb_doi is None:
            return bool(client.do_team_dungeon(int(dich)))
        return bool(chay_pb_doi(client, int(dich)))
    if viec == VIEC_PB_DOI_THEO:
        # Member KHONG dung toi cua party THUONG o day: loi moi phong PB di duong rieng
        # (`0x2f/0f00`) va `_on_dungeon` da TU accept + ready khi `auto_accept_party` bat.
        # Goi `set_party_invite_ready(True)` o day la mo nham cua - vua khong giup gi cho PB, vua
        # cho loi moi party thuong lot vao giua luc dang cho phong PB.
        client.auto_accept_party = True
        client.flee_mode = True      # dung danh le trong luc cho leader keo vao phong
        return True
    if viec == VIEC_RA_SPOT:
        if dich is None:
            return False
        client.flee_mode = False      # du party -> keo ra spot phai DANH bat chap, khong flee
        # LEADER co DUONG CAPTURE (`MOB_PATHS`) thi di theo duong do de KEO CA PARTY, khong
        # navigate thang: bai quai xa thi duong thang di xuyen vung quai, va member khong duoc keo.
        # Engine cu: "sau khi LAP PARTY xong, _start_training moi cho leader follow_path KEO CA
        # PARTY (da join, dang o rally) ra spot".
        # `flee=False` LA BAT BUOC (engine cu: `c.follow_path(path, flee=False, abort=_abs)`).
        # Party da du -> keo ra spot phai DANH bat chap; de flee mac dinh True thi acc bo chay moi
        # lan gap quai va khong bao gio toi noi.
        _duong = duong_ra_spot if getattr(client, "_pe_la_leader", False) else None
        if _duong:
            try:
                return bool(client.follow_path(_duong, flee=False, abort=_abort))
            except Exception:
                pass                  # khong di duoc duong capture -> roi xuong navigate thang
        # XE DICH toa do +-10 (`_jitter` cua engine cu): ca party navigate y het mot diem thi chung
        # chong len nhau. Engine cu luon `navigate_to(*_jitter(spot), ...)`.
        _x, _y = int(dich[0]), int(dich[1])
        if xe_dich is not None:
            try:
                _x, _y = xe_dich((_x, _y))
            except Exception:
                pass
        _ok = bool(client.navigate_to(_x, _y, flee=False, abort=_abort))
        if _ok and con_lam():
            # Bat ghi nhan THONG KE CHAN o tam quai nay (engine cu: `_set_train_block_stats_spot(
            # spot, enabled=True)` ngay truoc `combat_ready`). Thieu thi bang thong ke train
            # khong co so lieu cua party engine moi.
            if ghi_thong_ke is not None:
                try:
                    ghi_thong_ke((int(dich[0]), int(dich[1])), True)
                except Exception:
                    pass
            # TOI NOI LA DANH LUON, khong cho nhip sau doi sang `VIEC_TRAIN`.
            #
            # `viec_dang_lam` trong anh chup la VIEC DUOC GIAO, khong phai "da toi noi". Neu bat
            # nhip phai doi viec thi engine se giao `ra_spot` mai mai va acc dung im tai bai quai -
            # cung ho voi vong `login_chore` <-> `viec_vat` da thay o lan chay dau (15/09).
            try:
                client.combat_ready()
            except Exception:
                pass
        return _ok
    if viec == VIEC_TRAIN:
        client.flee_mode = False
        try:
            client.combat_ready()
        except Exception:
            pass
        # TRONG DI GIOI PHAI CHAY LONG VONG TIM QUAI.
        #
        # Quai trong DG khong tu toi: engine cu goi `start_run_around()` o moi duong vao DG
        # (run_party_digioi.py:5941/5964/6049/6357 - "DG: chay long vong tim quai"). Thieu no thi
        # ca party dung im giua Di Gioi, `combat=False` mai.
        # Do that 16/09 party 41: `dtmot` (LEADER) + `dthai` dung yen o map 49942, party 4/4,
        # pos khong doi suot hang phut (user: "p41 dung o quang truong").
        try:
            if client.in_di_gioi():
                client.start_run_around()
            else:
                client.stop_run_around()
        except Exception:
            pass
        _duy_tri(client, log=log, ho_phu=ho_phu)
        return True

    if viec == VIEC_THOAT:
        # Mode `digioi` thuan het gio -> THOAT GAME, khong dung im giua Di Gioi.
        # Goi `stop_account` cua engine cu (truyen vao qua `thoat_acc`): no set stop-event VA chan
        # cung relogin - tu viet lai thi acc se bi supervisor login lai ngay, quay vong ca ngay.
        if thoat_acc is None:
            return False
        thoat_acc(getattr(client, "_username", None) or getattr(client, "_label", ""),
                  "het gio Di Gioi (mode digioi)")
        return True
    if viec == VIEC_VAO_EVENT:
        # `go_to_event(ev)` cua engine cu - no lo ca cinematic va thoat cutscene.
        # CHUA VAO MAP EVENT THI CHUA DUOC LAP PARTY (xem nhanh PHA_EVENT trong `quyet_dinh`).
        if vao_event is None:
            return False
        return bool(vao_event(client))
    if viec == VIEC_DANH_EVENT:
        # LEADER mo vong battle - goi lai dung duong engine cu (`start_npc40_loop` voi hai callback
        # `_on_npc40_loss` / `_before_npc40_repeat`, va `_set_party_quest_mode` cho CA party).
        # Tu viet lai vong danh o day la bia - toan bo xu ly thua/hoi mau giua tran nam trong do.
        if danh_event is None:
            return False
        return bool(danh_event(client))
    if viec == VIEC_FC_GOM:
        # 2K LECH TANG: DI BO ve tang gom bang `regroup_to_event_start` cua engine cu.
        # KHONG duoc dung `go_to_event` o day - ham do `leave_party()` ngay dong dau ("vao event
        # phai khong co party"), goi giua luc party da lap xong la DAP TAN PARTY (user 20/09:
        # "sao party xong leader bi vang the").
        if fc_gom is None:
            return False
        return bool(fc_gom(client))
    if viec == VIEC_LENH_TAY:
        # LENH TAY cua GUI (teleport thanh / di map). Goi lai duong THI HANH cua engine cu qua
        # callback - khong tu viet lai chuoi "cho het tran -> roi party -> teleport".
        if lenh_tay_fn is None:
            return False
        return bool(lenh_tay_fn(client))
    if viec in (VIEC_2K_DANH, VIEC_2K_LEN_TANG):
        # MOT buoc cua vong leo thap - `floor_crawl.danh_mot_diem` / `qua_cong_len_tang`.
        # Tra ve sau MOT tran (hoac mot lan qua cong) roi engine quyet buoc ke tiep, thay vi mot
        # thread rieng chay het ca thap ma khong doc lenh cua ai.
        if fc_buoc_fn is None:
            return False
        return bool(fc_buoc_fn(client, viec == VIEC_2K_LEN_TANG))
    if viec == VIEC_DOI_THUONG:
        # Y flow cu: huy party -> `claim_40npc_reward(ev)` -> `close()` (thoat game).
        # "event thi danh xong out, train deo gi o day" (user 14/09).
        if doi_thuong is None:
            return False
        return bool(doi_thuong(client))
    if viec == VIEC_VIEC_VAT:
        # Acc dang nam han trong `client` (PB don / boss the gioi) - KHONG quay ray (user 14/09).
        return True
    return True


def _duy_tri(client, log=None, ho_phu=None):
    """Viec DINH KY trong luc train: Phuc Than + mua HP/SP + Di Gioi Ho Phu.

    Engine cu lam hai viec nay trong vong keepalive: `use_phuc_than_items` khi `phuc_than_pending`,
    va `buy_hp_sp` MOI 2 TIENG (`next_buy_hpsp`) khi user bat tick. Bo thi acc train mai voi buff
    da tut va het thuoc hoi - khong bao gio bao loi, chi kem dan.
    """
    _cfg = getattr(client, "_pe_pcfg", None) or {}
    # DI GIOI HO PHU - moi 3 phut, Y FLOW CU (`run_account` vong keepalive):
    #     if is_digioi and pcfg["use_digioi_ho_phu"] and time.time() >= next_ho_phu:
    #         if not c.in_combat(): _maybe_use_di_gioi_ho_phu("3p")
    #
    # Engine moi truoc day CHI goi ho phu trong `VIEC_DI_GIOI` - tuc luc acc dang DI VAO Di Gioi.
    # Vao roi thi engine giao `VIEC_TRAIN` (chay long vong) nen khong con goi nua, trong khi ho phu
    # lai dung la thu can dung LUC DANG O TRONG DG va con < 15 phut.
    # Hau qua: chi dung duoc SAU KHI acc da bi day ra khoi DG - mat han tac dung keo dai gio.
    # Ca that 22/09 (user: "engine moi hinh nhu ko tu dung Di gioi ho phu"):
    #     02:41:17 [dtbay] Kenh hien tai = 2 ... map 12003      <- da o Quang Truong, ngoai DG
    #     02:41:18 [dtbay] ENGINE: Di Gioi Ho Phu - con 3 phut (<15), da gui lenh dung
    if (_cfg.get("use_digioi_ho_phu") and ho_phu is not None
            and _goi(client, "in_di_gioi", False)):
        _han = float(getattr(client, "_pe_next_ho_phu", 0.0) or 0.0)
        if time.time() >= _han and not _goi(client, "in_combat", False):
            client._pe_next_ho_phu = time.time() + HO_PHU_CHECK_SEC
            try:
                ho_phu(client)
            except Exception as e:
                if log is not None:
                    log.warning("[%s] ENGINE: Ho Phu (dinh ky) loi (bo qua): %s",
                                getattr(client, "_label", "?"), e)
    if _cfg.get("use_phuc_than") and getattr(client, "phuc_than_pending", False):
        try:
            client.use_phuc_than_items()
        except Exception as e:
            if log is not None:
                log.warning("[%s] ENGINE: phuc than loi (bo qua): %s",
                            getattr(client, "_label", "?"), e)
    # MUA HP/SP - Y FLOW CU (`run_account`, nhanh "MUA HP/SP giua phien"): moi 2 TIENG, chi khi
    # KHONG trong tran, va `buy_hp_sp` TU kiem nguong du tru (du thi no khong di).
    #
    # Ban dau cho nay goi `client.buy_hp_sp()` KHONG THAM SO, trong khi ham can 6 tham so bat
    # buoc (buy_hp, hp_qty, hp_thresh, buy_sp, sp_qty, sp_thresh) -> TypeError, bi nuot vao
    # `except` va chi ghi "mua thuoc loi (bo qua)". Tuc party chay engine moi ma bat tick mua
    # HP/SP thi KHONG BAO GIO mua duoc, va loi thi nam im trong log warning.
    # Va cua cu `has_hp_and_sp_items()` cung sai loai: no hoi "con item HP/SP nao khong", con
    # flow cu hoi "DU TRU co tut duoi nguong user dien khong" - hai cau khac han.
    if _cfg.get("buy_hp") or _cfg.get("buy_sp"):
        _den = float(getattr(client, "_pe_next_buy_hpsp", 0.0) or 0.0)
        _ban = False
        try:
            _ban = bool(client.in_combat())
        except Exception:
            pass
        if time.time() >= _den and not _ban:
            client._pe_next_buy_hpsp = time.time() + BUY_HPSP_MOI_SEC   # dat TRUOC: loi cung khong spam
            try:
                _con_thieu = client.buy_hp_sp(
                    _cfg.get("buy_hp", False), int(_cfg.get("hp_qty", 9999)),
                    int(_cfg.get("hp_thresh", 500000)),
                    _cfg.get("buy_sp", False), int(_cfg.get("sp_qty", 9999)),
                    int(_cfg.get("sp_thresh", 500000)),
                )
                if _con_thieu and log is not None:
                    # Y flow cu: mua xong VAN THIEU (het xu) -> co party thi train tiep, 2h sau
                    # check lai. Engine moi luon chay theo party nen khong co nhanh "solo -> out".
                    log.info("[%s] ENGINE: mua HP/SP van thieu (het xu) -> train tiep, 2h sau "
                             "check lai", getattr(client, "_label", "?"))
            except Exception as e:
                if log is not None:
                    log.warning("[%s] ENGINE: mua thuoc loi (bo qua): %s",
                                getattr(client, "_label", "?"), e)


# ---------------------------------------------------------------- viec vat sau login
#
# KHONG tu che danh sach viec: goi THANG `lam_login_chores` cua engine cu (truyen vao qua
# `chore_fn`). Khoi do co hon hai chuc muc - diem danh, qua 14 ngay, qua quan doan, qua ban be,
# mo rong tui, tu cong diem, nang skill, Ba Dau, skill pet, LO HOANG KIM, donate quan doan,
# ruong trang bi, mua shop... Ba trong so do con la NGUON cua bang "Chu y" tren GUI
# (`_tu_cong_diem` -> diem du, `_kiem_han_ba_dau` -> Ba Dau, `process_furnace` -> lo).
#
# Ban tu che dau tien cua engine moi chi co 9 muc => user mat bang "Chu y" va hang chuc viec vat
# khac ma khong co mot dong log nao bao (16/09: "hinh nhu bi mat cai chu y").


def lam_viec_vat(client, pcfg=None, log=None, con_lam=None, chore_fn=None):
    """Lam viec vat sau login. Tra True khi da chay xong.

    Danh dau `_pe_xong_chore = True` khi xong: nhip sau doc co do de thoi giao viec nay. Khong
    dung dong ho - acc cham may cung phai lam xong, khong ai duoc dat han cho no (user 14/09:
    "m dat han 300s, sau 300 ma no van chua xong viec vat thi sao").
    """
    if con_lam is not None and not con_lam():
        return False                     # co lenh moi -> nha ra, nhip sau lam tiep
    if chore_fn is None:
        return False
    # DANH DAU "DANG LAM" ngay tu dau: chua co co nay thi nhip sau doc `xong_chore` = False roi
    # giao lai `login_chore`, ma neu co nao do lam no thanh True giua chung thi engine chuyen luon
    # sang `lap_party` VA CAT NGANG chores (party 41, 16/09: 15:52:21 login_chore -> 15:52:29
    # lap_party trong khi chores con chay toi 15:52:35).
    client._pe_xong_chore = False
    if log is not None:
        log.info("[%s] ENGINE: bat dau viec vat sau login", getattr(client, "_label", "?"))
    try:
        chore_fn(client)
    except Exception as e:
        # Mot viec no KHONG duoc lam mat ca luot: danh dau xong de acc di lam viec chinh, lan
        # login sau chay lai.
        if log is not None:
            log.warning("[%s] ENGINE: viec vat loi (bo qua): %s",
                        getattr(client, "_label", "?"), e)
    client._pe_xong_chore = True
    if log is not None:
        log.info("[%s] ENGINE: XONG viec vat sau login", getattr(client, "_label", "?"))
    return True


def lam_nhiem_vu_ngay(client, log=None, con_lam=None, daily_fn=None):
    """NHIEM VU NGAY: PB don (o 1) + claim 9 o. Tra True khi da chay xong.

    Danh dau `_pe_xong_daily` y het `_pe_xong_chore`: dat False NGAY TU DAU, khong thi nhip sau
    doc `xong_daily` = False roi giao lai, ma giua chung co the bi cat ngang.
    """
    if con_lam is not None and not con_lam():
        return False                     # co lenh moi -> nha ra, nhip sau lam tiep
    if daily_fn is None:
        client._pe_xong_daily = True     # khong ai lam duoc -> thoi giao viec nay
        return False
    client._pe_xong_daily = False
    if log is not None:
        log.info("[%s] ENGINE: bat dau NHIEM VU NGAY", getattr(client, "_label", "?"))
    try:
        daily_fn(client)
    except Exception as e:
        # Mot o hong KHONG duoc lam mat ca luot: danh dau xong de acc di lam viec chinh, lan login
        # sau chay lai (server tra trang thai that nen khong lam trung).
        if log is not None:
            log.warning("[%s] ENGINE: nhiem vu ngay loi (bo qua): %s",
                        getattr(client, "_label", "?"), e)
    client._pe_xong_daily = True
    if log is not None:
        log.info("[%s] ENGINE: XONG nhiem vu ngay", getattr(client, "_label", "?"))
    return True


def _goi(client, ten, mac_dinh=None):
    """Goi mot ham cua client, loi/thieu -> tra mac dinh.

    Doc TUNG TRUONG doc lap chu khong boc ca anh trong mot try: thieu MOT API (vd client cu chua
    co `digioi_minutes_live`) ma lam ca acc bi coi la CHET thi engine se tuong party hong va gom
    lai vo tan - dat hon nhieu so voi viec chi mat mot truong.
    """
    ham = getattr(client, ten, None)
    if ham is None:
        return mac_dinh
    try:
        return ham()
    except Exception:
        return mac_dinh


# ---------------------------------------------------------------- PartyEngine (1 thread / party)

NHIP_SEC = 1.0
# Nhip toi thieu cua worker: viec tra ve NGAY (train / pb_doi_theo / viec_vat) khong duoc phep
# lam vong quay nong. Xem ghi chu trong `AccWorker._vong`.
NHIP_WORKER_SEC = 1.0
# Mot viec duoc giao lai lien tiep qua nhieu lan = no chay xong ngay ma khong doi duoc gi.
# Keu len thay vi quay vong trong im lang.
LAP_CANH_BAO = 20


class PartyEngine:
    """MOT thread quyet dinh cho ca party. Khong chan o bat ky dau trong nhip.

    Vong doi mot nhip:
        chup anh 5 client  ->  quyet_dinh(anh)  ->  giao viec cho worker  ->  return
    Khong `while` cho ai, khong `sleep` giua chung. Vi the moi lenh (ke ca lenh do CHINH no vua
    ra o nhip truoc) deu duoc xet lai o nhip sau - tre toi da NHIP_SEC.

    So sanh voi engine cu: `run_account` co 21 vong cho khong han, 14 vong diec voi `reform_gen`.
    O day con so do la 0, va `tests/test_party_engine_nhip.py` chan bang AST khong cho mọc lai.
    """

    def __init__(self, pidx, doc_clients, can_bao_nhieu=0, map_dich=None, log=None,
                 bao_gui=None, pha=PHA_TRAIN, gio_dg_toi_da=120, doc_spot=None,
                 pb_doi_levels=(), ghi_pha=None, cap_nhat=None, moi_party=None,
                 co_pha_train=True, thoat_acc=None, pcfg=None, doc_duong=None,
                 doc_gen=None, doc_keo=None, doc_fc_di_bo=None, la_thanh=None,
                 hoi_du_cap=None, nhip_acc=None,
                 chay_pb_doi=None, ho_phu=None, doc_cap_dg=None, chore_fn=None,
                 daily_fn=None,
                 ve_safe_khi_stop=None, hoi_thanh=None, hoi_cho=None, doc_safe=None,
                 hoi_dieu_phoi=None, doc_thanh=None, kenh_doi_duoc=None, xe_dich=None,
                 ghi_thong_ke=None, vao_event=None, danh_event=None, doi_thuong=None,
                 map_event=(), hoi_event_xong=None, fc_gom=None, doc_tang_gom=None,
                 fc_buoc_fn=None, doc_fc_buoc=None, lenh_tay_fn=None, doc_lenh_tay=None):
        self.pidx = int(pidx)
        self._doc_clients = doc_clients      # () -> [(username, client, la_leader)]
        self.can_bao_nhieu = int(can_bao_nhieu or 0)
        self.map_dich = map_dich
        self._log = log
        self._bao_gui = bao_gui          # (username, mo_ta, pha) -> None : cho GUI thay
        self.pha = pha                   # PHA_DG / PHA_TRAIN (mode digioi_train doi pha giua chung)
        self.gio_dg_toi_da = int(gio_dg_toi_da or 120)
        self._doc_spot = doc_spot        # () -> (x, y) | None : tam bai quai leader da chot
        self.pb_doi_levels = tuple(pb_doi_levels or ())   # level PB to doi user BAT trong config
        self._ghi_pha = ghi_pha          # (pha) -> None : ghi nguoc `dt_phase` ra state party
        self._cap_nhat = cap_nhat        # (engine) -> None : doc lai cau hinh + chot bai, moi nhip
        self._moi_party = moi_party      # (client, train_on_map) -> None : `_invite_party_participants`
        self.co_pha_train = bool(co_pha_train)   # mode `digioi` thuan: het gio DG la HET, khong train
        self._thoat_acc = thoat_acc      # (username, ly_do) -> None : `stop_account` cua engine cu
        self.pcfg = dict(pcfg or {})     # config party (co bat/tat tung tinh nang cua user)
        self._doc_duong = doc_duong      # () -> [buoc] | None : MOB_PATHS toi tam quai (leader keo)
        self._chay_pb_doi = chay_pb_doi  # (client, level) -> bool : `_handle_auto_team_dungeon`
        self._ho_phu = ho_phu            # (client) -> None : dung Di Gioi Ho Phu khi con < 15 phut
        self._doc_cap_dg = doc_cap_dg or (lambda: None)   # () -> cap quai DG dieu phoi da chot
        self._chore_fn = chore_fn        # (client) -> None : `lam_login_chores` cua engine cu
        self._daily_fn = daily_fn        # (client) -> None : NHIEM VU NGAY (PB don o1 + claim 9 o)
        self._ve_safe_khi_stop = ve_safe_khi_stop   # (client) -> None : STOP thi ve safe truoc
        self.hoi_thanh = hoi_thanh       # (map_id) -> bool : `_o_thanh_di_qua` cua engine cu
        self.hoi_cho = hoi_cho           # () -> str : ly do chua nen ra lenh ("" = ra duoc)
        self.hoi_dieu_phoi = hoi_dieu_phoi   # () -> (viec, map, kenh, ly_do) : `_dieu_phoi_quyet`
        self._dp_kenh = None             # kenh dich do dieu phoi cu chot
        self._doc_gen = doc_gen          # () -> (reform_gen, resync_gen) : hai gen cua dieu phoi
        self._doc_keo = doc_keo          # () -> username | "*" : ai duoc di duong (`dat_nguoi_keo`)
        self._doc_fc_di_bo = doc_fc_di_bo  # () -> city_id | None : thanh cua route PHAI DI BO toi
        self._la_thanh = la_thanh        # (map_id) -> bool : co phai THANH TELEPORT khong
        self._hoi_du_cap = hoi_du_cap    # (level) -> bool : CA PARTY du cap danh PB do chua
        self._nhip_acc = nhip_acc        # (client) -> None : nhip keepalive per-acc (xem AccWorker)
        self._reform_da_lam = None
        self._resync_da_lam = None
        self._dp_viec_truoc = None
        self._doc_safe = doc_safe        # () -> [(x,y)] : safe cua map dich (cho build_smart_route)
        self._doc_thanh = doc_thanh      # () -> city_id : `_thanh_tap_ket_dich` cua engine cu
        self._kenh_doi_duoc = kenh_doi_duoc   # (client) -> bool : `_kenh_doi_duoc_ngay`
        self._xe_dich = xe_dich          # (x,y) -> (x,y) : `_jitter` cua engine cu
        self._ghi_thong_ke = ghi_thong_ke   # (spot, bat) -> None : `_set_train_block_stats_spot`
        self._vao_event = vao_event      # (client) -> bool : `go_to_event`
        self._danh_event = danh_event    # (client) -> bool : `start_npc40_loop` + callback
        self._doi_thuong = doi_thuong    # (client) -> bool : huy party + claim + thoat game
        self.map_event = tuple(map_event or ())    # map cua event (staging/dest) - de biet "da vao"
        self.hoi_event_xong = hoi_event_xong       # () -> bool : ngoai gio / da thua / da xong
        self._fc_gom = fc_gom            # (client) -> bool : `regroup_to_event_start` ve tang gom
        self._doc_tang_gom = doc_tang_gom  # () -> map_id | None : `_tang_gom_2k` cua engine cu
        self._fc_buoc_fn = fc_buoc_fn      # (client, len_tang: bool) -> bool : lam MOT buoc leo thap
        self._doc_fc_buoc = doc_fc_buoc    # () -> "danh" | "len_tang" | None : buoc ke tiep
        self._lenh_tay_fn = lenh_tay_fn    # (client) -> bool : thi hanh lenh tay cua GUI
        self._doc_lenh_tay = doc_lenh_tay  # () -> gen : `st["cmd_gen"]` hien tai
        self.workers = {}
        self._dung = threading.Event()
        self._th = None
        self.nhip_dem = 0
        self._dem_lap = {}               # username -> (viec, so lan giao lai lien tiep)
        self.viec_hien_tai = {}              # username -> viec (GUI doc)

    # -- chup anh --
    def chup(self):
        """Doc trang thai THAT cua tung client tai MOT khoanh khac.

        Doc THANG `client` (cung tien trinh) chu khong doi ai bao cao - L2. Loi khi doc mot acc
        KHONG duoc lam hong ca anh: coi acc do la `song=False`, nhip sau doc lai.
        """
        accs = []
        for username, c, la_leader in self._doc_clients():
            _w = self.workers.get(username)
            if c is None:
                # DANG LOGIN: van la nguoi cua party (`_clients_cua_party` da bo acc TAT HAN).
                # Dem no vao thi engine TU BIET party chua du - khong phai hoi ai.
                accs.append(AnhAcc(username, la_leader=la_leader, song=False))
                continue
            try:
                song = bool(getattr(c, "running", False))
                accs.append(AnhAcc(
                    username,
                    la_leader=la_leader,
                    song=song,
                    map_id=(int(getattr(c, "current_map", 0) or 0) or None) if song else None,
                    kenh=(int(getattr(c, "current_channel", 0) or 0) or None) if song else None,
                    dang_danh=bool(song and _goi(c, "in_combat", False)),
                    so_member=len(getattr(c, "party_members", None) or ()),
                    viec_dang_lam=self.viec_hien_tai.get(username, VIEC_NGHI),
                    xong_chore=bool(getattr(c, "_pe_xong_chore", False)),
                    xong_daily=bool(getattr(c, "_pe_xong_daily", False)),
                    dang_ban=bool(_w.dang_ban()) if _w is not None else False,
                    trong_dg=bool(song and _goi(c, "in_di_gioi", False)),
                    # DANG DUNG TRONG map pho ban to doi - doc MAP THAT (`in_team_dungeon`),
                    # khong doan theo dong ho.
                    trong_pb=bool(song and _goi(c, "in_team_dungeon", False)),
                    # Gen lenh tay acc nay DA thi hanh xong (callback thi hanh tu ghi len client).
                    lenh_tay_da_lam=int(getattr(c, "_pe_lenh_tay_gen", 0) or 0),
                    trong_event=bool(song and self.map_event
                                     and int(getattr(c, "current_map", 0) or 0)
                                     in self.map_event),
                    # Doc DONG HO SERVER (`digioi_minutes_live`), khong tu dem gio: acc co the da
                    # dung gio DG o may khac / phien truoc. Engine cu tung danh dau acc con nguyen
                    # 120/120 phut la "xong DG" vi doan bua (ca that 07/09 [chutam]).
                    con_gio_dg=bool(song and _goi(c, "digioi_minutes_live", 0)
                                    < self.gio_dg_toi_da),
                ))
            except Exception:
                accs.append(AnhAcc(username, la_leader=la_leader, song=False))
        _pb_lv = self._pb_doi_level()
        # Cho CLIENT biet doi dang lap la de di PHO BAN TO DOI: luc do `invite_members` duoc moi
        # ca member o MAP KHAC (PB khong doi cung map). Engine moi KHONG goi `dat_pha_pho_ban` nen
        # thieu cho nay la party 20 lai "1 dua dung ngoai PT" nhu 21/09.
        # CHI danh dau khi CON LUOT PB - het luot la ve lai luat cu (party thuong PHAI cung map).
        for _u, _c, _l in self._doc_clients():
            if _c is not None:
                try: _c._pe_pb_doi_level = _pb_lv
                except Exception: pass
        _anh = AnhParty(self.pidx, accs, can_bao_nhieu=self.can_bao_nhieu,
                        map_dich=self.map_dich, pha=self.pha,
                        co_spot=self._spot() is not None,
                        pb_doi_level=_pb_lv,
                        co_pha_train=self.co_pha_train,
                        event_xong=bool(self.hoi_event_xong() if self.hoi_event_xong else False),
                        tang_gom=self._tang_gom(), fc_buoc=self._fc_buoc(),
                        lenh_tay_gen=self._lenh_tay_gen())
        # THANH DI NGANG QUA: hoi THANG `_o_thanh_di_qua` cua engine cu (truyen qua `hoi_thanh`).
        # KHONG tu viet lai phep thu - ham do da can nhac: chi True khi CHAC CHAN (la thanh
        # teleport, da biet dich, va khac ca dich lan map train), "tha lap party thua con hon
        # khong bao gio lap".
        # QUYET DINH CAP PARTY - hoi THANG `_dieu_phoi_quyet` cua engine cu.
        if self.hoi_dieu_phoi is not None:
            try:
                _kq = self.hoi_dieu_phoi()
            except Exception:
                # NUOT LOI o day = party im lang re sang nhanh tu quyet ca ngay ma khong ai biet.
                _kq = None
                if self._log is not None:
                    self._log.exception("[party %d] ENGINE: hoi_dieu_phoi LOI", self.pidx + 1)
            if _kq:
                _anh.dp_viec, _dp_map, _dp_kenh, _ly = _kq
                if _dp_map:
                    _anh.map_dich = _dp_map
                self._dp_kenh = _dp_kenh
                if _anh.dp_viec != self._dp_viec_truoc and self._log is not None:
                    self._dp_viec_truoc = _anh.dp_viec
                    self._log.info("[party %d] ENGINE: dieu phoi chot '%s' - %s",
                                   self.pidx + 1, _anh.dp_viec, _ly)
        # CHUA NEN RA LENH? - hoi THANG cac phep thu cua engine cu (leader dang rot / co acc dang
        # doi kenh / thieu acc song / lech instance).
        if self.hoi_cho is not None:
            try:
                _anh.cho_ly_do = self.hoi_cho() or ""
            except Exception:
                _anh.cho_ly_do = ""
        _maps = _anh.maps()
        if self.hoi_thanh is not None and len(_maps) == 1:
            try:
                _anh.thanh_di_ngang = bool(self.hoi_thanh(_maps[0]))
            except Exception:
                pass
        # HAI GEN CUA DIEU PHOI - doc mot lan, bao "moi" dung mot nhip.
        #
        # `_dieu_phoi_thi_hanh` bump gen DUNG MOT NHAT roi vao cooldown 180s. Engine phai phan ung
        # dung mot lan y nhu `run_account` cu lam (`resync_gen > resync_gen_handled`), khong thi
        # lai thanh giao lai moi giay - dung cai da lam p43 bi dap qua lai giua thanh va map train.
        if self._doc_keo is not None:
            try:
                _anh.nguoi_keo = self._doc_keo() or "*"
            except Exception:
                _anh.nguoi_keo = "*"      # khong doc duoc -> khong khoa ai lai (L0)
        # THANH TAP KET (`chot_thanh_tap_ket`) - de biet member da ve toi noi chua.
        try:
            _td = self._thanh_dich()
        except Exception:
            _td = None
        _anh.thanh_dich = int(_td[0]) if _td else None
        if self._doc_gen is not None:
            try:
                _rf, _rs = self._doc_gen()
            except Exception:
                _rf, _rs = None, None
            if _rf is not None:
                if self._reform_da_lam is None:
                    self._reform_da_lam = int(_rf)     # nhip dau: khong coi la lenh moi
                elif int(_rf) > self._reform_da_lam:
                    self._reform_da_lam = int(_rf)
                    _anh.reform_moi = True
            if _rs is not None:
                if self._resync_da_lam is None:
                    self._resync_da_lam = int(_rs)
                elif int(_rs) > self._resync_da_lam:
                    self._resync_da_lam = int(_rs)
                    _anh.resync_moi = True
            if (_anh.reform_moi or _anh.resync_moi) and self._log is not None:
                self._log.info("[party %d] ENGINE: dieu phoi bump %s -> ca party thi hanh",
                               self.pidx + 1,
                               "reform_gen" if _anh.reform_moi else "resync_gen")
        return _anh

    # -- mot nhip --
    def nhip(self):
        if self._cap_nhat is not None:
            try:
                self._cap_nhat(self)
            except Exception:
                if self._log is not None:
                    self._log.exception("[party %d] ENGINE: loi cap nhat cau hinh (bo qua nhip)",
                                        self.pidx + 1)
        anh = self.chup()
        self._doi_pha_neu_het_gio_dg(anh)
        if anh.pha != self.pha:
            anh.pha = self.pha            # doi pha ngay trong nhip nay, khong cho them mot giay
        viec = quyet_dinh(anh)
        self.nhip_dem += 1
        for username, v in viec.items():
            w = self.workers.get(username)
            if w is None:
                continue
            if w.giao(v) and self._log is not None:
                self._log.info("[party %d] ENGINE: %s -> %s", self.pidx + 1, username, v)
        # BAO GUI CHI KHI VIEC DOI.
        #
        # `set_account_activity` mac dinh tao TASK MOI (tang `_ACC_TASK_SEQ`, dat lai `start`).
        # Goi no moi nhip cho moi acc = 62 task moi/giay voi 14 party -> GUI doc `seq` de biet co
        # gi doi nen no VE LAI BANG LIEN TUC -> Tk "not responding" (do that 15/09, ngay lan chay
        # dau tien cua engine moi).
        #
        # Viec cua acc thuong giu nguyen hang phut (di duong, danh PB, train), nen loc theo "co doi
        # khong" cat gan het luu luong ma GUI van thay dung trang thai.
        if self._bao_gui is not None:
            for username, v in viec.items():
                if self.viec_hien_tai.get(username) == v:
                    continue
                try:
                    self._bao_gui(username, "engine: %s" % v, v)
                except Exception:
                    pass
        self.viec_hien_tai = dict(viec)
        # CANH BAO VIEC QUAY VONG: cung mot viec duoc giao lai qua nhieu lan lien tiep = no chay
        # xong ngay roi khong doi duoc gi (vd `ve_map` ma dich la chinh cho dang dung). Truoc day
        # kieu nay quay CA NGAY trong im lang, phai doc log ENGINE moi thay.
        for _u, _v in viec.items():
            if _v in (VIEC_NGHI, VIEC_TRAIN):
                self._dem_lap.pop(_u, None)
                continue
            _c = self._dem_lap.get(_u)
            self._dem_lap[_u] = (_v, (_c[1] + 1) if (_c and _c[0] == _v) else 1)
            _n = self._dem_lap[_u][1]
            if _n % LAP_CANH_BAO == 0 and self._log is not None:
                self._log.warning("[party %d] ENGINE: '%s' giao lai %d lan lien tiep cho %s - viec "
                                  "chay xong ngay ma khong doi duoc gi (dang quay vong?)",
                                  self.pidx + 1, _v, _n, _u)
        return viec

    # -- vong doi --
    def start(self):
        for username, c, la_leader in self._doc_clients():
            if c is None:
                continue        # DANG LOGIN - chua co client de gan co / lam worker
            try:
                c._pe_la_leader = bool(la_leader)
                # PCFG PHAI GAN O DAY. Truoc day chi co cho DOC (`lam_viec_vat`) ma khong ai GAN ->
                # pcfg rong -> moi co `pcfg.get(co, True)` deu ra True: user TAT tinh nang nao thi
                # engine moi van lam tinh nang do. Hong am tham, khong loi, khong log.
                c._pe_pcfg = self.pcfg
            except Exception:
                pass
            w = self.workers.get(username)
            if w is not None:
                # ACC ROT ROI RELOGIN -> `GameClient` MOI HOAN TOAN. Worker cu van tro vao client
                # CU DA CHET: no se goi ham tren mot socket dong, va acc do VINH VIEN khong nhan
                # duoc lenh nua - mot kieu "im lang" y het `luumuoi` ngay 15/09.
                if w.client is not c:
                    w.client = c
                    w.giao(VIEC_NGHI)      # bo viec dang lam tren client cu
                    if self._log is not None:
                        self._log.info("[party %d] ENGINE: %s da relogin -> gan client MOI cho worker",
                                       self.pidx + 1, username)
                continue
            # KHONG `w.start()`: thread cua chinh acc se goi `chay_o_day()` (xem
            # `_dang_ky_engine_moi`). Tao thread rieng o day la them 1 thread/acc - dung cai da lam
            # GUI treo (799 thread, 798 tranh GIL).
            self.workers[username] = AccWorker(username, c, self._lam_viec,
                                              ve_safe_khi_stop=self._ve_safe_khi_stop,
                                              log=self._log, nhip_acc=self._nhip_acc)
        if self._th is None or not self._th.is_alive():
            self._dung.clear()
            self._th = threading.Thread(target=self._vong, name="engine-p%d" % (self.pidx + 1),
                                        daemon=True)
            self._th.start()

    def stop(self):
        self._dung.set()
        for w in self.workers.values():
            w.stop()

    def _vong(self):
        while not self._dung.is_set():
            t0 = time.time()
            # PARTY DA DUNG HAN -> THOAT LUONG. Y `_party_watcher` cua engine cu:
            #   `if not accs or not any(is_account_running(u) for u in accs): return`
            # Thieu buoc nay thi sau khi user bam "Stop tat ca", thread nhip van quay mai va giu
            # tham chieu toi client da dong (user 16/09: "an stop tat ca -> acc theo co che moi
            # ko thay tat").
            try:
                if not any(getattr(c, "running", False) for _u, c, _l in self._doc_clients()):
                    if self._log is not None:
                        self._log.info("[party %d] ENGINE: party da dung han -> thoat luong",
                                       self.pidx + 1)
                    self.stop()
                    return
            except Exception:
                pass
            try:
                self.nhip()
            except Exception:
                # Mot nhip no KHONG duoc giet engine: party se dung im vinh vien, dung cai L0 cam.
                if self._log is not None:
                    self._log.exception("[party %d] ENGINE: nhip loi -> bo qua, nhip sau lam lai",
                                        self.pidx + 1)
            cho = NHIP_SEC - (time.time() - t0)
            if cho > 0:
                self._dung.wait(cho)

    def _lam_viec(self, client, viec, con_lam):
        dich = None
        _fc_bo = None
        if viec == VIEC_VE_MAP:
            dich = self._map_dich_hien_tai()
            if self._doc_fc_di_bo is not None:
                try:
                    _fc_bo = self._doc_fc_di_bo()
                except Exception:
                    _fc_bo = None
        elif viec == VIEC_VE_THANH:
            dich = self._thanh_dich()
        elif viec in (VIEC_DOI_KENH, VIEC_RESYNC):
            dich = self._kenh_dich_hien_tai()
        elif viec == VIEC_RA_SPOT:
            dich = self._spot()
        elif viec == VIEC_PB_DOI:
            dich = self._pb_doi_level()
        thi_hanh(client, viec, con_lam, dich=dich, log=self._log, fc_di_bo=_fc_bo,
                 la_thanh=self._la_thanh, daily_fn=self._daily_fn,
                 moi_party=self._moi_party, thoat_acc=self._thoat_acc,
                 duong_ra_spot=(self._duong() if viec == VIEC_RA_SPOT else None),
                 chay_pb_doi=self._chay_pb_doi, ho_phu=self._ho_phu,
                 cap_dg=(self._doc_cap_dg() if viec == VIEC_DI_GIOI else None),
                 chore_fn=self._chore_fn,
                 safe_dich=(self._safe_dich() if viec == VIEC_VE_MAP else None),
                 kenh_doi_duoc=self._kenh_doi_duoc, xe_dich=self._xe_dich,
                 ghi_thong_ke=self._ghi_thong_ke, vao_event=self._vao_event,
                 danh_event=self._danh_event, doi_thuong=self._doi_thuong,
                 fc_gom=self._fc_gom, fc_buoc_fn=self._fc_buoc_fn,
                 lenh_tay_fn=self._lenh_tay_fn)

    def _map_dich_hien_tai(self):
        """MAP phai di toi.

        CA PARTY DA CUNG MAP (dang o thanh DI NGANG QUA) -> dich la MAP TRAIN, khong phai cho dang
        dung. Truoc day lay "map dong nguoi nhat" nen no tra ve CHINH CAI THANH DANG DUNG: viec
        `ve_map` thay "da o do roi" -> tra ve ngay -> worker nghi -> engine giao lai -> vong 1 giay.
        Ca that 16/09 party 41 (user: "p41 lai lap pt o Trac quan"):
            17:15:26 ENGINE: dt806..dt810 -> ve_map
            17:15:27 ENGINE: dt806..dt810 -> ve_map
            17:15:28 ENGINE: dt806..dt810 -> ve_map
        """
        anh = self.chup()
        maps = anh.maps()
        if self.map_dich in maps:
            return self.map_dich
        if len(maps) <= 1 and self.map_dich:
            return self.map_dich        # cung map roi -> di TOI DICH (map train), khong dung yen
        return _map_dich(anh, anh._dem_duoc(), maps)

    def _doi_pha_neu_het_gio_dg(self, anh):
        """CA PARTY het gio Di Gioi -> doi pha sang train. ENGINE MOI PHAI TU LAM VIEC NAY.

        Hai cho doi pha cua engine cu deu KHONG chay voi party engine moi:
            `run_account`        - engine moi khong chay kich ban nay (cua chan so 2)
            `_dieu_phoi_quyet`   - dieu phoi cu bi cam dung vao party engine moi (cua chan so 1)
        Thieu doan nay thi party het gio DG se ket o pha DG VINH VIEN: moi acc `con_gio_dg=False`
        -> `VIEC_NGHI` -> dung im mai mai. Dung cai L0 cam ("party hong thi phai gom lai BANG
        DUOC", khong co duong "dung im").

        DU PARTY moi doi pha: mot acc con gio ma ca party bo di train la no mat gio DG. Acc dang
        lam viec vat khong tinh (no o map khac la dung).
        """
        if self.pha != PHA_DG or not self.co_pha_train:
            # Mode `digioi` THUAN khong co pha train: het gio DG la het viec, khong doi pha di dau.
            # Truoc day doi bat ke mode -> nhip sau `_cap_nhat` dat lai pha DG (vi mode do LUON la
            # DG) -> doi lai -> vong lap SPAM LOG moi giay (do that 16/09, party 46 va 54).
            return
        dem = anh._dem_duoc()
        if not dem:
            return
        if any(a.con_gio_dg or a.trong_dg for a in dem):
            return                        # con nguoi con gio / dang trong DG -> chua doi
        self.pha = PHA_TRAIN
        if self._ghi_pha is not None:
            try:
                self._ghi_pha(PHA_TRAIN)
            except Exception:
                pass
        if self._log is not None:
            self._log.warning("[party %d] ENGINE: ca party (%d acc) HET GIO Di Gioi -> doi pha TRAIN",
                              self.pidx + 1, len(dem))

    def _pb_doi_level(self):
        """Level PB to doi CON LUOT gan nhat, doc tu DONG HO SERVER cua leader.

        `team_dungeon_remaining` tinh tu `mission_steps[daily_flag]` - bang mission-step server gui
        (`0x18 sub 0x06`). KHONG tu dem luot da danh: acc co the da danh o may khac / phien truoc,
        va engine cu tung danh dau nham acc con nguyen luot la "da xong" chi vi doan bua.

        Chua co bang mission-step -> tra None (CHUA KET LUAN), khong phai "het luot".
        """
        if not self.pb_doi_levels:
            return None
        _song = [(u, c) for u, c, _l in self._doc_clients() if getattr(c, "running", False)]
        if not _song:
            return None
        for lv in self.pb_doi_levels:
            lv = int(lv)
            # CA PARTY phai CON LUOT moi chay - y het bon cua cua flow cu
            # (`_handle_auto_team_dungeon`): doc luot TUNG member, thieu status cua ai do thi BO
            # QUA, va chi chay khi `len(need) == len(members)`.
            #
            # Truoc day o day chi doc luot cua MOI LEADER -> leader tao phong roi moi, nhung mot
            # member da het luot / chua du cap thi no khong vao duoc => phong thieu nguoi, leader
            # huy roi tao lai, quay vong.
            # Ca that 20/09 party 41 (user: "p41, di PB khi co 1 dua ben ngoai"):
            #   11:24:49 [dtsau] (LEADER) roster phong pho ban chi 3/4 member sau 8.0s -> THIEU
            #   11:25:10 [dtsau] (LEADER) roster phong pho ban chi 1/4 member sau 8.0s -> THIEU
            #   11:25:27 ENGINE: 'pb_doi_theo' giao lai 80 lan lien tiep cho dt807
            _du = True
            for _u, _c in _song:
                if not getattr(_c, "mission_steps_loaded", False):
                    _du = False          # chua co status 0x18 -> CHUA KET LUAN, khong phai "con luot"
                    break
                try:
                    if not _c.team_dungeon_remaining(lv):
                        _du = False
                        break
                except Exception:
                    _du = False
                    break
            if not _du:
                continue
            # CHUA DU CAP thi server khong cho ready - co tao phong cung chi ra "ready 0/4".
            if self._hoi_du_cap is not None:
                try:
                    if not self._hoi_du_cap(lv):
                        continue
                except Exception:
                    pass
            return lv
        return None

    def _duong(self):
        if self._doc_duong is None:
            return None
        try:
            return self._doc_duong()
        except Exception:
            return None

    def _thanh_dich(self):
        """THANH TAP KET - hoi `_thanh_tap_ket_dich` cua engine cu, khong tu chon."""
        if self._doc_thanh is None:
            return None
        try:
            return self._doc_thanh()
        except Exception:
            return None

    def _safe_dich(self):
        """Safe cua MAP DICH de truyen cho `build_smart_route` - y flow cu (`route_safe`)."""
        if self._doc_safe is None:
            return None
        try:
            return self._doc_safe()
        except Exception:
            return None

    def _spot(self):
        if self._doc_spot is None:
            return None
        try:
            sp = self._doc_spot()
        except Exception:
            return None
        return (int(sp[0]), int(sp[1])) if sp else None

    def _lenh_tay_gen(self):
        """`cmd_gen` cua party - GUI tang moi khi user ra lenh tay (teleport thanh / di map)."""
        if self._doc_lenh_tay is None:
            return 0
        try:
            return int(self._doc_lenh_tay() or 0)
        except Exception:
            return 0

    def _tang_gom(self):
        """TANG GOM cua 2K - hoi THANG `_tang_gom_2k` cua engine cu, khong tu tinh.

        None = khong phai 2K, hoac KHONG AI trong thap (ca party con o thanh -> nhanh
        `VIEC_VAO_EVENT` lo, khong co viec "gom tang" nao ca).
        """
        if self._doc_tang_gom is None:
            return None
        try:
            return self._doc_tang_gom()
        except Exception:
            return None

    def _fc_buoc(self):
        """BUOC KE TIEP cua 2K - hoi `floor_crawl.tinh_buoc()` qua callback, khong tu tinh."""
        if self._doc_fc_buoc is None:
            return None
        try:
            return self._doc_fc_buoc()
        except Exception:
            return None

    def _kenh_dich_hien_tai(self):
        if self._dp_kenh:
            return self._dp_kenh        # kenh DIEU PHOI CU da chot (`pick_best_channel`)
        k = self.chup().kenhs()
        return k[0] if k else None


# ============================================================================================
# QUYET DINH CAP PARTY - chuyen tu `_dieu_phoi_quyet` (run_party_digioi.py) vao ENGINE.
#
# User 21/09: "chuyen ve cung 1 thread thi de cai dieu phoi lam lon gi nua, thread biet het tat
# ca thong tin roi thi no phai nam vai tro dieu phoi luon" va "ve lau dai tao se xoa engine cu
# va dieu phoi".
#
# Nguyen tac giu nguyen tu ban cu:
#   * HAM THUAN: khong I/O, khong khoa, khong doc dong ho (gio truyen vao qua `anh.bay_gio`).
#     Moi thay doi trang thai tra ve trong `HieuUng` de nguoi goi thi hanh.
#   * THU TU NHANH LA LUAT: nhanh duoi chi dung khi nhanh tren da loai tru xong. Moi nhanh deu
#     giu nguyen chu thich + ca hong that da sinh ra no - dung xoa khi sua.
# ============================================================================================

class HieuUng(object):
    """Nhung thay doi trang thai ma quyet dinh nay keo theo. Ham quyet dinh KHONG tu lam."""

    __slots__ = ("doi_pha_train", "reset_joined", "kenh_hong", "rut_reform", "dang_gom",
                 "nguoi_keo", "chot_tang_gom", "chot_2k_xong", "xoa_nhip_acc", "o_thanh_tu",
                 "lech_tu", "het_lech_tu")

    def __init__(self):
        self.doi_pha_train = False   # mode digioi_train: ca party het gio DG -> sang pha train
        self.reset_joined = False    # leader rot -> so nho khong duoc giu nguoi cua doi da tan
        self.kenh_hong = None        # kenh "cung so ma khong thay nhau" -> picker phai TRANH
        self.rut_reform = False      # da du doi + cung map/kenh -> rut lenh reform da dat muc dich
        self.dang_gom = False        # bao acc biet party dang gom -> hoan viec vat
        self.nguoi_keo = "*"         # ai duoc di duong (xem `dat_nguoi_keo`)
        self.chot_tang_gom = False   # 2K: gom = di bo xuong tang -> phai chot tang cho ca party
        self.chot_2k_xong = False    # pha event: hoi xem 2K da het chua
        self.xoa_nhip_acc = False    # ra lenh roi thi moi acc tinh lai tu dau
        self.o_thanh_tu = None       # moc "ca party bat dau dam chan o thanh" (None = giu nguyen)
        self.lech_tu = None          # moc bat dau lech (None = xoa)
        self.het_lech_tu = None      # moc bat dau HET lech (None = xoa)


class AnhCapParty(object):
    """Anh chup MOT khoanh khac cua ca party, du de quyet dinh viec cap party.

    Moi truong o day la SU THAT DA DOC XONG - ham quyet dinh khong duoc di doc them gi nua.
    """

    __slots__ = ("bay_gio", "so_acc_song", "so_acc_cau_hinh", "raw_mode", "pha",
                 "can_lap_doi", "ngoai_gio_40npc", "event_xong", "ca_party_het_gio_dg",
                 "maps", "kenhs", "chua_biet_map", "lech_kenh_that", "mot_minh",
                 "du_doi", "leader_dang_rot", "dang_doi_kenh", "thieu_acc_song",
                 "ai_lech_instance", "o_thanh_di_qua", "thanh_tap_ket", "ca_party_o_thanh",
                 "acc_dung_hinh", "viec_di_train", "ly_do_di_train", "tinh_hinh_doi",
                 # Cau ly do lech do `_ly_do_lech` dung san (no can `maps`/`kenhs`/`mot_minh`
                 # va cach dien dat da chot tu lau) - anh chup mang sang, ham quyet dinh khong
                 # tu ghep chuoi.
                 "ly_do_lech", "ly_do_lech_dg",
                 "kenh_hien_tai", "lech_tu", "het_lech_tu", "o_thanh_tu", "reform_gen",
                 "reform_gen_thoa", "leader_acc", "co_leader_dang_song", "thanh_cu",
                 "han_lech_map", "han_lech_chung", "han_het_lech", "han_dung_hinh")

    def __init__(self, **kw):
        for ten in self.__slots__:
            setattr(self, ten, kw.get(ten))


def quyet_dinh_cap_party(anh):
    """(AnhCapParty) -> (viec, ly_do, HieuUng). HAM THUAN.

    Chuoi nhanh chuyen nguyen van tu `_dieu_phoi_quyet`. THU TU LA LUAT - nhanh duoi chi dung khi
    nhanh tren da loai tru xong. Moi ca hong that giu lai o dung nhanh sinh ra no.
    """
    hu = HieuUng()
    hu.lech_tu, hu.het_lech_tu, hu.o_thanh_tu = anh.lech_tu, anh.het_lech_tu, anh.o_thanh_tu
    now = anh.bay_gio

    # (1) MODE KHONG CAN LAP DOI -> dieu phoi khong co viec gi o cap party (loan dau: moi acc tu
    # dang ky va tu danh). Day la CUA DAU TIEN: ba lenh `moi`/`gom`/`dong_bo` deu sinh ra tu ham
    # nay, nen chan o cho chot kenh thoi la chua du (party 24, 10/09).
    if not anh.can_lap_doi:
        return DP_LAM, "mode KHONG CAN LAP DOI (loan dau: moi acc tu dang ky va tu danh)", hu
    # (2) 40NPC NGOAI GIO: viec duy nhat la moi acc TU di doi thuong roi thoat.
    if anh.ngoai_gio_40npc:
        return (DP_LAM,
                "40NPC ngoai gio -> moi acc tu di doi thuong roi thoat (khong gom, khong sync kenh)",
                hu)
    # (3) EVENT DA XONG -> moi acc di doi thuong roi THOAT (user 14/09: "event thi danh xong out,
    # train deo gi o day"). Dieu phoi ma van gom/moi thi acc bi keo vao vong reform va khong bao
    # gio quay lai duoc nhanh doc co do (party 6 va 7, 14/09).
    if anh.event_xong:
        return (DP_LAM,
                "event DA XONG -> moi acc di doi thuong roi thoat (khong gom, khong moi party)", hu)

    pha = anh.pha
    ly_do = ""
    # (4) mode `digioi_train`, pha DG: CA PARTY het gio DG -> DOI PHA.
    if anh.raw_mode == "digioi_train" and pha == PHA_DG and anh.ca_party_het_gio_dg:
        pha = PHA_TRAIN
        hu.doi_pha_train = True
        ly_do = "ca party (%d acc) het gio Di Gioi" % anh.so_acc_song

    maps, kenhs = anh.maps or {}, anh.kenhs or set()
    lech = len(maps) > 1 or bool(anh.lech_kenh_that)
    # DU PARTY = DA CUNG INSTANCE -> KHONG CO CHUYEN "LECH KENH". Server khong cho o chung doi ma
    # khac phan khu, nen roster DU la bang chung ca party dang o cung mot cho; con `current_channel`
    # la SO BOT TU NHO va no sai duoc (user kiem chung 30/08: bot hien ca 5 nick kenh 12, vao game
    # xem la 12/12/12/2/1). Ket luan "lech kenh" tu so nho do dan toi resync + doi kenh, ca hai deu
    # PHA party dang lanh (user 07/09: "vi sao du pt roi ma van co lenh doi kenh de pt lai").
    lech = lech or (len(kenhs) > 1 and not anh.du_doi)

    # DONG HO LECH KHONG DUOC RESET BOI MOT NHIP THOANG QUA. Ban cu thay cung map MOT nhip la ve 0,
    # nen party lech NGAT QUANG khong bao gio chay du han -> khong bao gio duoc gom (party 1, 09/09:
    # ba phut cho mot viec dieu phoi DA BIET tu giay dau).
    if lech:
        hu.het_lech_tu = None
        if hu.lech_tu is None:
            hu.lech_tu = now
    elif hu.lech_tu is not None:
        if hu.het_lech_tu is None:
            hu.het_lech_tu = now
        elif now - float(hu.het_lech_tu) >= anh.han_het_lech:
            hu.lech_tu = None
            hu.het_lech_tu = None
    # LECH MAP an han NGAN, lech kenh giu han cu: "khac map thi gom map" khong phai viec phai can
    # nhac mot phut - teleport chuyen tiep chi mat vai giay.
    _han = anh.han_lech_map if len(maps) > 1 else anh.han_lech_chung
    lech_lau = lech and hu.lech_tu is not None and now - hu.lech_tu > _han

    if pha == PHA_DG:
        # TRONG DI GIOI: van xu ly khi lech, nhung bang DONG BO TAI CHO chu KHONG gom ve thanh -
        # tu DG ra thanh la phai DI BO ra cong, tuc loi ca party ra khoi DG (party 2, 06/09).
        viec = DP_DONG_BO if lech_lau else DP_LAM
        if lech_lau and not ly_do:
            ly_do = anh.ly_do_lech_dg
    elif lech_lau:
        # LECH KENH -> DONG BO TAI CHO; chi lech MAP moi phai gom. Party 5 (06/09) ca 5 acc deu o
        # map 12922 ma van ra lenh GOM voi ly do "lech kenh [1, 5]" - gom ve thanh giua thap 2K la
        # vo nghia, leader quay vong 201.495 lan.
        viec = DP_DONG_BO if len(maps) <= 1 else DP_GOM
        if not ly_do:
            ly_do = anh.ly_do_lech
    elif anh.leader_dang_rot:
        # LEADER dang login lai -> server DA thao doi. Khong doi roster bao (no toi tre).
        viec = DP_MOI
        hu.reset_joined = True     # so nho khong duoc giu nguoi cua party da tan (L2d)
        if not ly_do:
            ly_do = "LEADER dang dis/login lai -> server da giai tan doi, phai lap lai"
    elif anh.dang_doi_kenh:
        # Co acc dang do viec doi kenh -> roster dang bien dong, CHUA KET LUAN gi ca.
        viec = DP_LAM
        if not ly_do:
            ly_do = "co acc dang doi kenh -> cho roster on dinh roi moi quyet"
    elif len(maps) > 1:
        # CON LECH MAP thi CHUA DEN LUOT LAP PARTY (user 08/09: "gom lai thi cai dau tien phai
        # check la co cung map hay ko"). Lech THOANG QUA la binh thuong -> de dong ho chay; qua han
        # thi chinh no ra lenh GOM. Chi CAM lap party luc dang lech.
        viec = DP_LAM
        if not ly_do:
            ly_do = "con lech map %s -> chua lap party, cho gom xong" % sorted(maps)
    elif anh.thieu_acc_song:
        # CHUA DU ACC LOGIN XONG -> chua duoc ket luan "cung map/kenh": 2 dua vao truoc cung kenh 1
        # bi ket luan la "ca party cung kenh" trong khi ba dua con lai co the o kenh khac han
        # (party 2, 13/09).
        viec = DP_LAM
        if not ly_do:
            ly_do = ("moi %d/%d acc login xong -> chua ket luan map/kenh, cho du roi moi quyet"
                     % (anh.so_acc_song, anh.so_acc_cau_hinh))
    elif anh.chua_biet_map:
        # CHUA BIET MAP CUA MOT NGUOI THI CHUA XONG BAC MAP - chua duoc xuong bac kenh. Phep dem
        # `maps` bo qua acc chua biet map, nen 4 dua cung map + 1 dua chua biet bi ket luan la
        # "cung map" -> tut xuong bac kenh -> khong bao gio chot duoc kenh dich (party 9, 13/09).
        viec = DP_LAM
        if not ly_do:
            ly_do = ("chua doc duoc map cua %s -> chua xong bac gom map, chua den luot kenh"
                     % (sorted(anh.chua_biet_map),))
    elif not anh.du_doi and anh.ai_lech_instance:
        # CUNG MAP + CUNG SO KENH MA KHONG THAY NHAU = KHAC INSTANCE. "Ai dang dung quanh minh"
        # (`0x03 PlayerAppear`) la bang chung that - server chi gui cho nguoi CUNG SCENE + CUNG
        # INSTANCE (user 13/09: "biet duoc nhung nguoi xung quanh minh thi biet duoc co cung kenh
        # hay ko, co cai lon gi ma ko chac").
        #
        # DANH DAU KENH HIEN TAI LA HONG. Khong co buoc nay thi `dong_bo` la lenh RONG: ca party DA
        # cung so kenh roi nen khong co gi de dong bo, nhip sau van khong thay nhau -> lap vo tan.
        # Ca that 21/09 party 43 - DUNG MOT TIENG o Tuong Duong (08:05:15 -> 09:05:03, 82 lan),
        # user: "p43 dung o Tuong duong bao lau roi ... 1 thread dieu khien ca pt roi ma van de
        # ngu the".
        viec = DP_DONG_BO
        hu.kenh_hong = anh.kenh_hien_tai or (sorted(kenhs)[0] if kenhs else None)
        if not ly_do:
            ly_do = ("cung map nhung %s KHONG THAY duoc dong doi (khac instance du cung so kenh) "
                     "-> danh dau kenh %s la HONG va chot kenh KHAC (%s)"
                     % (anh.ai_lech_instance, hu.kenh_hong, anh.tinh_hinh_doi))
    elif len(kenhs) > 1 and not anh.du_doi:
        # CUNG MAP ROI NHUNG CON LECH KENH -> GOM KENH TRUOC, chua den luot moi party: moi nguoi
        # khac kenh la vo ich vi server khong chuyen loi moi qua kenh (party 7, 11/09).
        # KHONG doi `lech_lau`: lech kenh o day chan dung viec dang lam, va dong bo kenh tai cho
        # thi khong ton gi.
        viec = DP_DONG_BO
        if not ly_do:
            ly_do = "cung map nhung LECH KENH %s -> gom kenh truoc khi moi (%s)" % (
                sorted(kenhs), anh.tinh_hinh_doi)
    elif not anh.du_doi:
        # CHI LAP PARTY O THANH TAP KET HOAC MAP TRAIN (user chot 13/09): thanh di ngang qua thi
        # lap xong la phai teleport di tiep, ma teleport bat buoc roi doi -> party vua lap lai tan.
        if anh.o_thanh_di_qua:
            viec = DP_GOM
            if not ly_do:
                _noi = next(iter(maps)) if len(maps) == 1 else None
                ly_do = ("dang o thanh DI NGANG QUA %s, chua toi thanh tap ket %s -> di tiep roi "
                         "moi lap party (%s)" % (_noi, anh.thanh_tap_ket, anh.tinh_hinh_doi))
        else:
            viec = DP_MOI
            if not ly_do:
                ly_do = "cung map/kenh nhung DOI chua du (%s)" % anh.tinh_hinh_doi
    else:
        # DU DOI, CUNG MAP+KENH -> hai buoc cuoi cua chuoi di train.
        viec = anh.viec_di_train
        if anh.ly_do_di_train and not ly_do:
            ly_do = anh.ly_do_di_train
        # RUT LENH REFORM DA DAT MUC DICH: bump reform la lenh "doi hong, lap lai di"; doi du roi
        # thi no CHET, nhung truoc day khong ai thu no ve - no nam do cho duoc thi hanh THEM LAN
        # NUA, va lan do pha dung cai party vua lap (party 1, 13/09).
        # Chi rut o DUNG nhanh nay: du doi + cung map + cung kenh.
        if anh.reform_gen and int(anh.reform_gen_thoa or 0) < int(anh.reform_gen):
            hu.rut_reform = True

    # PARTY DUNG HINH / DAM CHAN O THANH: du nguoi, cung map/kenh, khong lech gi - nhung KHONG AI
    # NHUC NHICH. Ba phep do cu (lech map/lech kenh/thieu nguoi) deu XANH khi ca party cung dam
    # chan mot cho SAI, vi chung chi so cac acc VOI NHAU chu khong so voi VIEC PHAI LAM (user
    # 07/09: "ko lech map ko lech kenh nhung ko party va ko thuc hien dung mode duoc chon thi phai
    # xu ly chu"). Ca that party 1, 07/09: 44 PHUT ca party dung im o Truong Sa.
    #
    # CHI xet khi viec = LAM (da du doi): party CHUA du doi thi dung o thanh CHINH LA viec dung -
    # do la diem gom cua vong reform, bump luc do = abort chinh vong gom vua ra lenh (party 1,
    # 08/09: mat 3 phut moi thoat).
    if viec == DP_LAM and anh.so_acc_song and pha != PHA_EVENT:
        if anh.ca_party_o_thanh:
            if not hu.o_thanh_tu:
                hu.o_thanh_tu = now
            elif now - float(hu.o_thanh_tu) > anh.han_dung_hinh:
                viec = DP_GOM
                ly_do = "ca party dam chan o THANH %s %.0fs (mode=%s) - khong lam dung viec" % (
                    sorted(maps)[0] if maps else "?", now - float(hu.o_thanh_tu),
                    anh.raw_mode or "?")
                hu.o_thanh_tu = now
        else:
            hu.o_thanh_tu = 0.0

    _dung_hinh = list(anh.acc_dung_hinh or [])
    # PARTY DU NGUOI + CUNG KENH thi "dong bo" KHONG CON NGHIA GI - `resync_gen` chi lam duoc dung
    # mot viec: bat moi member `leave_party()` roi moi lai, tuc DAP party dang lanh. Trong DG do
    # chinh la cai lam leader "moi 2198s chua du party (2/4)" dem 10->11/09. Van giu phat hien
    # dung hinh (party co the ket that), nhung cach chua phai khac cach PHA party.
    if _dung_hinh and pha == PHA_DG and anh.du_doi and len(kenhs) <= 1:
        _dung_hinh = []
    if viec == DP_LAM and _dung_hinh:
        viec = DP_GOM if pha != PHA_DG else DP_DONG_BO
        ly_do = "%d/%d acc DUNG HINH qua %.0fs: %s" % (
            len(_dung_hinh), anh.so_acc_song, anh.han_dung_hinh, sorted(_dung_hinh))
        hu.xoa_nhip_acc = True

    # BAO CHO ACC BIET party dang gom -> viec vat (cat tien trang / ban Noi Dat) phai HOAN.
    hu.dang_gom = viec in (DP_GOM, DP_MOI, DP_DONG_BO)
    # CHOT AI KEO CA PARTY DI DUONG. Di ra bai train bat buoc teleport, ma teleport thi phai ROI
    # DOI truoc - nen viec nay phai giao cho DUNG MOT nguoi; hai acc cung di la party tan.
    if viec in (DP_GOM, DP_DONG_BO):
        hu.nguoi_keo = "*"     # dang GOM: ca party phai tu ve diem hen
    elif not anh.leader_acc:
        hu.nguoi_keo = "*"     # party khong co bot-leader -> khong ai phai cho ai
    elif not anh.co_leader_dang_song:
        hu.nguoi_keo = "*"     # nguoi duoc giao da tat/rot -> khong de ca party cho (L0)
    else:
        hu.nguoi_keo = anh.leader_acc

    hu.chot_tang_gom = (viec == DP_GOM and pha == PHA_EVENT)
    hu.chot_2k_xong = (pha == PHA_EVENT)
    return viec, ly_do, hu
