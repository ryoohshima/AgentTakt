# Lessons

このプロジェクトで得た教訓。同じ轍を踏まないこと。

## Textual / TUI

- **Screen のメソッド名衝突に注意**: Textual の `Screen` は `clear_selection()`（テキスト選択解除）を持ち、リアクティブ watcher から内部的に呼ばれる。独自メソッドをオーバーライドすると「呼んだ覚えのない呼び出し」で状態が破壊される。Screen/App に独自メソッドを生やす前に `hasattr(Screen, name)` で衝突確認する。
- **`widget.size` はコンテンツ領域**: border/padding 込みの外形は `outer_size`。マウスイベントの `event.offset` は外形基準なので、ヒット判定は `outer_size` と比較する。
- **Pilot にドラッグ API はない**: `mouse_down` → `hover` → `mouse_up` で組む。ドラッグ対象自身は動くため、移動先は「ウィジェット相対」ではなく `hover(None, offset=画面絶対座標)` で指定する（ウィジェット相対だと mouse_up 前の合成 MouseMove で二重移動する）。

## asyncio / Unix domain socket

- **CPython の `create_unix_server` は既存 socket ファイルを bind 前に黙って削除する**。生きているサーバーの socket も奪うため、二重起動検出は bind に頼らず「存在するなら connect で生存確認 → 死んでいれば unlink」を bind 前に自前で行う。
- **Python 3.12+ の `Server.wait_closed()` は全接続のトランスポートが閉じるまで待つ**。ハンドラ内で writer を閉じ忘れると stop() が永久にハングする。全経路で `writer.close()` を徹底し、stop() には timeout の保険をかける。
- **macOS の `sun_path` は 104 バイト**: pytest の `tmp_path` は深すぎて `AF_UNIX path too long` になる。socket テストは `tempfile.mkdtemp` 直下の短いパスを使う（tests/conftest.py の `sock_path` fixture）。
- **通常ファイルへの connect は `ENOTSOCK`（errno 38）**: `ConnectionRefusedError` だけ捕まえると漏れる。stale 判定は `OSError` 全体で受ける。

## テスト運用

- **rtk フィルタ経由の pytest 出力は要約される**（"No tests collected" 等が実態と異なることがある）。切り分け時は `rtk proxy uv run python -m pytest -v` で素の出力を見る。
- ハング調査でヒアドキュメント実行するときは `python -u`（バッファリング無効）にしないと print が失われる。
