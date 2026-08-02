from __future__ import annotations

import os
import tempfile
from pathlib import Path

ENV_VAR = "AGENTTAKT_SOCKET"


def default_socket_path() -> Path:
    """socket パスを決める。AGENTTAKT_SOCKET → 既定 {tempdir}/agenttakt-{uid}/takt.sock。

    macOS の sun_path 104 バイト制限があるため浅いパスにしている。
    """
    custom = os.environ.get(ENV_VAR)
    if custom:
        return Path(custom)
    return Path(tempfile.gettempdir()) / f"agenttakt-{os.getuid()}" / "takt.sock"


def prepare_socket_dir(path: Path) -> None:
    """socket 置き場を 0700 で用意する（既存ディレクトリのパーミッションも矯正）。"""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
