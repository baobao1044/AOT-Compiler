"""Project-specific exceptions for AOTC."""

from __future__ import annotations


class AOTCError(Exception):
    """Base error for AOTC."""


class FrontEndError(AOTCError):
    """Raised for AST-to-IR lowering failures."""


class CodegenError(AOTCError):
    """Raised for IR-to-LLVM failures."""


class BuildError(AOTCError):
    """Raised for external toolchain failures."""


class RuntimeErrorAOTC(AOTCError):
    """Raised for runtime loader/decorator failures."""
