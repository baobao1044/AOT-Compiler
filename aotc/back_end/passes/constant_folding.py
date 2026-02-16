"""Constant folding optimization pass."""

from __future__ import annotations

from aotc.ir.cfg import FunctionIR
from aotc.ir.node import Alloca, BinOp, Call, Cast, Const, GEP, GetField, Load, Phi, PtrCast, Value


class ConstantFoldingPass:
    name = "constant-folding"

    def run(self, fn: FunctionIR) -> FunctionIR:
        known: dict[str, int | float | bool] = {}

        for block in fn.ordered_blocks():
            new_nodes = []
            for node in block.nodes:
                if isinstance(node, Const):
                    known[node.result.name] = node.value
                    new_nodes.append(node)
                    continue

                if isinstance(node, BinOp) and node.lhs.name in known and node.rhs.name in known:
                    folded = self._fold(node.op, known[node.lhs.name], known[node.rhs.name])
                    if folded is not None:
                        new_const = Const(result=node.result, value=folded)
                        known[node.result.name] = folded
                        new_nodes.append(new_const)
                        continue

                defined = self._defined_value(node)
                if defined is not None:
                    known.pop(defined.name, None)

                new_nodes.append(node)

            block.nodes = new_nodes

        return fn

    def _defined_value(self, node: object) -> Value | None:
        if isinstance(node, (BinOp, Phi, Alloca, GEP, GetField, Load, Cast, PtrCast)):
            return node.result
        if isinstance(node, Call):
            return node.result
        return None

    def _fold(self, op: str, lhs: int | float | bool, rhs: int | float | bool) -> int | float | bool | None:
        try:
            if op == "+":
                return lhs + rhs
            if op == "-":
                return lhs - rhs
            if op == "*":
                return lhs * rhs
            if op == "/":
                return lhs / rhs
            if op == "lt":
                return lhs < rhs
            if op == "le":
                return lhs <= rhs
            if op == "gt":
                return lhs > rhs
            if op == "ge":
                return lhs >= rhs
            if op == "eq":
                return lhs == rhs
            if op == "ne":
                return lhs != rhs
            if op == "id":
                return lhs
        except ZeroDivisionError:
            return None
        return None
