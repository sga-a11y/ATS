"""Anti-debug guard (Windows). Goi check_debugger() luc khoi dong app product.
Phat hien debugger dang attach -> thoat ngay. KHONG tuyet doi (co the bypass) nhung tang rao can.
Tat o ban dev bang bien moi truong ATS_NO_GUARD=1."""
import os
import sys
import threading
import time


def _is_debugger_present_win() -> bool:
    """Goi IsDebuggerPresent + CheckRemoteDebuggerPresent (kernel32) tren Windows."""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        if k32.IsDebuggerPresent():
            return True
        present = ctypes.c_int(0)
        k32.CheckRemoteDebuggerPresent(k32.GetCurrentProcess(), ctypes.byref(present))
        return bool(present.value)
    except Exception:
        return False


def _trace_detected() -> bool:
    """Co ham trace/profile dang gan (vd dang chay duoi pdb/debugger Python)."""
    return sys.gettrace() is not None or sys.getprofile() is not None


def _bad_modules_loaded() -> bool:
    """Cac module debug/decompile pho bien da nap vao process."""
    bad = ("pdb", "pydevd", "debugpy", "uncompyle6", "decompyle3", "dis3", "bdb")
    return any(m in sys.modules for m in bad)


def _exit():
    # thoat im lang (khong in ly do cho nguoi reverse)
    os._exit(1)


def check_debugger():
    """Kiem tra 1 lan luc khoi dong. Co debugger -> thoat."""
    if os.environ.get("ATS_NO_GUARD") == "1":
        return
    if _is_debugger_present_win() or _trace_detected() or _bad_modules_loaded():
        _exit()


def start_watch(interval: float = 3.0):
    """Vong kiem tra dinh ky (debugger attach GIUA chung). Chay nen, daemon."""
    if os.environ.get("ATS_NO_GUARD") == "1":
        return

    def _loop():
        while True:
            if _is_debugger_present_win() or _trace_detected():
                _exit()
            time.sleep(interval)

    threading.Thread(target=_loop, daemon=True).start()
