from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class ConfirmApproveScreen(ModalScreen[bool]):
    """承認前の確認ダイアログ。"""

    BINDINGS = [("escape", "dismiss(False)", "キャンセル")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("この計画を承認しますか？", classes="dialog-message")
            with Horizontal(classes="dialog-buttons"):
                yield Button("承認", variant="success", id="ok")
                yield Button("キャンセル", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "ok")


class RejectReasonScreen(ModalScreen[str | None]):
    """却下理由の入力ダイアログ。キャンセル時は None を返す。"""

    BINDINGS = [("escape", "dismiss(None)", "キャンセル")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("却下理由（Executor に返されます）", classes="dialog-message")
            yield Input(placeholder="理由を入力", id="reject-reason")
            with Horizontal(classes="dialog-buttons"):
                yield Button("却下", variant="error", id="ok")
                yield Button("キャンセル", id="cancel")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def _submit(self) -> None:
        self.dismiss(self.query_one(Input).value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()
