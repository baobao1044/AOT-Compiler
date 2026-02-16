# Data Bridge v0.3 (Zero-copy Buffer Protocol)

## Goal
- Accept Python buffer objects (`numpy.ndarray`, `array.array`, `bytes`) in `@native`.
- Avoid data copy by passing raw memory pointers directly to compiled code.
- Keep objects pinned during native execution to prevent lifetime bugs.

## Type Mapping
- `NDArray[int]` -> internal `ptr_int`
- `NDArray[float]` -> internal `ptr_float`
- `NDArray[bool]` -> internal `ptr_bool`

Frontend lowering treats pointer args as indexable buffers:
- `a[i]` -> `GEP + Load`
- `a[i] = x` -> `GEP + Store`

## Runtime Bridge
- `acquire_buffer(obj)` builds a `memoryview` and extracts raw pointer.
- `BufferHandle` stores:
  - `address`, `nbytes`, `itemsize`, `shape`, `strides`, `format`
  - strong references (`owner`, `view`) to keep memory alive.
- `@native` wrapper converts `NDArray[...]` arguments to `c_void_p` and pins handles for call duration.

## Safety (v0.3 MVP)
- Requires C-contiguous buffers.
- Enforces element size:
  - `int`: 8 bytes
  - `float`: 8 bytes
  - `bool`: 1 byte
- Read-only buffers are currently supported for `bytes`; writable buffers are required for mutable array objects.

## IR Extensions
- `StructDef`, `StructField`
- `GetField` (field-pointer access)
- `PtrCast` (ptr<->int and ptr->ptr cast path)

These are foundation pieces for upcoming composite-type and FFI-heavy stages.
