# Technical Mapping Checklist (v0.2)

## IR mapping
- `Alloca(type)` -> LLVM `alloca`
- `Load(ptr)` -> LLVM `load`
- `Store(ptr, val)` -> LLVM `store`
- `GEP(base_ptr, index)` -> LLVM `getelementptr`
- `Call(name, args)` -> LLVM `call`
- `ExternDecl` -> LLVM `declare` + builder link flags

## CLI mapping
- `aotc build file.py --emit so|asm|ll`
- `aotc build file.py --opt O3 --passes cf,dce,inline`
- `aotc bench --threads 8`

## Release mapping
- `CHANGELOG.md` includes `v0.2.0`
- `scripts/tag_release_v0_2.sh` added
- CI covers Linux/macOS/Windows and wheel build workflow
