"""AOTC package."""

from aotc.loader.runtime import (
    NDArray,
    acquire_buffer,
    extern,
    native,
    native_struct,
    parallel,
    parallel_for,
)

__all__ = [
    "__version__",
    "native",
    "native_struct",
    "extern",
    "parallel",
    "parallel_for",
    "NDArray",
    "acquire_buffer",
]
__version__ = "0.2.0"
