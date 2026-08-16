"""アップグレード通知（update_check + TUI 統合）のテスト。"""

import io
import json

from agenttakt.tui.app import AgentTaktApp
from agenttakt.update_check import fetch_latest_version, is_newer


def test_is_newer():
    assert is_newer("0.3.0", "0.2.0")
    assert not is_newer("0.2.0", "0.2.0")
    assert not is_newer("0.1.9", "0.2.0")
    # 数値タプル比較（文字列比較だと 0.10.0 < 0.2.0 になる）
    assert is_newer("0.10.0", "0.2.0")
    # 比較不能（プレリリース表記等）は沈黙して False
    assert not is_newer("0.3.0rc1", "0.2.0")


def test_fetch_latest_version_parses_pypi_json(monkeypatch):
    body = json.dumps({"info": {"version": "1.2.3"}}).encode()
    monkeypatch.setattr(
        "agenttakt.update_check.urllib.request.urlopen",
        lambda url, timeout: io.BytesIO(body),
    )
    assert fetch_latest_version() == "1.2.3"


def test_fetch_latest_version_swallows_errors(monkeypatch):
    def boom(url, timeout):
        raise OSError("network down")

    monkeypatch.setattr("agenttakt.update_check.urllib.request.urlopen", boom)
    assert fetch_latest_version() is None


async def test_notify_on_newer_version(sock_path, monkeypatch):
    monkeypatch.setattr("agenttakt.tui.app.fetch_latest_version", lambda: "999.0.0")
    app = AgentTaktApp(socket_path=sock_path, check_updates=True)
    messages = []
    monkeypatch.setattr(app, "notify", lambda message, **kwargs: messages.append(message))
    async with app.run_test(size=(120, 40)) as pilot:
        for _ in range(60):
            if messages:
                break
            await pilot.pause(0.05)
    assert any("999.0.0" in message for message in messages)


async def test_no_check_by_default(sock_path, monkeypatch):
    """check_updates を渡さない限りネットワークへ出ない（テストのオフライン性の保証）。"""

    def forbidden():
        raise AssertionError("fetch_latest_version が呼ばれた")

    monkeypatch.setattr("agenttakt.tui.app.fetch_latest_version", forbidden)
    app = AgentTaktApp(socket_path=sock_path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.2)
