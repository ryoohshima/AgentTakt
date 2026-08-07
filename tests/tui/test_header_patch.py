"""textual_header_patch の回帰テスト。

画面 pop 中に HeaderTitle が先に除去された状態で title watcher が走ると、
未パッチの Header は NoMatches でアプリごと落ちる(CI でのみ顕在化した競合)。
HeaderTitle を除去してから title を変更することで競合を決定的に再現する。
"""

import agenttakt.tui.textual_header_patch  # noqa: F401  Header へのパッチ適用
from textual.app import App, ComposeResult
from textual.widgets import Header
from textual.widgets._header import HeaderTitle


class _HeaderApp(App):
    def compose(self) -> ComposeResult:
        yield Header()


async def test_title_change_after_header_title_removed():
    app = _HeaderApp()
    async with app.run_test() as pilot:
        await app.query_one(HeaderTitle).remove()
        app.title = "changed"
        await pilot.pause()
        # NoMatches が漏れるとここまで到達せずテストごと落ちる
