from __future__ import annotations

import json

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Input, Label, Static

from agenttakt.models.plan import Node


class ParamPanel(VerticalScroll):
    """選択ノードのパラメータ編集サイドパネル。

    data は JSON を直書きさせず、トップレベルキーごとの入力欄に分解する。
    文字列値はそのまま編集、リスト・数値・オブジェクトは JSON 断片として編集する。
    """

    def __init__(self) -> None:
        super().__init__()
        self._node: Node | None = None
        self._loading = False  # 値の流し込み中に Changed を無視するためのガード
        self._json_keys: set[str] = set()  # 文字列以外（JSON 断片編集）のキー

    def compose(self) -> ComposeResult:
        yield Static("Parameters", classes="panel-heading")
        yield Static("No node selected", id="panel-node-id")
        yield Label("title")
        yield Input(id="panel-title")
        yield Label("type")
        yield Input(id="panel-type")
        yield Label("data")
        yield Vertical(id="panel-data-fields")
        yield Input(id="panel-data-new-key", placeholder="+ new key (Enter)")

    def show_node(self, node: Node) -> None:
        self._loading = True
        self._node = node
        self.query_one("#panel-node-id", Static).update(f"id: {node.id}")
        self.query_one("#panel-title", Input).value = node.title
        self.query_one("#panel-type", Input).value = node.type
        self._render_data_fields(node)
        self._loading = False

    def show_none(self) -> None:
        self._loading = True
        self._node = None
        self.query_one("#panel-node-id", Static).update("No node selected")
        self.query_one("#panel-title", Input).value = ""
        self.query_one("#panel-type", Input).value = ""
        self.query_one("#panel-data-fields", Vertical).remove_children()
        self._json_keys = set()
        self._loading = False

    def _render_data_fields(self, node: Node) -> None:
        container = self.query_one("#panel-data-fields", Vertical)
        container.remove_children()
        self._json_keys = set()
        widgets = []
        for key, value in node.data.items():
            if isinstance(value, str):
                text = value
            else:
                text = json.dumps(value, ensure_ascii=False)
                self._json_keys.add(key)
            widgets.append(Label(key, classes="data-key"))
            widgets.append(Input(value=text, name=key, classes="data-field"))
        if widgets:
            container.mount(*widgets)

    # --- モデルへの反映 ---

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

    @on(Input.Changed, ".data-field")
    def _data_field_changed(self, event: Input.Changed) -> None:
        if self._loading or self._node is None or not event.input.name:
            return
        key = event.input.name
        if key in self._json_keys:
            try:
                value = json.loads(event.value)
            except json.JSONDecodeError:
                return  # 入力途中。確定できない間は反映せず、blur 時に通知する
        else:
            value = event.value
        data = dict(self._node.data)
        data[key] = value
        self.screen.apply_node_edit(self._node.id, "data", data)  # type: ignore[attr-defined]

    @on(Input.Submitted, "#panel-data-new-key")
    def _add_data_key(self, event: Input.Submitted) -> None:
        if self._node is None:
            return
        key = event.value.strip()
        if not key or key in self._node.data:
            return
        data = dict(self._node.data)
        data[key] = ""
        self.screen.apply_node_edit(self._node.id, "data", data)  # type: ignore[attr-defined]
        event.input.value = ""
        self._render_data_fields(self._node)

    def on_descendant_blur(self, event: events.DescendantBlur) -> None:
        # JSON 断片フィールドが不正なまま離脱したら知らせる
        widget = event.widget
        if self._node is None or not isinstance(widget, Input):
            return
        if widget.name and widget.name in self._json_keys and widget.has_class("data-field"):
            try:
                json.loads(widget.value)
            except json.JSONDecodeError as error:
                self.app.notify(f"Invalid JSON in '{widget.name}': {error}", severity="error")
