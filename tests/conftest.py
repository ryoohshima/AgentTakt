import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def sock_path():
    """socket 用の短い一時パス。

    pytest の tmp_path は macOS で深すぎて sun_path 104 バイト制限を超えるため、
    tempfile 直下に短いディレクトリを切る。
    """
    directory = Path(tempfile.mkdtemp(prefix="at-test-"))
    try:
        yield directory / "takt.sock"
    finally:
        shutil.rmtree(directory, ignore_errors=True)
