#!/usr/bin/env python3
"""Homebrew formula の本体 url / sha256 を、PyPI 上の新バージョンへ差し替える。

release ワークフローの homebrew ジョブから呼ばれる。

    python bump_homebrew_formula.py <version> <formula_path>

PyPI への公開直後は JSON API にまだ反映されていないことがあるため、
sdist が見えるまでリトライする。formula の resource 節（依存パッケージ）は
触らない — 直接依存を変更したリリースでは別途手動で再生成すること。
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PACKAGE = "agenttakt"
RETRY_COUNT = 12
RETRY_INTERVAL = 15  # 秒


def fetch_sdist(version: str) -> tuple[str, str]:
    """PyPI JSON API から sdist の (url, sha256) を取得する。"""
    api = f"https://pypi.org/pypi/{PACKAGE}/{version}/json"
    last_error = "unknown"

    for attempt in range(1, RETRY_COUNT + 1):
        try:
            with urllib.request.urlopen(api, timeout=30) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
        except OSError as exc:
            last_error = str(exc)
        else:
            for entry in payload.get("urls", []):
                if entry.get("packagetype") == "sdist":
                    return entry["url"], entry["digests"]["sha256"]
            last_error = "sdist がレスポンスに含まれていない"

        print(
            f"[{attempt}/{RETRY_COUNT}] {PACKAGE} {version} を PyPI で待機中 ({last_error})",
            flush=True,
        )
        if attempt < RETRY_COUNT:
            time.sleep(RETRY_INTERVAL)

    raise SystemExit(f"PyPI に {PACKAGE} {version} の sdist が見つからない: {last_error}")


def bump(formula: Path, url: str, sha256: str) -> None:
    """formula 本体の url / sha256 行のみを置換する。

    resource 節の url / sha256 はインデント 4 で書かれるのに対し、
    formula 本体はインデント 2。この差で本体だけを狙い撃ちできる。
    """
    source = formula.read_text(encoding="utf-8")

    source, url_hits = re.subn(
        r'^  url ".*"$', f'  url "{url}"', source, count=1, flags=re.MULTILINE
    )
    source, sha_hits = re.subn(
        r'^  sha256 ".*"$', f'  sha256 "{sha256}"', source, count=1, flags=re.MULTILINE
    )

    if url_hits != 1 or sha_hits != 1:
        raise SystemExit(
            f"formula の本体 url / sha256 を特定できなかった "
            f"(url={url_hits} 件, sha256={sha_hits} 件): {formula}"
        )

    formula.write_text(source, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} <version> <formula_path>")

    version, formula_path = sys.argv[1], Path(sys.argv[2])
    url, sha256 = fetch_sdist(version)
    bump(formula_path, url, sha256)

    print(f"formula を {version} へ更新した")
    print(f"  url    = {url}")
    print(f"  sha256 = {sha256}")


if __name__ == "__main__":
    main()
