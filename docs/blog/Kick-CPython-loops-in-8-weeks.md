# Kick CPython's loops in 8 weeks

AOTC v0.1 proves a practical path from Python AST to native shared objects for loop-heavy code.

## Build phases
1. AST -> SSA-like IR
2. IR optimization (constant folding + DCE)
3. LLVM IR emission
4. clang/lld shared-object build
5. Runtime loading with ctypes

## Key benchmark takeaway
`heavy_loop` is the first target where AOTC can compare against CPython in a repeatable flow.

## Next roadmap
- richer typing
- recursion lowering
- stronger SSA construction
- true PyFunctionObject patching in loader
