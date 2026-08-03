# ブリッジプロトコル（MCP サーバー ⇔ TUI）

MCP サーバープロセス（`agenttakt serve`）と TUI プロセス（`agenttakt`）を繋ぐ Unix domain socket プロトコルの仕様。

## socket パス

1. 環境変数 `AGENTTAKT_SOCKET` があればそれを使う（プロジェクト毎に分離したい場合の上書き手段）
2. 既定: `{tempdir}/agenttakt-{uid}/takt.sock`
   - ディレクトリはパーミッション `0700` で作成する
   - macOS の `sun_path` 104 バイト制限を考慮し、浅いパスにする

## フレーミング

NDJSON（1 行 1 メッセージ、UTF-8、改行 `\n` 区切り）。

- pydantic の `model_dump_json()` は改行を含まないため安全
- `nc -U <socket>` で手動テストできるデバッグ容易性を優先し、バイナリ長プレフィックスは採用しない

## メッセージ型

`type` フィールドを discriminator とする tagged union。

### `review_request`（MCP → TUI）

```json
{
  "type": "review_request",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "plan": { "graph_id": "...", "nodes": [], "edges": [] },
  "meta": {
    "summary": "認証まわりのリファクタリング計画",
    "cwd": "/path/to/project",
    "timestamp": "2026-08-02T12:00:00+09:00"
  }
}
```

- `request_id`: MCP 側が uuid4 で採番
- `meta.summary`: TUI ヘッダに表示する 1 行説明（任意）

### `review_response`（TUI → MCP）

```json
{
  "type": "review_response",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "approved",
  "plan": { "graph_id": "...", "status": "approved", "nodes": [], "edges": [] },
  "reason": null
}
```

- `decision`: `"approved"` | `"rejected"`
- `plan`: 人間の編集を反映した計画（`status` 書き換え済み）
- `reason`: 却下時の理由（任意）

### `error`（双方向）

```json
{
  "type": "error",
  "request_id": "550e8400-...",
  "code": "invalid_plan",
  "message": "..."
}
```

## 接続ライフサイクル

- **1 接続 1 リクエスト**。MCP 側は `接続 → review_request 送信 → review_response 受信 → 切断` を 1 サイクルとする（多重化しない）。
- TUI 側（`BridgeServer`）は複数同時接続を受理し、リクエストを FIFO キューに積んで 1 件ずつ処理する。応答は受信した接続へ書き戻す。
- **切断検出**: TUI 側は各接続の reader EOF を監視する。Executor 側タイムアウト・キャンセルで接続が落ちたら該当リクエストをキューから除去し、編集中であれば人間に通知して待機画面へ戻る。

## 異常系

| 状況 | 挙動 |
|---|---|
| TUI 未起動（connect が `FileNotFoundError` / `ConnectionRefusedError`） | MCP ツールがエラーを返す: `AgentTakt editor is not running. Ask the user to run "agenttakt" in a separate terminal, then call request_approval again.` |
| stale socket（TUI 異常終了の残骸） | TUI 起動時に bind 失敗 → connect 試行 → 拒否されたら unlink して再 bind |
| TUI 正常終了 | finally + SIGINT/SIGTERM handler で socket を unlink |
