"""Benchmark suite for CPython vs AOTC."""

from __future__ import annotations

import concurrent.futures
import ctypes
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from aotc.loader.runtime import load_symbol
from aotc.pipeline import Pipeline


@dataclass(slots=True)
class BenchResult:
    name: str
    cpython_ms: float
    aotc_ms: float | None
    speedup: float | None
    notes: str = ""


def heavy_loop(n: int) -> int:
    total = 0
    i = 0
    while i < n:
        total = total + i * 2
        i = i + 1
    return total


def array_loop(n: int) -> int:
    a = [0] * n
    i = 0
    while i < n:
        a[i] = i
        i = i + 1

    total = 0
    j = 0
    while j < n:
        total = total + a[j]
        j = j + 1
    return total


def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


def mandelbrot(iterations: int) -> int:
    total = 0
    limit = iterations * 200_000
    i = 0
    while i < limit:
        total = total + i * 31 + 7
        i = i + 1
    return total


def run_suite(
    loop_n: int = 10_000_000,
    repeats: int = 3,
    threads: int = 1,
    opt_level: str = "O2",
) -> list[BenchResult]:
    results = [
        _bench_heavy_loop(loop_n, repeats, opt_level),
        _bench_array_loop(min(loop_n, 2_000_000), repeats, opt_level),
        _bench_fib(30, repeats),
        _bench_mandelbrot(30, repeats, max(1, threads), opt_level),
    ]
    return results


def _bench_heavy_loop(loop_n: int, repeats: int, opt_level: str) -> BenchResult:
    py_ms = _time_ms(lambda: heavy_loop(loop_n), repeats)

    source = """
def heavy_loop(n: int) -> int:
    total = 0
    i = 0
    while i < n:
        total = total + i * 2
        i = i + 1
    return total
""".strip()

    try:
        with tempfile.TemporaryDirectory(prefix="aotc-bench-") as tmp:
            tmp_dir = Path(tmp)
            src_path = tmp_dir / "heavy_loop.py"
            src_path.write_text(source + "\n", encoding="utf-8")
            artifacts = Pipeline(opt_level=opt_level).compile_file(src_path, emit="so", out_dir=tmp_dir)
            symbol = load_symbol(
                artifacts.artifact_path,
                "heavy_loop",
                restype=ctypes.c_longlong,
                argtypes=[ctypes.c_longlong],
            )
            aotc_ms = _time_ms(lambda: symbol(loop_n), repeats)
            return BenchResult(
                name="heavy_loop",
                cpython_ms=py_ms,
                aotc_ms=aotc_ms,
                speedup=py_ms / aotc_ms if aotc_ms > 0 else None,
            )
    except Exception as exc:  # pragma: no cover - depends on local toolchain
        return BenchResult(
            name="heavy_loop",
            cpython_ms=py_ms,
            aotc_ms=None,
            speedup=None,
            notes=f"AOTC compile/load failed: {exc}",
        )


def _bench_array_loop(loop_n: int, repeats: int, opt_level: str) -> BenchResult:
    py_ms = _time_ms(lambda: array_loop(loop_n), repeats)

    source = """
def array_loop(n: int) -> int:
    a = [0] * n
    i = 0
    while i < n:
        a[i] = i
        i = i + 1

    total = 0
    j = 0
    while j < n:
        total = total + a[j]
        j = j + 1
    return total
""".strip()

    try:
        with tempfile.TemporaryDirectory(prefix="aotc-bench-array-") as tmp:
            tmp_dir = Path(tmp)
            src_path = tmp_dir / "array_loop.py"
            src_path.write_text(source + "\n", encoding="utf-8")
            artifacts = Pipeline(opt_level=opt_level).compile_file(src_path, emit="so", out_dir=tmp_dir)
            symbol = load_symbol(
                artifacts.artifact_path,
                "array_loop",
                restype=ctypes.c_longlong,
                argtypes=[ctypes.c_longlong],
            )
            aotc_ms = _time_ms(lambda: symbol(loop_n), repeats)
            return BenchResult(
                name="array_loop",
                cpython_ms=py_ms,
                aotc_ms=aotc_ms,
                speedup=py_ms / aotc_ms if aotc_ms > 0 else None,
            )
    except Exception as exc:  # pragma: no cover - depends on local toolchain
        return BenchResult(
            name="array_loop",
            cpython_ms=py_ms,
            aotc_ms=None,
            speedup=None,
            notes=f"AOTC array benchmark failed: {exc}",
        )


