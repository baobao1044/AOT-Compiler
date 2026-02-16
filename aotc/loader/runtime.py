"""Runtime loader and decorators for AOTC."""

from __future__ import annotations

import concurrent.futures
import ctypes
import inspect
import os
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Generic, TypeVar, get_args, get_origin

from aotc.errors import RuntimeErrorAOTC
from aotc.pipeline import Pipeline


TScalar = TypeVar("TScalar", int, float, bool)


class NDArray(Generic[TScalar]):
    """Typing marker for native buffer arguments."""


@dataclass(slots=True)
class ExternSpec:
    lib: str
    fn: Callable[..., Any]


_NATIVE_REGISTRY: dict[str, dict[str, Callable[..., Any]]] = {}
_EXTERN_REGISTRY: dict[str, dict[str, ExternSpec]] = {}
_STRUCT_REGISTRY: dict[str, dict[str, type[Any]]] = {}


@dataclass(slots=True)
class BufferHandle:
    address: int
    nbytes: int
    itemsize: int
    readonly: bool
    format: str | None
    ndim: int
    shape: tuple[int, ...]
    strides: tuple[int, ...] | None
    owner: Any = field(repr=False)
    view: memoryview | None = field(repr=False, default=None)
    _released: bool = field(repr=False, default=False)

    def release(self) -> None:
        if self._released:
            return
        if self.view is not None:
            self.view.release()
        self.owner = None
        self.view = None
        self._released = True

    def __enter__(self) -> BufferHandle:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        self.release()
        return False


@dataclass(slots=True)
class _NativeArgSpec:
    ctype: Any
    kind: str
    elem_type: str | None = None
    writable: bool = False


def init_patch_table() -> None:
    """Initialize runtime patch state at import time (MVP placeholder)."""
    return None


def acquire_buffer(
    obj: Any,
    *,
    writable: bool = False,
    require_c_contiguous: bool = True,
) -> BufferHandle:
    """Extract a zero-copy raw pointer from a Python buffer-protocol object."""
    try:
        view = memoryview(obj)
    except TypeError as exc:
        raise RuntimeErrorAOTC("Object does not support the buffer protocol") from exc

    if writable and view.readonly:
        view.release()
        raise RuntimeErrorAOTC("Writable buffer required, got read-only object")

    if require_c_contiguous and not view.c_contiguous:
        view.release()
        raise RuntimeErrorAOTC("AOTC requires C-contiguous buffers for NDArray arguments")

    address = _buffer_address(obj, view, writable=writable)
    return BufferHandle(
        address=address,
        nbytes=view.nbytes,
        itemsize=view.itemsize,
        readonly=view.readonly,
        format=view.format,
        ndim=view.ndim,
        shape=tuple(view.shape),
        strides=tuple(view.strides) if view.strides is not None else None,
        owner=obj,
        view=view,
    )


def load_shared_library(path: str | Path) -> ctypes.CDLL:
    lib_path = Path(path).resolve()
    if not lib_path.exists():
        raise RuntimeErrorAOTC(f"Shared library not found: {lib_path}")

    if sys.platform.startswith("win") and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(lib_path.parent))

    return ctypes.CDLL(str(lib_path))


def load_symbol(
    path: str | Path,
    symbol: str,
    restype: Any,
    argtypes: list[Any],
) -> Any:
    lib = load_shared_library(path)
    try:
        fn = getattr(lib, symbol)
    except AttributeError as exc:
        raise RuntimeErrorAOTC(f"Symbol '{symbol}' not found in {path}") from exc
    fn.restype = restype
    fn.argtypes = argtypes
    return fn


