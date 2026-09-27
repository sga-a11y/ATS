"""Mode-specific decisions for the single party controller.

The caller owns the party snapshot and existing game operations. This module
only chooses bounded account work; it never starts a controller thread.
"""


_PRIORITY = frozenset(("lenh_tay", "login_chore", "daily", "viec_vat"))
_GROUP_AT_REST = frozenset(("lap_party", "doi_kenh"))


def decide_mode(mode, decisions, accs, *, target_map=None, event_kind=None,
                event_map=None, event_open=True, event_done=(), manual_pending=(), has_leader=True):
    """Adapt party work to modes outside the train/DG/team-event flow.

    ``accs`` are the account records in the engine's current party snapshot.
    Unknown maps never count as arrival at a destination.
    """
    result = dict(decisions)
    if mode == "event" and event_kind != "chaos_vs" and not has_leader:
        return _event_cho_moi(result, accs)
    if mode not in ("city", "stand", "cleanbag") and not (
            mode == "event" and event_kind == "chaos_vs"):
        return result

    manual_pending = set(manual_pending)
    event_done = set(event_done)
    for account in accs:
        user = account.username
        if user not in result or not account.song:
            continue
        current = result[user]
        if user in manual_pending or current == "lenh_tay":
            result[user] = "lenh_tay"
            continue
        if current in _PRIORITY:
            continue
        if account.dang_danh:
            result[user] = ("solo_event_run"
                            if mode == "event" and event_kind == "chaos_vs"
                            and getattr(account, "dang_ban", False)
                            and getattr(account, "viec_dang_lam", None) == "solo_event_run"
                            else "nghi")
            continue
        if mode == "city":
            if target_map is None or account.map_id is None:
                result[user] = "nghi"
            elif int(account.map_id) != int(target_map):
                result[user] = "city"
            else:
                result[user] = current if current in _GROUP_AT_REST else "nghi"
        elif mode in ("stand", "cleanbag"):
            result[user] = current if current in _GROUP_AT_REST else "nghi"
        elif user in event_done or not event_open:
            result[user] = "solo_event_exit"
        elif event_map is None or account.map_id is None:
            result[user] = "nghi"
        elif int(account.map_id) != int(event_map):
            result[user] = "solo_event_enter"
        else:
            result[user] = "solo_event_run"
    return result


# Event xong / het gio / stop: phai di duoc ke ca khi khong co leader bot (y engine cu).
_EVENT_THOAT = frozenset(("doi_thuong", "thoat"))


def _event_cho_moi(decisions, accs):
    """Event KHONG CO LEADER BOT ("Bot dung yen, cho nhan loi moi tu ...") - y engine cu:
    vao map event roi DUNG YEN cho nguoi that trong whitelist moi.

    - viec uu tien / event xong -> giu nguyen
    - chua o map event          -> `vao_event`
    - da vao doi                -> `nghi`: dung yen theo nguoi moi
    - da o map event            -> `lap_party`: acc khong phai leader chi MO CUA nhan loi moi
                                   (`set_party_invite_ready`), khong moi ai, khong roi doi.
    Truoc day moi viec deu thanh `nghi`: party 7 (27/09) dung o 12003 khong vao event, va du co
    vao thi loi moi cua nguoi that bi GIU vi khong ai mo cua.
    """
    by_user = {a.username: a for a in accs}
    result = {}
    for user, action in decisions.items():
        account = by_user.get(user)
        if action in _PRIORITY or action in _EVENT_THOAT or account is None or not account.song:
            result[user] = action
        elif account.dang_danh:
            result[user] = "nghi"
        elif not getattr(account, "trong_event", False):
            result[user] = "vao_event"
        elif getattr(account, "so_member", 0):
            # DA VAO DOI (nguoi that moi) -> DUNG YEN theo ho, y engine cu. Khong giao `lap_party`
            # nua: acc dang trong doi khong co gi de "mo cua".
            result[user] = "nghi"
        else:
            result[user] = "lap_party"
    return result


def execute_mode_action(action, client, *, target_map=None, city_flag=0,
                        event=None, abort=None, go_to_city=None, run_chaos=None,
                        leave_solo_event=None, stop=None, one_battle=False,
                        before_repeat=None):
    """Run one selected action on the existing account worker.

    Callbacks bridge to the runner's established city route, solo event loop,
    exit and stop helpers. The chaos callback must run in this worker and honor
    the supplied abort predicate.
    """
    if abort is not None and abort():
        return False
    if action == "city":
        if target_map is None or go_to_city is None:
            return False
        return bool(go_to_city(client, int(target_map), int(city_flag)))
    if action == "solo_event_enter":
        if not event or not event.get("dest_map"):
            return False
        return bool(client.go_to_event(event))
    if action == "solo_event_run":
        if not event or not event.get("dest_map") or run_chaos is None:
            return False
        if int(getattr(client, "current_map", 0) or 0) != int(event["dest_map"]):
            return False
        point = tuple((event.get("party_battle") or {}).get("point") or (910, 290))
        return bool(run_chaos(client, point, abort, before_repeat, bool(one_battle), event))
    if action == "solo_event_exit":
        if leave_solo_event is None or stop is None:
            return False
        try:
            leave_solo_event(client, event)
        finally:
            stop(client)
        return True
    return False
