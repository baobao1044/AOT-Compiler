from __future__ import annotations

import ctypes
import math
import shutil
import sys
from pathlib import Path

import pytest

from aotc.loader.runtime import load_symbol
from aotc.pipeline import Pipeline


FFI_SOURCE = """
from aotc import extern

@extern("m")
def sin(x: float) -> float:
    ...

@extern("m")
def cos(x: float) -> float:
    ...

def trig_sum(x: float) -> float:
    return sin(x) + cos(x)
""".strip()


@pytest.mark.skipif(sys.platform.startswith("win"), reason="libm mapping differs on Windows")
@pytest.mark.skipif(shutil.which("clang") is None, reason="clang required")
def test_extern_sin_cos(tmp_path: Path) -> None:
    source = tmp_path / "ffi_demo.py"
    source.write_text(FFI_SOURCE + "\n", encoding="utf-8")

    artifacts = Pipeline(opt_level="O2").compile_file(source, emit="so", out_dir=tmp_path / "build")
    assert artifacts.artifact_path is not None

    symbol = load_symbol(
        artifacts.artifact_path,
        "trig_sum",
        restype=ctypes.c_double,
        argtypes=[ctypes.c_double],
    )

    got = float(symbol(1.0))
    expected = math.sin(1.0) + math.cos(1.0)
    assert abs(got - expected) < 1e-9
