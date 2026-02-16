from __future__ import annotations

import shutil

import pytest

from aotc.loader.runtime import native


@native
def add_native(a: int, b: int) -> int:
    return a + b


@pytest.mark.skipif(shutil.which("clang") is None, reason="clang required")
def test_native_decorator_compiles_and_runs() -> None:
    assert add_native(4, 9) == 13
