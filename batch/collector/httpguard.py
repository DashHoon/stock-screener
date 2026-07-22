"""requests 전역 타임아웃 가드.

fdr(FinanceDataReader)은 내부에서 requests를 타임아웃 없이 호출한다.
requests는 timeout=None이면 socket.setdefaulttimeout()도 무시하고 무한 대기하므로
(2026-07-22 실측: 응답 없는 연결이 수집 스레드를 7시간 동결시킴),
어댑터 레벨에서 기본 타임아웃을 강제한다.
"""

import requests.adapters

_installed = False


def install_timeout_guard(seconds: float = 15.0) -> None:
    """타임아웃 미지정 requests 호출에 기본 타임아웃을 강제한다. 멱등."""
    global _installed
    if _installed:
        return
    _installed = True

    original_send = requests.adapters.HTTPAdapter.send

    def send_with_timeout(self, request, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = seconds
        return original_send(self, request, **kwargs)

    requests.adapters.HTTPAdapter.send = send_with_timeout
