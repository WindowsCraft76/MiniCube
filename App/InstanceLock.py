import sys
from Config import TEMP_DIR, MAX_INSTANCE_SLOTS

def _try_lock(f):
    try:
        if sys.platform == "win32":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def acquire_instance_slot():
    handle = None
    other_running = False

    for i in range(MAX_INSTANCE_SLOTS):
        try:
            f = open(TEMP_DIR / f"minicube_instance_{i}.lock", "a+b")
        except OSError:
            continue

        if _try_lock(f):
            if handle is None:
                handle = f
            else:
                f.close()
        else:
            other_running = True
            f.close()

    return handle, other_running