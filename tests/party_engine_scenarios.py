"""Small live-party fixtures shared by controller regression tests."""
from bot import party_engine as E


def account(name="a", **kwargs):
    values = dict(map_id=100, kenh=1, la_leader=name == "a", so_member=1)
    values.update(kwargs)
    return E.AnhAcc(name, **values)


def snapshot(accs=None, **kwargs):
    values = dict(can_bao_nhieu=1, map_dich=100, co_spot=True)
    values.update(kwargs)
    return E.AnhParty(0, accs if accs is not None else [account(), account("b")], **values)
