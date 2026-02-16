# AOTC v0.2 Roadmap

## Week 1 - Arrays + memory ops
- Add IR memory instructions: `Alloca`, `Load`, `Store`, `GEP`
- Parse static array subset: `a = [0] * n`, `a[i]`, `a[i] = expr`
- Reject dynamic list methods (`append`, etc.)
- Add array tests and compile+run `sum_array`

## Week 2 - Native calls + module linking
- Add `Call` node and function signature table
- Parse strict typed calls between native functions
- Compile multi-function modules and verify internal symbol linkage

## Week 3 - Optimizer controls
- Add CLI `--opt O0|O2|O3` and `--passes ...`
- Keep LLVM mem2reg optimization hook when llvmlite is available
- Add array-loop benchmark path

## Week 4 - FFI extern
- Add `@extern("lib")` API and extern declaration lowering
- Emit LLVM `declare` + platform link flags (`-lm` on Linux/macOS)
- Add `sin/cos` tests with tolerance checks

## Week 5 - Parallel runtime path
- Add `@native(parallel=True)` and `@parallel`
- Add runtime `parallel_for` helper with chunking
- Add threaded benchmark path for loop-heavy kernel

## Week 6 - Packaging + Windows + release
- Extend CI matrix to include Windows
- Add cibuildwheel workflow for Linux/macOS/Windows
- Update docs/examples/changelog and add v0.2 tagging script
