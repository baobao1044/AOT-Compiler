from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aotc.cli import main


def test_build_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        main(["build", "missing.py"])


def test_build_emit_ll(tmp_path: Path) -> None:
    source = tmp_path / "mod.py"
    source.write_text("def f(x: int) -> int:\n    return x + 1\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    assert (
        main(
            [
                "build",
                str(source),
                "--emit",
                "ll",
                "--opt",
                "O3",
                "--passes",
                "cf,dce,inline",
                "--out-dir",
                str(out_dir),
            ]
        )
        == 0
    )
    assert (out_dir / "mod.ll").exists()


def test_clean_ok(tmp_path: Path) -> None:
    out_dir = tmp_path / "build"
    out_dir.mkdir(parents=True)
    assert main(["clean", "--out-dir", str(out_dir)]) == 0
    assert not out_dir.exists()


def test_bench_ok() -> None:
    if shutil.which("clang") is None:
        pytest.skip("clang required")
    assert main(["bench", "--loop-count", "1000", "--repeats", "1", "--threads", "1"]) == 0
