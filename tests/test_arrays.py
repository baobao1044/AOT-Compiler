from __future__ import annotations

import ctypes
import shutil
from pathlib import Path

import pytest

from aotc.loader.runtime import load_symbol
from aotc.pipeline import Pipeline


ARRAY_SOURCE = """
def sum_array(n: int) -> int:
    a = [0] * n

    i = 0
    while i < n:
        a[i] = i
        i = i + 1

    total = 0
    j = 0
    while j < n:
        total = total + a[j]
        j = j + 1

    return total
""".strip()


@pytest.mark.skipif(shutil.which("clang") is None, reason="clang required")
def test_compile_and_run_sum_array(tmp_path: Path) -> None:
    source = tmp_path / "sum_array.py"
    source.write_text(ARRAY_SOURCE + "\n", encoding="utf-8")

    artifacts = Pipeline(opt_level="O3").compile_file(source, emit="so", out_dir=tmp_path / "build")
    assert artifacts.artifact_path is not None

    symbol = load_symbol(
        artifacts.artifact_path,
        "sum_array",
        restype=ctypes.c_longlong,
        argtypes=[ctypes.c_longlong],
    )

    assert symbol(8) == 28
