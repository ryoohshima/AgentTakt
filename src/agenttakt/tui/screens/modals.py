from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class ConfirmApproveScreen(ModalScreen[bool]):
    """承認前の確認ダイアログ。"""

    BINDINGS = [("escape", "dismiss(False)", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("Approve this plan?", classes="dialog-message")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Approve", variant="success", id="ok")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "ok")


class RejectReasonScreen(ModalScreen[str | None]):
    """却下理由の入力ダイアログ。キャンセル時は None を返す。"""

    BINDINGS = [("escape", "dismiss(None)", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("Reason for rejection (returned to the Executor)", classes="dialog-message")
            yield Input(placeholder="Enter a reason", id="reject-reason")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Reject", variant="error", id="ok")
                yield Button("Cancel", id="cancel")

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
