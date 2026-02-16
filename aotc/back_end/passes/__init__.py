"""Optimization passes."""

from aotc.back_end.passes.constant_folding import ConstantFoldingPass
from aotc.back_end.passes.dead_code import DeadCodeEliminationPass
from aotc.back_end.passes.inline import InlinePass

__all__ = ["ConstantFoldingPass", "DeadCodeEliminationPass", "InlinePass"]
