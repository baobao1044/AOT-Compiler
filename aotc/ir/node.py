"""Core IR node and SSA/composite/memory value types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ScalarType = Literal["int", "float", "bool", "void"]
TypeName = str


def is_scalar_type(typ: TypeName) -> bool:
    return typ in {"int", "float", "bool", "void"}


def ptr_type(elem_type: TypeName) -> TypeName:
    return f"ptr_{elem_type}"


def pointee_type(typ: TypeName) -> TypeName | None:
    if typ.startswith("ptr_"):
        return typ[len("ptr_") :]
    return None


@dataclass(slots=True, frozen=True)
class Value:
    name: str
    typ: TypeName


@dataclass(slots=True, frozen=True)
class StructField:
    name: str
    typ: TypeName


@dataclass(slots=True)
class StructDef:
    name: str
    fields: list[StructField]
    field_offsets: dict[str, int] = field(default_factory=dict)
    size: int | None = None
    alignment: int | None = None
    packed: bool = False


@dataclass(slots=True)
class Const:
    result: Value
    value: int | float | bool


@dataclass(slots=True)
class BinOp:
    op: str
    lhs: Value
    rhs: Value
    result: Value


@dataclass(slots=True)
class Phi:
    result: Value
    incomings: dict[str, Value] = field(default_factory=dict)


@dataclass(slots=True)
class Alloca:
    result: Value
    elem_type: ScalarType
    count: Value | None = None
    zero_init: bool = False


@dataclass(slots=True)
class Load:
    ptr: Value
    result: Value
    elem_type: ScalarType


@dataclass(slots=True)
class Store:
    ptr: Value
    value: Value
    elem_type: ScalarType


@dataclass(slots=True)
class GEP:
    base_ptr: Value
    index: Value
    result: Value
    elem_type: TypeName


@dataclass(slots=True)
class GetField:
    base_ptr: Value
    result: Value
    struct_name: str
    field_name: str
    field_index: int


@dataclass(slots=True)
class PtrCast:
    value: Value
    target_type: TypeName
    result: Value


@dataclass(slots=True)
class Call:
    func_name: str
    args: list[Value]
    return_type: TypeName
    result: Value | None


@dataclass(slots=True)
class Cast:
    value: Value
    target_type: ScalarType
    result: Value


@dataclass(slots=True)
class ExternDecl:
    name: str
    lib: str
    arg_types: list[TypeName]
    return_type: TypeName


@dataclass(slots=True)
class Branch:
    cond: Value
    true_label: str
    false_label: str


@dataclass(slots=True)
class Jump:
    target: str


@dataclass(slots=True)
class Return:
    value: Value | None


Instruction = (
    Const | BinOp | Phi | Alloca | Load | Store | GEP | GetField | PtrCast | Call | Cast
)
Terminator = Branch | Jump | Return


def is_terminator(node: object) -> bool:
    return isinstance(node, (Branch, Jump, Return))