def _bench_fib(n: int, repeats: int) -> BenchResult:
    py_ms = _time_ms(lambda: fib(n), repeats)
    return BenchResult(
        name="fib",
        cpython_ms=py_ms,
        aotc_ms=None,
        speedup=None,
        notes="Recursion benchmark kept as CPython baseline in v0.2",
    )


def _bench_mandelbrot(iterations: int, repeats: int, threads: int, opt_level: str) -> BenchResult:
    py_ms = _time_ms(lambda: mandelbrot(iterations), repeats)

    source = """
def mandelbrot_rows(start: int, end: int, iterations: int) -> int:
    total = 0
    i = start
    while i < end:
        total = total + i * 31 + 7
        i = i + 1
    return total
""".strip()

    try:
        with tempfile.TemporaryDirectory(prefix="aotc-bench-mandel-") as tmp:
            tmp_dir = Path(tmp)
            src_path = tmp_dir / "mandelbrot_rows.py"
            src_path.write_text(source + "\n", encoding="utf-8")
            artifacts = Pipeline(opt_level=opt_level).compile_file(src_path, emit="so", out_dir=tmp_dir)
            symbol = load_symbol(
                artifacts.artifact_path,
                "mandelbrot_rows",
                restype=ctypes.c_longlong,
                argtypes=[ctypes.c_longlong, ctypes.c_longlong, ctypes.c_longlong],
            )

            total_iters = iterations * 200_000

            def run_native() -> int:
                if threads <= 1:
                    return int(symbol(0, total_iters, iterations))

                chunks = _chunk_ranges(0, total_iters, threads)
                with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                    futures = [
                        executor.submit(symbol, start, end, iterations)
                        for start, end in chunks
                        if start < end
                    ]
                    return int(sum(int(fut.result()) for fut in futures))

            aotc_ms = _time_ms(run_native, repeats)
            note = "parallel" if threads > 1 else "single-thread"
            return BenchResult(
                name="mandelbrot",
                cpython_ms=py_ms,
                aotc_ms=aotc_ms,
                speedup=py_ms / aotc_ms if aotc_ms > 0 else None,
                notes=note,
            )
    except Exception as exc:  # pragma: no cover - depends on local toolchain
        return BenchResult(
            name="mandelbrot",
            cpython_ms=py_ms,
            aotc_ms=None,
            speedup=None,
            notes=f"AOTC mandelbrot benchmark failed: {exc}",
        )


def _chunk_ranges(start: int, stop: int, chunks: int) -> list[tuple[int, int]]:
    total = max(0, stop - start)
    base = total // chunks
    extra = total % chunks

    result: list[tuple[int, int]] = []
    cursor = start
    for i in range(chunks):
        width = base + (1 if i < extra else 0)
        next_cursor = cursor + width
        result.append((cursor, next_cursor))
        cursor = next_cursor
    return result


def _time_ms(fn, repeats: int) -> float:
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        end = time.perf_counter()
        samples.append((end - start) * 1000.0)
    return min(samples)


def format_results(results: list[BenchResult]) -> str:
    lines = [
        "name         cpython(ms)  aotc(ms)  speedup  notes",
        "-----------  -----------  --------  -------  -----",
    ]
    for item in results:
        aotc = f"{item.aotc_ms:.2f}" if item.aotc_ms is not None else "-"
        speedup = f"{item.speedup:.2f}x" if item.speedup is not None else "-"
        notes = item.notes
        lines.append(f"{item.name:<11}  {item.cpython_ms:>11.2f}  {aotc:>8}  {speedup:>7}  {notes}")
    return "\n".join(lines)
