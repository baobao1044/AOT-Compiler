# AOTC v0.1 Roadmap (8 weeks)

## Week 1: Repo bootstrap + CLI
- Initialize packaging (`hatchling`) and dev tooling (`pre-commit`, `ruff`, `pytest`).
- Implement `aotc build <file.py>` command with argparse.
- Create package skeleton for front-end and back-end.

## Week 2: IR and arithmetic
- Define Node + SSA Value model.
- Lower AST to IR for primitive types and `+ - * / return`.
- Add unit tests.

## Week 3: Control-flow
- Build CFG with basic blocks.
- Support `if/else`, `while`, `for range()`.
- Add Phi nodes and loop tests.

## Week 4: LLVM + shared object
- Integrate llvmlite.
- Lower AOTC IR to LLVM IR.
- Build `.so` / `.dll` and support `--emit=asm`.

## Week 5: Loader and patcher
- Implement `loader/patcher.c` for runtime function patching.
- Load shared object with `ctypes` or `cffi`.
- Add benchmark for 10M loop iterations.

## Week 6: Lightweight optimizer
- Constant folding.
- Dead-code elimination.
- Re-run benchmarks and capture metrics.

## Week 7: DX and docs
- `@native` decorator API with clear errors.
- Add `README.md`, `CONTRIBUTING.md`, architecture diagram.
- Configure CI for lint/test/build (Linux + macOS, Python 3.9-3.12).

## Week 8: Release and distribution
- Tag `v0.1.0` and publish to PyPI.
- Publish benchmark post and social announcements.
