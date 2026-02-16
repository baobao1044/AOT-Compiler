from __future__ import annotations

from aotc.back_end.codegen import LLVMCodeGenerator
from aotc.front_end.parser import FrontEndParser


def test_codegen_generates_define_and_ret() -> None:
    src = """
def add(a: int, b: int) -> int:
    c = a + b
    return c
"""
    module = FrontEndParser().lower_module(src)
    result = LLVMCodeGenerator().emit_module(module)
    assert "define dso_local i64 @add" in result.llvm_ir
    assert "ret i64" in result.llvm_ir


def test_codegen_emits_struct_type_definition() -> None:
    src = """
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float

def noop() -> int:
    return 0
"""
    module = FrontEndParser().lower_module(src)
    result = LLVMCodeGenerator().emit_module(module)
    assert "%struct.Point = type { double, double }" in result.llvm_ir
