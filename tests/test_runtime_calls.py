from __future__ import annotations

import shutil

import pytest

from aotc import native
from aotc.loader.runtime import parallel_for


@native
def inc(x: int) -> int:
    return x + 1


@native
def call_inc(x: int) -> int:
    return inc(x)


@pytest.mark.skipif(shutil.which("clang") is None, reason="clang required")
def test_native_function_calls_native_function() -> None:
    assert call_inc(41) == 42


def test_parallel_for_chunks_results() -> None:
    results = parallel_for(0, 8, lambda s, e: e - s, threads=4)
    assert sum(results) == 8
