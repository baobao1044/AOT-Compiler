"""Type helpers for front-end lowering."""

from __future__ import annotations

import ast

from aotc.ir.node import ScalarType, TypeName, ptr_type


_SCALAR_BY_NAME: dict[str, ScalarType] = {
    "int": "int",
    "float": "float",
    "bool": "bool",
    "void": "void",
    "none": "void",
}

_BUFFER_BASE_NAMES = {"NDArray", "ndarray", "ArrayView", "Buffer", "Ptr", "Pointer"}


def annotation_to_typename(node: ast.expr | None) -> TypeName:
    if node is None:
        return "int"

    parsed = _annotation_expr_to_typename(node)
    if parsed is not None:
        return parsed

    return "int"


def merge_types(lhs: TypeName, rhs: TypeName) -> TypeName:
    if lhs == rhs:
        return lhs
    if lhs.startswith("ptr_") or rhs.startswith("ptr_"):
        raise TypeError(f"Cannot merge pointer-like types: {lhs} and {rhs}")
    if "float" in (lhs, rhs):
        return "float"
    if "bool" in (lhs, rhs):
        return "bool"
    return "int"


def _annotation_expr_to_typename(node: ast.expr) -> TypeName | None:
    if isinstance(node, ast.Name):
        mapped = _SCALAR_BY_NAME.get(node.id.lower())
        if mapped is not None:
            return mapped
        if node.id.startswith("ptr_"):
            elem = node.id[len("ptr_") :]
            if elem in {"int", "float", "bool"}:
                return node.id
        return None

    if isinstance(node, ast.Constant):
        if node.value is None:
            return "void"
        if isinstance(node.value, str):
            return _annotation_str_to_typename(node.value)
        return None

    if isinstance(node, ast.Subscript):
        base_name = _expr_name(node.value)
        base_leaf = base_name.split(".")[-1] if base_name else ""
        if base_name in _BUFFER_BASE_NAMES or base_leaf in _BUFFER_BASE_NAMES:
            elem_type = _slice_to_scalar(node.slice)
            return ptr_type(elem_type)
        return None

    if isinstance(node, ast.Attribute):
        if node.attr.lower() in _SCALAR_BY_NAME:
            return _SCALAR_BY_NAME[node.attr.lower()]
        return None

    return None


def _annotation_str_to_typename(value: str) -> TypeName:
    token = value.strip().replace(" ", "")
    lowered = token.lower()

    mapped = _SCALAR_BY_NAME.get(lowered)
    if mapped is not None:
        return mapped

    if token.startswith("ptr_"):
        elem = token[len("ptr_") :]
        if elem in {"int", "float", "bool"}:
            return token

    for base in _BUFFER_BASE_NAMES:
        prefix = f"{base}["
        if token.startswith(prefix) and token.endswith("]"):
            inner = token[len(prefix) : -1]
            elem = _scalar_from_name(inner)
            if elem is not None:
                return ptr_type(elem)

    return "int"


def _slice_to_scalar(node: ast.expr) -> ScalarType:
    if isinstance(node, ast.Tuple):
        raise TypeError("NDArray currently supports exactly one element type argument")

    if isinstance(node, ast.Name):
        scalar = _scalar_from_name(node.id)
        if scalar is not None:
            return scalar
        raise TypeError(f"Unsupported NDArray element type '{node.id}'")

    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            scalar = _scalar_from_name(node.value)
            if scalar is not None:
                return scalar
            raise TypeError(f"Unsupported NDArray element type '{node.value}'")
        raise TypeError("NDArray element type must be a scalar type name")

    if isinstance(node, ast.Attribute):
        scalar = _scalar_from_name(node.attr)
        if scalar is not None:
            return scalar
        raise TypeError(f"Unsupported NDArray element type '{node.attr}'")

    raise TypeError(f"Unsupported NDArray element type node: {type(node).__name__}")


def _scalar_from_name(name: str) -> ScalarType | None:
    return _SCALAR_BY_NAME.get(name.strip().lower())


def _expr_name(expr: ast.expr) -> str:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        parent = _expr_name(expr.value)
        if parent:
            return f"{parent}.{expr.attr}"
        return expr.attr
    return ""
