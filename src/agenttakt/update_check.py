"""PyPI 上の新バージョン確認。

失敗（ネットワーク・パース）はすべて沈黙して None / False を返す。
ブロッキング I/O なので、呼び出し側は thread worker で実行すること。
"""

from __future__ import annotations

import json
import urllib.request

PYPI_JSON_URL = "https://pypi.org/pypi/agenttakt/json"


def fetch_latest_version(timeout: float = 3.0) -> str | None:
    """PyPI の最新バージョン文字列を返す。取得できなければ None。"""
    try:
        with urllib.request.urlopen(PYPI_JSON_URL, timeout=timeout) as response:
            return json.load(response)["info"]["version"]
    except Exception:
        return None


def is_newer(latest: str, current: str) -> bool:
    """latest が current より新しいか。比較不能（プレリリース表記等）は False。"""
    try:
        return _parse(latest) > _parse(current)
    except ValueError:
        return False


def _parse(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))
