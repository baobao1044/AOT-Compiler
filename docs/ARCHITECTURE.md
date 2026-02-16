# AOTC Architecture (v0.3)

```mermaid
flowchart LR
    A[Python Source] --> B[FrontEndParser\nAST -> AOTC IR]
    B --> C[CFG + SSA/Memory/Composite IR\nConst/BinOp/Phi/Alloca/Load/Store/GEP/GetField/Call]
    C --> D[PassManager\nCF + DCE + optional Inline]
    D --> E[LLVMCodeGenerator\nLLVM IR (.ll)]
    E --> F[clang/lld + link libs\n.so/.dll/.dylib or .s]
    F --> G[Runtime Loader\nBuffer Bridge + ctypes]
```

## IR mapping (v0.3)
- `Alloca(type)` -> LLVM `alloca`
- `Load(ptr)` -> LLVM `load`
- `Store(ptr, val)` -> LLVM `store`
- `GEP(base_ptr, index)` -> LLVM `getelementptr`
- `GetField(base_ptr, index)` -> LLVM `getelementptr` (struct field access)
- `Call(name, args)` -> LLVM `call`
- `ExternDecl` -> LLVM `declare` + builder link flags

## Memory & Data Bridge (v0.3)
- **Zero-Copy Buffers:** `NDArray[T]` arguments use the Python Buffer Protocol to extract raw memory pointers.
- **Buffer Pinning:** `BufferHandle` objects ensure Python objects are not garbage collected while native code is executing.
- **Layout Calculation:** `@native_struct` classes have their memory layout (offsets and alignment) calculated deterministically at compile-time to match LLVM's expectations.

## Function calls and linkage
- Module-level signatures are collected before lowering.
- Cross-function calls within the same module are resolved at link-time.
- Extern declarations (`@extern("m")`) are emitted as LLVM declarations and linked by the backend builder.

## Parallel model
- Multi-threading is supported via a runtime thread pool.
- Users can trigger parallel execution using the `@parallel` decorator or `parallel_for` API.
- The compiler focuses on generating thread-safe kernels that operate on independent memory chunks.
