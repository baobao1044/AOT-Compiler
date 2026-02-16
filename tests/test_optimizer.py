from __future__ import annotations

from aotc.back_end.optimizer import default_pass_manager
from aotc.front_end.parser import FrontEndParser
from aotc.ir.node import BinOp, Const


def test_constant_folding_rewrites_binop_to_const() -> None:
    src = """
def f() -> int:
    x = 2 + 3
    return x
"""
    module = FrontEndParser().lower_module(src)
    optimized = default_pass_manager().run_module(module)
    fn = optimized.functions[0]
    nodes = [n for b in fn.ordered_blocks() for n in b.nodes]
    assert any(isinstance(n, Const) for n in nodes)
    assert not any(isinstance(n, BinOp) and n.op == "+" for n in nodes)
