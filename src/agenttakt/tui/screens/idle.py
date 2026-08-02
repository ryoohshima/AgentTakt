from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Middle, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

_LOGO = """\
 ▄▀█ █▀▀ █▀▀ █▄░█ ▀█▀ ▀█▀ ▄▀█ █▄▀ ▀█▀
 █▀█ █▄█ ██▄ █░▀█ ░█░ ░█░ █▀█ █░█ ░█░"""


class IdleScreen(Screen):
    """計画の到着を待つ常駐画面。"""

    BINDINGS = [("q", "app.quit", "終了")]

    def __init__(self, socket_path: str) -> None:
        super().__init__()
        self._socket_path = socket_path

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Middle():
            with Center():
                with Vertical(id="idle-box"):
                    yield Static(_LOGO, id="idle-logo")
                    yield Static("", id="idle-status")
                    yield Static(f"socket: {self._socket_path}", id="idle-socket")
        yield Footer()

    def on_mount(self) -> None:
        self.update_status(0)

    def update_status(self, queue_size: int) -> None:
        status = self.query_one("#idle-status", Static)
        if queue_size:
            status.update(f"レビュー待ち: {queue_size} 件")
        else:
            status.update("Executor からの計画を待機中…")
