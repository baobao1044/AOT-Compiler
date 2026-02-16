from __future__ import annotations

import time

import numpy as np

from aotc import NDArray, native


@native
def blur_1d(src: NDArray[float], dst: NDArray[float], n: int) -> None:
    dst[0] = src[0]
    i = 1
    while i < n - 1:
        dst[i] = (src[i - 1] + src[i] + src[i + 1]) / 3.0
        i = i + 1
    dst[n - 1] = src[n - 1]


if __name__ == "__main__":
    n = 2_000_000
    src = np.random.rand(n).astype(np.float64)
    dst = np.zeros_like(src)

    t0 = time.perf_counter()
    blur_1d(src, dst, n)
    elapsed = time.perf_counter() - t0

    print(f"blur_1d({n}) done in {elapsed:.6f}s")
    print(f"checksum={float(dst.sum()):.6f}")
