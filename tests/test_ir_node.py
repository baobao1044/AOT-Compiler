from __future__ import annotations

from aotc.ir.node import BinOp, Value


def test_binop_holds_ssa_values() -> None:
    lhs = Value(name="v1", typ="int")
    rhs = Value(name="v2", typ="int")
    out = Value(name="v3", typ="int")
    node = BinOp(op="+", lhs=lhs, rhs=rhs, result=out)
    assert node.result == out
    assert node.op == "+"
