"""APK-owned update lifecycle; never replaced with the running train_bot package."""
import sys
import time


def flush_caches():
    client = sys.modules.get('train_bot.client')
    flush = getattr(client, '_cache_flush', None)
    if flush is not None:
        flush(force=True)


def capture(state=sys):
    modules = {name: module for name, module in list(state.modules.items())
               if name == 'train_bot' or name.startswith('train_bot.')}
    return modules, list(state.path), getattr(state, '__ats_core_loaded__', None)


def restore(snapshot, state=sys):
    modules, path, version = snapshot
    for name in list(state.modules):
        if name == 'train_bot' or name.startswith('train_bot.'):
            del state.modules[name]
    state.modules.update(modules)
    state.path[:] = path
    state.__ats_core_loaded__ = version


def active_accounts(core):
    stops = getattr(core, 'account_stops', {})
    return [user for user, thread in list(core.account_threads.items())
            if thread.is_alive() and not (stops.get(user) and stops[user].is_set())]


def quiesce(core, timeout=60):
    active = active_accounts(core)
    core.stop_all(reason='Tu dong cap nhat core')
    engines = list(getattr(core, '_party_engines', {}).values())
    threads = list(core.account_threads.values())
    for engine in engines:
        engine.stop()
        threads.append(getattr(engine, '_th', None))
        threads.extend(getattr(worker, '_th', None)
                       for worker in list(engine.workers.values()))
    deadline = time.monotonic() + timeout
    for thread in threads:
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0, deadline - time.monotonic()))
    if any(thread is not None and thread.is_alive() for thread in threads):
        raise RuntimeError('Bot cũ chưa dừng hẳn; không thay core đang chạy')
    return active
