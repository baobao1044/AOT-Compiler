from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aotc.pipeline import Pipeline


@pytest.mark.skipif(shutil.which("clang") is None, reason="clang required")
def test_pipeline_compile_to_asm(tmp_path: Path) -> None:
    source = tmp_path / "demo.py"
    source.write_text(
        "def add(a: int, b: int) -> int:\n"
        "    c = a + b\n"
        "    return c\n",
        encoding="utf-8",
    )
    artifacts = Pipeline().compile_file(source, emit="asm", out_dir=tmp_path / "build")
    assert artifacts.artifact_path is not None
    assert artifacts.artifact_path.exists()
    assert artifacts.llvm_ir_path.exists()
