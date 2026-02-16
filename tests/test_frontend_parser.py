from __future__ import annotations

from aotc.front_end.parser import FrontEndParser
from aotc.ir.node import Branch, GEP, Load, Phi


def test_lower_arithmetic_function() -> None:
    src = """
def add(a: int, b: int) -> int:
    c = a + b
    return c
"""
    module = FrontEndParser().lower_module(src)
    fn = module.functions[0]
    assert fn.name == "add"
    assert len(fn.ordered_blocks()) == 1
    assert fn.ordered_blocks()[0].terminator is not None


def test_lower_if_else_inserts_phi() -> None:
    src = """
def f(x: int) -> int:
    y = 1
    if x < 5:
        y = y + 1
    else:
        y = y + 2
    return y
"""
    module = FrontEndParser().lower_module(src)
    fn = module.functions[0]
    phis = [node for block in fn.ordered_blocks() for node in block.nodes if isinstance(node, Phi)]
    assert phis


def test_lower_while_has_branch() -> None:
    src = """
def loop(n: int) -> int:
    i = 0
    s = 0
    while i < n:
        s = s + i
        i = i + 1
    return s
"""
    module = FrontEndParser().lower_module(src)
    fn = module.functions[0]
    branches = [b.terminator for b in fn.ordered_blocks() if isinstance(b.terminator, Branch)]
    assert branches


def test_lower_for_range() -> None:
    src = """
def loop(n: int) -> int:
    total = 0
    for i in range(n):
        total = total + i
    return total
"""
    module = FrontEndParser().lower_module(src)
    fn = module.functions[0]
    assert len(fn.ordered_blocks()) >= 3


def test_lower_ndarray_pointer_argument_with_indexing() -> None:
    src = """
def sum_buf(a: NDArray[int], n: int) -> int:
    total = 0
    for i in range(n):
        total = total + a[i]
    return total
"""
    module = FrontEndParser().lower_module(src)
    fn = module.functions[0]
    assert fn.args[0].typ == "ptr_int"

    geps = [node for block in fn.ordered_blocks() for node in block.nodes if isinstance(node, GEP)]
    loads = [node for block in fn.ordered_blocks() for node in block.nodes if isinstance(node, Load)]
    assert geps
    assert loads
