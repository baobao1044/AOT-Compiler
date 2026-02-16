"""Build LLVM IR into platform artifacts using clang/lld."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from aotc.errors import BuildError


def shared_lib_suffix() -> str:
    if sys.platform.startswith("win"):
        return ".dll"
    if sys.platform == "darwin":
        return ".dylib"
    return ".so"


def compile_llvm_ir(
    ll_path: Path,
    output_path: Path,
    emit: str = "so",
    opt_level: str = "O2",
    link_libs: list[str] | None = None,
) -> Path:
    clang = shutil.which("clang")
    if clang is None:
        raise BuildError("clang is required but was not found in PATH")

    if not ll_path.exists():
        raise BuildError(f"LLVM IR file does not exist: {ll_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    opt_flag = _normalize_opt_flag(opt_level)

    cmd = [clang]
    if emit == "asm":
        cmd += [opt_flag, "-S", "-x", "ir", str(ll_path), "-o", str(output_path)]
    elif emit == "so":
        cmd += ["-shared", opt_flag]
        if not sys.platform.startswith("win"):
            cmd.append("-fPIC")
        if shutil.which("ld.lld") is not None:
            cmd.append("-fuse-ld=lld")
        if sys.platform.startswith("win"):
            cmd.append("-Wl,--export-all-symbols")

        cmd += ["-x", "ir", str(ll_path), "-o", str(output_path)]
        cmd += _link_flags(link_libs or [])
    else:
        raise BuildError(f"Unsupported emit kind: {emit}")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or "<no stderr>"
        raise BuildError(f"clang failed (exit={proc.returncode}): {stderr}")

    return output_path


def _normalize_opt_flag(opt_level: str) -> str:
    normalized = opt_level.upper()
    if normalized not in {"O0", "O2", "O3"}:
        raise BuildError(f"Unsupported opt level '{opt_level}'")
    return f"-{normalized.lower()}"


def _link_flags(libs: list[str]) -> list[str]:
    flags: list[str] = []
    seen: set[str] = set()

    for lib in libs:
        mapped = _map_lib_name(lib)
        if mapped in seen:
            continue
        seen.add(mapped)
        flags.append(f"-l{mapped}")

    return flags


def _map_lib_name(lib: str) -> str:
    if lib == "m":
        if sys.platform.startswith("win"):
            return "msvcrt"
        return "m"
    return lib
