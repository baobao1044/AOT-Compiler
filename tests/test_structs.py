from __future__ import annotations

from aotc.front_end.parser import FrontEndParser


def test_lower_native_struct_dataclass_to_ir_struct() -> None:
    src = """
from dataclasses import dataclass
from aotc import native_struct

@native_struct
@dataclass
class Point:
    x: float
    y: float
    visible: bool

def noop() -> int:
    return 0
"""
    module = FrontEndParser().lower_module(src)
    assert "Point" in module.structs

    point = module.structs["Point"]
    assert [field.name for field in point.fields] == ["x", "y", "visible"]
    assert [field.typ for field in point.fields] == ["float", "float", "bool"]

    assert point.field_offsets == {"x": 0, "y": 8, "visible": 16}
    assert point.size == 24
    assert point.alignment == 8
