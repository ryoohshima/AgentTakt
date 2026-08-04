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

## レイヤー描画（ユーザー報告バグより）

- **状況**: エッジ作成のラバーバンドを最前面 overlay レイヤーの全面ウィジェットで描いたところ、ドラッグ中に仮線以外の全描画が消えるとユーザーから報告を受けた。
- **ミス/原因**: Textual のウィジェットは不透明で、render_line が返す空白セルも下のレイヤーを覆い隠す。全面サイズの前面レイヤーは「線以外の全セル」で画面を塗り潰していた。
- **再発防止ルール**: 部分的な装飾（仮線・ハイライト等）を前面レイヤーの全面ウィジェットで描くな。既存の背面レイヤーのセルバッファに合成するか、装飾の bounding box に限定したウィジェットにせよ。また TUI の描画変更は「操作の途中状態」（ドラッグ最中など）を export_screenshot で目視確認してから完了とせよ（静止状態のテストだけでは覆い隠しバグは検出できない）。
- **関連ファイル**: src/agenttakt/tui/widgets/edge_layer.py（set_preview / cells_for_row）

## スクリーンショット（SVG エクスポート）

- **Textual の `export_screenshot()` は全角文字を 1 セル幅で数える**。`<text textLength=...>` が実幅の半分になり、日本語ラベルが潰れて判読不能になる（README のスクショで発覚）。UI 文字列は英語に統一して回避したため補正コードは持たない。UI に全角文字を足すと SVG が再び壊れる — その際は East Asian Width で `textLength` を計算し直すこと（削除ではなく再計算。削除すると閲覧環境のフォント幅次第でグリッドがずれる）。
- **UI 文字列は英語**（README / docs / PyPI が英語のため）。コメントと docstring は日本語のままでよい。
- **SVG は必ずラスタライズして目視確認する**。テキスト抽出だけでは字詰まり・見切れを検出できない。`Google Chrome --headless --screenshot` で PNG 化して確認する（既存プロファイルが動いていると起動に失敗するので `--user-data-dir` は別を指定）。

## テスト運用

- **rtk フィルタ経由の pytest 出力は要約される**（"No tests collected" 等が実態と異なることがある）。切り分け時は `rtk proxy uv run python -m pytest -v` で素の出力を見る。
- ハング調査でヒアドキュメント実行するときは `python -u`（バッファリング無効）にしないと print が失われる。
