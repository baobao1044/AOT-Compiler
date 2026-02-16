# AOTC v0.2 social drafts

## Twitter/X
AOTC v0.2 is out: static arrays + native calls + extern FFI + parallel runtime APIs.
Compile Python subset -> LLVM IR -> native .so/.dll with `aotc build`.

## Reddit
Shipped AOTC v0.2 with memory IR (`alloca/load/store/gep`), typed call lowering, and `@extern("m")` interop.
Bench now includes array loops and threaded kernel path.

## Hacker News
Show HN: AOTC v0.2 adds arrays, calls, FFI, and parallel runtime helpers to a Python subset AOT compiler.
Focus is still educational compiler stages with executable artifacts and tests.
