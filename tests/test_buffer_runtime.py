from __future__ import annotations

import ctypes
import shutil
from array import array

import pytest

from aotc import NDArray, native
from aotc.errors import RuntimeErrorAOTC
from aotc.loader.runtime import acquire_buffer


@native
def sum_native_buffer(values: NDArray[int], n: int) -> int:
    total = 0
    for i in range(n):
        total = total + values[i]
    return total


def test_acquire_buffer_array_is_zero_copy() -> None:
    values = array("d", [1.0, 2.0, 3.0])
    with acquire_buffer(values, writable=True) as handle:
        assert handle.itemsize == 8
        view = (ctypes.c_double * len(values)).from_address(handle.address)
        view[1] = 9.5
    assert values[1] == pytest.approx(9.5)


def test_acquire_buffer_bytes_read_only_pointer() -> None:
    payload = b"AOTC"
    with acquire_buffer(payload) as handle:
        assert handle.readonly
        view = (ctypes.c_char * len(payload)).from_address(handle.address)
        assert bytes(view) == payload


@pytest.mark.skipif(shutil.which("clang") is None, reason="clang required")
def test_native_ndarray_arg_uses_buffer_bridge() -> None:
    values = array("q", [1, 2, 3, 4, 5, 6])
    assert sum_native_buffer(values, len(values)) == sum(values)


@pytest.mark.skipif(shutil.which("clang") is None, reason="clang required")
def test_native_ndarray_rejects_wrong_itemsize() -> None:
    small_ints = array("i", [1, 2, 3, 4])
    with pytest.raises(RuntimeErrorAOTC):
        sum_native_buffer(small_ints, len(small_ints))
