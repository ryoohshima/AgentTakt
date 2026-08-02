from __future__ import annotations

import json

from textual import events, on
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Input, Label, Static, TextArea

from agenttakt.models.plan import Node


class ParamPanel(VerticalScroll):
    """選択ノードのパラメータ編集サイドパネル。

    title / type は入力即時反映、data(JSON) はフォーカスが外れたときに検証して反映する。
    """

    def __init__(self) -> None:
        super().__init__()
        self._node: Node | None = None
        self._loading = False  # 値の流し込み中に Changed を無視するためのガード

    def compose(self) -> ComposeResult:
        yield Static("パラメータ", classes="panel-heading")
        yield Static("ノード未選択", id="panel-node-id")
        yield Label("title")
        yield Input(id="panel-title")
        yield Label("type")
        yield Input(id="panel-type")
        yield Label("data (JSON)")
        yield TextArea(id="panel-data")

    def show_node(self, node: Node) -> None:
        self._loading = True
        self._node = node
        self.query_one("#panel-node-id", Static).update(f"id: {node.id}")
        self.query_one("#panel-title", Input).value = node.title
        self.query_one("#panel-type", Input).value = node.type
        self.query_one("#panel-data", TextArea).load_text(
            json.dumps(node.data, ensure_ascii=False, indent=2)
        )
        self._loading = False

    def show_none(self) -> None:
        self._loading = True
        self._node = None
        self.query_one("#panel-node-id", Static).update("ノード未選択")
        self.query_one("#panel-title", Input).value = ""
        self.query_one("#panel-type", Input).value = ""
        self.query_one("#panel-data", TextArea).load_text("")
        self._loading = False

    @on(Input.Changed, "#panel-title")
    def _title_changed(self, event: Input.Changed) -> None:
        if self._loading or self._node is None:
            return
        self.screen.apply_node_edit(self._node.id, "title", event.value)  # type: ignore[attr-defined]

    @on(Input.Changed, "#panel-type")
    def _type_changed(self, event: Input.Changed) -> None:
        if self._loading or self._node is None:
            return
        self.screen.apply_node_edit(self._node.id, "type", event.value)  # type: ignore[attr-defined]

    def on_descendant_blur(self, event: events.DescendantBlur) -> None:
        # data(JSON) はフォーカスアウト時に検証して反映する
        if self._node is None or not isinstance(event.widget, TextArea):
            return
        text = event.widget.text.strip() or "{}"
        try:
            data = json.loads(text)
            if not isinstance(data, dict):
                raise ValueError("data はオブジェクト（{}）である必要があります")
        except (json.JSONDecodeError, ValueError) as error:
            self.app.notify(f"data の JSON が不正: {error}", severity="error")
            return
        self.screen.apply_node_edit(self._node.id, "data", data)  # type: ignore[attr-defined]
