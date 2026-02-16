"""Dead code elimination optimization pass."""

from __future__ import annotations

from aotc.ir.cfg import FunctionIR
from aotc.ir.node import (
    Alloca,
    BinOp,
    Branch,
    Call,
    Cast,
    Const,
    GEP,
    GetField,
    Jump,
    Load,
    Phi,
    PtrCast,
    Return,
    Store,
)


class DeadCodeEliminationPass:
    name = "dead-code-elimination"

    def run(self, fn: FunctionIR) -> FunctionIR:
        changed = True
        while changed:
            changed = False
            referenced = self._collect_referenced_values(fn)

            for block in fn.ordered_blocks():
                kept = []
                for node in block.nodes:
                    if self._can_drop(node) and node.result is not None and node.result.name not in referenced:
                        changed = True
                        continue
                    kept.append(node)
                block.nodes = kept

        return fn

    def _collect_referenced_values(self, fn: FunctionIR) -> set[str]:
        names: set[str] = set()

        for block in fn.ordered_blocks():
            for node in block.nodes:
                if isinstance(node, BinOp):
                    names.add(node.lhs.name)
                    names.add(node.rhs.name)
                elif isinstance(node, Phi):
                    for incoming in node.incomings.values():
                        names.add(incoming.name)
                elif isinstance(node, Alloca) and node.count is not None:
                    names.add(node.count.name)
                elif isinstance(node, GEP):
                    names.add(node.base_ptr.name)
                    names.add(node.index.name)
                elif isinstance(node, GetField):
                    names.add(node.base_ptr.name)
                elif isinstance(node, Load):
                    names.add(node.ptr.name)
                elif isinstance(node, Cast):
                    names.add(node.value.name)
                elif isinstance(node, PtrCast):
                    names.add(node.value.name)
                elif isinstance(node, Store):
                    names.add(node.ptr.name)
                    names.add(node.value.name)
                elif isinstance(node, Call):
                    for arg in node.args:
                        names.add(arg.name)

            term = block.terminator
            if isinstance(term, Branch):
                names.add(term.cond.name)
            elif isinstance(term, Return) and term.value is not None:
                names.add(term.value.name)
            elif isinstance(term, Jump):
                pass

        return names

    def _can_drop(self, node: object) -> bool:
        return isinstance(node, (Const, BinOp, Phi, Alloca, GEP, GetField, Load, Cast, PtrCast))
