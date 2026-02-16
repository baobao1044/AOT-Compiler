from __future__ import annotations

import ctypes
import shutil
from pathlib import Path

import pytest

from aotc.loader.runtime import load_symbol
from aotc.pipeline import Pipeline


CALL_SOURCE = """
def add(a: int, b: int) -> int:
    return a + b


def twice(x: int) -> int:
    return add(x, x)


def driver(n: int) -> int:
    if n < 2:
        return n
    return add(twice(n), 1)
""".strip()


RECUR_SOURCE = """
def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)
""".strip()


@pytest.mark.skipif(shutil.which("clang") is None, reason="clang required")
def test_cross_function_calls(tmp_path: Path) -> None:
    source = tmp_path / "calls.py"
    source.write_text(CALL_SOURCE + "\n", encoding="utf-8")

    artifacts = Pipeline(opt_level="O2").compile_file(source, emit="so", out_dir=tmp_path / "build")
    assert artifacts.artifact_path is not None

    symbol = load_symbol(
        artifacts.artifact_path,
        "driver",
        restype=ctypes.c_longlong,
        argtypes=[ctypes.c_longlong],
    )

    assert symbol(10) == 21


@pytest.mark.skipif(shutil.which("clang") is None, reason="clang required")
def test_recursive_call_still_supported(tmp_path: Path) -> None:
    source = tmp_path / "fib.py"
    source.write_text(RECUR_SOURCE + "\n", encoding="utf-8")

    artifacts = Pipeline(opt_level="O2").compile_file(source, emit="so", out_dir=tmp_path / "build2")
    assert artifacts.artifact_path is not None

    symbol = load_symbol(
        artifacts.artifact_path,
        "fib",
        restype=ctypes.c_longlong,
        argtypes=[ctypes.c_longlong],
    )

    assert symbol(10) == 55
