#!/usr/bin/env python3
"""公式サイトからの取得を担う最小HTTPクライアント（標準ライブラリのみ）。

相手は古河電工の公開Webサイトなので、逐次取得・待ち時間あり・識別可能なUAで
負荷をかけないようにする。並列取得はしない。
"""
import time
import urllib.error
import urllib.request

UA = "F310-Knowledge-for-Agent/1.0 (local knowledge base builder; python-urllib)"
DELAY = 1.0        # 連続リクエストの間隔（秒）
TIMEOUT = 60
RETRIES = 3

_last_request = 0.0


def _throttle() -> None:
    global _last_request
    wait = DELAY - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def get(url: str, *, head: bool = False, retries: int = RETRIES):
    """(body, headers) を返す。head=True なら body は b""。

    404 等のクライアントエラーは即座に送出し、リトライしない。
    """
    last_err = None
    for attempt in range(1, retries + 1):
        _throttle()
        req = urllib.request.Request(
            url, headers={"User-Agent": UA}, method="HEAD" if head else "GET"
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
                return (b"" if head else res.read()), dict(res.headers)
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:
                raise
            last_err = e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
        if attempt < retries:
            time.sleep(2.0 * attempt)   # バックオフ
    raise RuntimeError(f"取得失敗（{retries}回）: {url} — {last_err}")
