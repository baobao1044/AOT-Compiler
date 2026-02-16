# Changelog

## v0.2.0 - 2026-02-16
- Added memory IR nodes: `Alloca`, `Load`, `Store`, `GEP`
- Added static array lowering (`a = [0] * n`, indexing read/write)
- Added native-to-native call lowering and strict signature type-checking
- Added extern declarations via `@extern("lib")` and LLVM `declare` emission
- Added builder library linking support (`-lm` mapping)
- Added CLI optimization controls: `--opt` and `--passes`
- Added benchmark entries for `array_loop` and threaded mandelbrot path
- Added runtime APIs: `extern`, `parallel`, `parallel_for`
- Extended CI to Linux/macOS/Windows and added cibuildwheel workflow

## v0.1.0 - 2026-02-16
- Added CLI commands: `build`, `clean`, `bench`
- Added front-end lowering for arithmetic and control-flow (`if/else`, `while`, `for range()`)
- Added SSA-like IR nodes (`Const`, `BinOp`, `Phi`, `Branch`, `Return`)
- Added optimization passes: constant folding + dead-code elimination
- Added LLVM IR code generation and clang/lld artifact build
- Added runtime loader and `@native` decorator API
- Added benchmark suite and reporting
- Added CI workflow for Linux/macOS with Python 3.9-3.12
