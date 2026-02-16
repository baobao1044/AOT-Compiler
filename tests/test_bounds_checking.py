from __future__ import annotations

import pytest

from aotc.errors import FrontEndError
from aotc.front_end.parser import FrontEndParser


def test_bounds_checking_rejects_static_oob_read() -> None:
    src = """
def bad_read() -> int:
    a = [0] * 4
    return a[4]
"""
    with pytest.raises(FrontEndError, match="Static out-of-bounds access"):
        FrontEndParser().lower_module(src)


def test_bounds_checking_rejects_static_oob_write() -> None:
    src = """
def bad_write() -> int:
    a = [0] * 3
    a[-1] = 7
    return a[0]
"""
    with pytest.raises(FrontEndError, match="Static out-of-bounds access"):
        FrontEndParser().lower_module(src)
