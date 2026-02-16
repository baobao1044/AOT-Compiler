# AOT-Compiler (AOTC) 🚀

**AOTC** is a high-performance, ahead-of-time (AOT) compiler pipeline for a typed subset of Python. It bridges the gap between Python's productivity and Native's performance by compiling Python code directly to optimized LLVM IR.

---

## 🌟 Key Breakthrough: The Zero-Copy Data Bridge

AOTC v0.3 introduces a revolutionary **Buffer Protocol Integration**. It allows `@native` functions to operate directly on external buffers (like **NumPy arrays**, `bytes`, or `array.array`) without any data copying.

- **Zero Overhead:** Pass 1GB of data in 0ms.
- **Native Speed:** Achieve C-level performance on your Python data structures.
- **Memory Safety:** Automatic buffer pinning ensures memory stays alive during native execution.

---

## 🛠️ Features & Roadmap

### ✅ v0.3: Data Bridge & Composite Types (Current)
- **Zero-Copy NDArray:** `NDArray[T]` support for seamless NumPy/Buffer integration.
- **Structured Data:** `@native_struct` for mapping `@dataclass` to LLVM Structs with deterministic layout.
- **Pointer Arithmetic:** Foundational IR nodes (`GetField`, `PtrCast`) for low-level memory control.
- **Static Guardrails:** Compile-time out-of-bounds checking for constant indices.

### ✅ v0.2: Memory, FFI & Parallelism
- **Memory Ops:** SSA-like IR with `Alloca`, `Load`, `Store`, and `GEP`.
- **Foreign Function Interface (FFI):** Call C libraries (`libc`, `libm`) via `@extern`.
- **Parallel Runtime:** Multi-threaded execution with `@parallel` and `parallel_for`.
- **Advanced Codegen:** Full support for Linux, macOS, and Windows.

### ✅ v0.1: The Foundation
- **Pipeline:** AST → AOTC IR → LLVM IR → Native Code.
- **Optimizations:** Constant folding and Dead Code Elimination (DCE).
- **Core Subset:** `int`, `float`, `bool`, `if/else`, `while`, `for range()`.

---

## 🚀 Quick Start

```bash
# Setup environment
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev,llvm]

# Run tests
pytest -v
```

### Build & Benchmark

```bash
# Build a shared library with O3 optimization
aotc build examples/numpy_blur.py --emit so --opt O3

# Run benchmarks
aotc bench --loop-count 10000000 --threads 4
```

---

## 💻 API Usage

### High-Performance Array Processing
```python
import numpy as np
from aotc import NDArray, native

@native
def blur_1d(src: NDArray[float], dst: NDArray[float], n: int) -> None:
    i = 1
    while i < n - 1:
        dst[i] = (src[i-1] + src[i] + src[i+1]) / 3.0
        i = i + 1
```

### Structured Data & FFI
```python
from aotc import native, native_struct, extern

@native_struct
class Point:
    x: float
    y: float

@extern("m")
def hypot(x: float, y: float) -> float: ...

@native
def distance_from_origin(p: Point) -> float:
    return hypot(p.x, p.y)
```

---

## 🏛️ Architecture

AOTC uses a multi-stage lowering process:
1. **Frontend:** Python AST is lowered to a custom SSA-based AOTC IR.
2. **Optimizer:** A custom PassManager runs CF, DCE, and Inlining.
3. **Backend:** AOTC IR is emitted as LLVM IR, then compiled by `clang` or `llvmlite`.
4. **Runtime:** A zero-copy loader pins memory and dispatches native calls via `ctypes`.

For more details, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/DATA_BRIDGE_V0_3.md](docs/DATA_BRIDGE_V0_3.md).

---

## 📜 License
AOTC is released under the MIT License. See `LICENSE` for details.