def extern(lib: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Declare an external C symbol for AOTC lowering."""
    if not isinstance(lib, str) or lib.strip() == "":
        raise RuntimeErrorAOTC("@extern requires a non-empty library name string")

    def decorator(py_fn: Callable[..., Any]) -> Callable[..., Any]:
        module_registry = _EXTERN_REGISTRY.setdefault(py_fn.__module__, {})
        module_registry[py_fn.__name__] = ExternSpec(lib=lib, fn=py_fn)
        return py_fn

    return decorator


def native_struct(cls: type[Any]) -> type[Any]:
    """Mark a dataclass-like type as native struct metadata source."""
    module_registry = _STRUCT_REGISTRY.setdefault(cls.__module__, {})
    module_registry[cls.__name__] = cls
    return cls


def native(
    func: Callable[..., Any] | None = None,
    *,
    parallel: bool = False,
    threads: int | None = None,
) -> Callable[..., Any]:
    """Compile decorated function to native code on first invocation."""

    def decorator(py_fn: Callable[..., Any]) -> Callable[..., Any]:
        module_registry = _NATIVE_REGISTRY.setdefault(py_fn.__module__, {})
        module_registry[py_fn.__name__] = py_fn

        cached_native: dict[str, Any] = {}

        @wraps(py_fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if kwargs:
                raise RuntimeErrorAOTC("@native currently supports positional arguments only")

            if "fn" not in cached_native:
                native_fn = _compile_callable(py_fn, parallel=parallel, threads=threads)
                cached_native["fn"] = native_fn
            return cached_native["fn"](*args)

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def parallel(
    func: Callable[..., Any] | None = None,
    *,
    threads: int | None = None,
) -> Callable[..., Any]:
    """Decorator alias for @native(parallel=True)."""

    if func is not None:
        return native(func, parallel=True, threads=threads)
    return native(parallel=True, threads=threads)


def parallel_for(
    start: int,
    stop: int,
    body: Callable[[int, int], Any],
    threads: int = 1,
) -> list[Any]:
    """Run a chunked range body in parallel threads."""
    if threads <= 1:
        return [body(start, stop)]

    chunks = _chunk_ranges(start, stop, threads)
    results: list[Any] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(body, chunk_start, chunk_end) for chunk_start, chunk_end in chunks]
        for future in futures:
            results.append(future.result())
    return results


def _compile_callable(py_fn: Callable[..., Any], parallel: bool, threads: int | None) -> Any:
    source = _build_compilation_unit(py_fn)

    signature = inspect.signature(py_fn)
    arg_specs = [_annotation_to_arg_spec(param.annotation) for param in signature.parameters.values()]
    argtypes = [spec.ctype for spec in arg_specs]
    restype = _annotation_to_return_ctype(signature.return_annotation)

    opt_level = "O3" if parallel else "O2"
    if threads is not None and threads <= 0:
        raise RuntimeErrorAOTC("@native(parallel=...) threads must be positive")

    with tempfile.TemporaryDirectory(prefix="aotc-native-") as tmp:
        tmp_dir = Path(tmp)
        src_path = tmp_dir / f"{py_fn.__module__.replace('.', '_')}.py"
        src_path.write_text(source + "\n", encoding="utf-8")

        artifacts = Pipeline(opt_level=opt_level).compile_file(src_path, emit="so", out_dir=tmp_dir)
        if artifacts.artifact_path is None:
            raise RuntimeErrorAOTC("Pipeline produced no artifact for @native function")

        native_symbol = load_symbol(artifacts.artifact_path, py_fn.__name__, restype=restype, argtypes=argtypes)
        return _bind_native_symbol(native_symbol, arg_specs)


def _build_compilation_unit(py_fn: Callable[..., Any]) -> str:
    module_name = py_fn.__module__
    externs = _EXTERN_REGISTRY.get(module_name, {})
    natives = _NATIVE_REGISTRY.get(module_name, {})
    structs = _STRUCT_REGISTRY.get(module_name, {})

    sections: list[str] = []

    if externs:
        sections.append("from aotc import extern")
    if structs:
        sections.append("from dataclasses import dataclass")

    extern_items = sorted(externs.values(), key=lambda item: _safe_source_line(item.fn))
    for item in extern_items:
        source = _safe_getsource(item.fn, required=False)
        if source is not None:
            sections.append(textwrap.dedent(source).strip())

    struct_items = sorted(structs.values(), key=_safe_source_line)
    for cls in struct_items:
        source = _safe_getsource(cls, required=False)
        if source is None:
            continue
        sections.append(textwrap.dedent(source).strip())

    native_items = sorted(natives.values(), key=lambda fn: _safe_source_line(fn))
    if not native_items:
        native_items = [py_fn]

    for fn in native_items:
        source = _safe_getsource(fn, required=(fn is py_fn))
        if source is None:
            continue
        clean_source = _strip_decorators(textwrap.dedent(source))
        sections.append(clean_source.strip())

    return "\n\n".join(section for section in sections if section)


def _strip_decorators(source: str) -> str:
    lines = source.splitlines()
    while lines and lines[0].strip().startswith("@"):
        lines.pop(0)
    return "\n".join(lines)


def _bind_native_symbol(native_symbol: Any, arg_specs: list[_NativeArgSpec]) -> Callable[..., Any]:
    def invoke(*args: Any) -> Any:
        if len(args) != len(arg_specs):
            raise RuntimeErrorAOTC(
                f"Expected {len(arg_specs)} arguments, got {len(args)}"
            )

        converted: list[Any] = []
        pinned: list[BufferHandle] = []
        try:
            for arg, spec in zip(args, arg_specs):
                if spec.kind == "buffer":
                    handle = acquire_buffer(arg, writable=spec.writable, require_c_contiguous=True)
                    _validate_buffer_element_type(handle, spec.elem_type or "")
                    pinned.append(handle)
                    converted.append(ctypes.c_void_p(handle.address))
                    continue

                converted.append(arg)

            return native_symbol(*converted)
        finally:
            for handle in reversed(pinned):
                handle.release()

    return invoke


def _annotation_to_arg_spec(annotation: Any) -> _NativeArgSpec:
    scalar = _annotation_to_scalar(annotation)
    if scalar is not None:
        return _NativeArgSpec(ctype=_scalar_ctype(scalar), kind="scalar")

    buffer_elem = _annotation_to_buffer_elem(annotation)
    if buffer_elem is not None:
        return _NativeArgSpec(ctype=ctypes.c_void_p, kind="buffer", elem_type=buffer_elem)

    raise RuntimeErrorAOTC(
        "@native requires explicit annotations: int/float/bool or NDArray[int|float|bool]"
    )


def _annotation_to_return_ctype(annotation: Any) -> Any:
    if annotation in (None, "None", type(None), "void"):
        return None

    scalar = _annotation_to_scalar(annotation)
    if scalar is not None:
        return _scalar_ctype(scalar)

    buffer_elem = _annotation_to_buffer_elem(annotation)
    if buffer_elem is not None:
        return ctypes.c_void_p

    raise RuntimeErrorAOTC(
        "@native return annotation must be int/float/bool/None or pointer-compatible"
    )


def _annotation_to_scalar(annotation: Any) -> str | None:
    if annotation in (int, "int"):
        return "int"
    if annotation in (float, "float"):
        return "float"
    if annotation in (bool, "bool"):
        return "bool"

    if isinstance(annotation, str):
        lowered = annotation.strip().replace(" ", "").lower()
        if lowered in {"int", "builtins.int"}:
            return "int"
        if lowered in {"float", "builtins.float"}:
            return "float"
        if lowered in {"bool", "builtins.bool"}:
            return "bool"

    return None


def _annotation_to_buffer_elem(annotation: Any) -> str | None:
    if isinstance(annotation, str):
        return _buffer_elem_from_text(annotation)

    origin = get_origin(annotation)
    if origin is NDArray:
        args = get_args(annotation)
        if len(args) != 1:
            raise RuntimeErrorAOTC("NDArray[...] requires exactly one scalar element type")
        scalar = _annotation_to_scalar(args[0])
        if scalar is None:
            raise RuntimeErrorAOTC("NDArray element type must be int/float/bool")
        return scalar

    return None


def _buffer_elem_from_text(text: str) -> str | None:
    token = text.strip().replace(" ", "")
    if token.startswith("ptr_"):
        suffix = token[len("ptr_") :].lower()
        if suffix in {"int", "float", "bool"}:
            return suffix

    lowered = token.lower()
    if "[" in lowered and lowered.endswith("]"):
        base, inner = lowered.split("[", 1)
        base_leaf = base.split(".")[-1]
        inner_type = inner[:-1]
        if base_leaf in {"ndarray", "arrayview", "buffer", "pointer", "ptr"}:
            if inner_type in {"int", "float", "bool"}:
                return inner_type

    return None


def _scalar_ctype(scalar: str) -> Any:
    if scalar == "int":
        return ctypes.c_longlong
    if scalar == "float":
        return ctypes.c_double
    if scalar == "bool":
        return ctypes.c_bool
    raise RuntimeErrorAOTC(f"Unsupported scalar type '{scalar}'")


def _validate_buffer_element_type(handle: BufferHandle, elem_type: str) -> None:
    if elem_type == "int":
        if handle.itemsize != 8:
            raise RuntimeErrorAOTC("NDArray[int] requires 8-byte integer buffers")
        return
    if elem_type == "float":
        if handle.itemsize != 8:
            raise RuntimeErrorAOTC("NDArray[float] requires 8-byte floating-point buffers")
        return
    if elem_type == "bool":
        if handle.itemsize != 1:
            raise RuntimeErrorAOTC("NDArray[bool] requires 1-byte boolean buffers")
        return
    raise RuntimeErrorAOTC(f"Unsupported NDArray element type '{elem_type}'")


def _safe_source_line(obj: Any) -> int:
    try:
        return inspect.getsourcelines(obj)[1]
    except OSError:
        return 10**9


def _safe_getsource(obj: Any, required: bool) -> str | None:
    try:
        return inspect.getsource(obj)
    except OSError as exc:
        if required:
            name = getattr(obj, "__name__", "<unknown>")
            raise RuntimeErrorAOTC(
                f"Could not read source for function '{name}'. "
                "Define @native functions in a regular Python module file."
            ) from exc
        return None


def _chunk_ranges(start: int, stop: int, chunks: int) -> list[tuple[int, int]]:
    total = max(0, stop - start)
    base = total // chunks
    extra = total % chunks

    result: list[tuple[int, int]] = []
    cursor = start
    for i in range(chunks):
        width = base + (1 if i < extra else 0)
        next_cursor = cursor + width
        result.append((cursor, next_cursor))
        cursor = next_cursor
    return result


def _buffer_address(obj: Any, view: memoryview, writable: bool) -> int:
    if view.nbytes == 0:
        return 0

    if isinstance(obj, bytes):
        pybytes_as_string = ctypes.pythonapi.PyBytes_AsString
        pybytes_as_string.argtypes = [ctypes.py_object]
        pybytes_as_string.restype = ctypes.c_void_p
        address = int(pybytes_as_string(obj))
        if address == 0:
            raise RuntimeErrorAOTC("Could not extract raw pointer from bytes object")
        return address

    if view.readonly and not writable:
        raise RuntimeErrorAOTC(
            "Read-only buffers are only supported for 'bytes' in v0.3 MVP"
        )

    try:
        return ctypes.addressof(ctypes.c_ubyte.from_buffer(view))
    except (TypeError, BufferError) as exc:
        raise RuntimeErrorAOTC(
            "Could not obtain writable zero-copy pointer from buffer object"
        ) from exc


init_patch_table()
