import socket
from Config import CONNECTIVITY_CHECK_HOSTS, CONNECTIVITY_CHECK_TIMEOUT


def is_online(timeout: float = CONNECTIVITY_CHECK_TIMEOUT) -> bool:
    for host, port in CONNECTIVITY_CHECK_HOSTS:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False