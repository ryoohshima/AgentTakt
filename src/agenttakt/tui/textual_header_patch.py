"""Textual 8.2.8 Header の teardown 競合パッチ。

Header._on_mount が登録する title/sub_title watcher は NoScreen しか
捕まえておらず、画面 pop 中に発火すると除去済みの HeaderTitle への
query_one が NoMatches を漏らしてアプリごと落ちる。

サブクラスでは直せない: Textual はイベントを MRO 全クラスの
_on_mount に配るため、override しても親の watcher 登録は走る。
そのため Header._on_mount 自体を、except に NoMatches を足した
複製（それ以外は 8.2.8 の原文どおり）へ差し替える。
上流が NoMatches を捕まえたらこのファイルごと削除する。
"""

from textual.css.query import NoMatches
from textual.dom import NoScreen
from textual.events import Mount
from textual.widgets import Header
from textual.widgets._header import HeaderTitle


def _safe_on_mount(self: Header, _: Mount) -> None:
    async def set_title() -> None:
        try:
            self.query_one(HeaderTitle).update(self.format_title())
        except (NoScreen, NoMatches):
            pass

    self.watch(self.app, "title", set_title)
    self.watch(self.app, "sub_title", set_title)
    self.watch(self.screen, "title", set_title)
    self.watch(self.screen, "sub_title", set_title)


Header._on_mount = _safe_on_mount  # type: ignore[method-assign]
