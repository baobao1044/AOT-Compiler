# AOTC v0.2 Implementation Status

Date: 2026-02-16

## Week 1 - Static arrays + memory ops
- Completed: IR nodes `Alloca/Load/Store/GEP`
- Completed: parser support for `a = [0] * n`, `a[i]`, `a[i] = expr`
- Completed: array compile/run tests

## Week 2 - Native calls + module linking
- Completed: `Call` node and module signature table
- Completed: strict typed call lowering across functions
- Completed: multi-function module compile + internal symbol resolution

## Week 3 - Optimizer v0.2
- Completed: CLI opt controls (`O0/O2/O3`)
- Completed: pass selection (`cf,dce,inline`)
- Completed: LLVM mem2reg hook path when llvmlite exists; clang opt fallback otherwise
- Completed: array loop benchmark entry

## Week 4 - FFI extern
- Completed: `@extern("lib")` API and lowering to `ExternDecl`
- Completed: LLVM `declare` emission + platform link flags (`-lm` mapping)
- Completed: `sin/cos` FFI tests

## Week 5 - Parallel runtime API
- Completed: `@native(parallel=True)`, `@parallel`, `parallel_for`
- Completed: threaded benchmark path using chunked native calls
- Limitation: compiler-side loop-to-thread transformation remains conservative in v0.2

## Week 6 - Packaging + Windows + release assets
- Completed: CI matrix extended to include Windows
- Completed: cibuildwheel workflow added
- Completed: docs/examples/changelog updated for v0.2
- Completed: `scripts/tag_release_v0_2.sh`
