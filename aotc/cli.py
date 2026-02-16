"""Command-line interface for AOTC."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from aotc.back_end.optimizer import parse_passes
from aotc.benchmarks.suite import format_results, run_suite
from aotc.errors import AOTCError
from aotc.pipeline import Pipeline


def cmd_build(
    source_file: str,
    emit: str,
    output: str | None,
    out_dir: str | None,
    opt_level: str,
    passes_spec: str | None,
) -> int:
    source = Path(source_file)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {source}")

    pipeline = Pipeline(opt_level=opt_level, passes=parse_passes(passes_spec))
    artifacts = pipeline.compile_file(
        source_path=source,
        emit=emit,
        output=Path(output) if output else None,
        out_dir=Path(out_dir) if out_dir else None,
    )

    print(f"[aotc] source: {artifacts.source_path}")
    print(f"[aotc] llvm ir: {artifacts.llvm_ir_path}")
    if artifacts.artifact_path is not None:
        print(f"[aotc] artifact: {artifacts.artifact_path}")
    print(f"[aotc] llvmlite: {'enabled' if artifacts.used_llvmlite else 'fallback-text'}")
    print(f"[aotc] opt: {artifacts.opt_level} | passes: {','.join(artifacts.passes)}")
    if artifacts.link_libs:
        print(f"[aotc] link libs: {','.join(artifacts.link_libs)}")
    return 0


def cmd_clean(out_dir: str | None) -> int:
    target = Path(out_dir) if out_dir else Path(".aotc_build")
    if target.exists():
        shutil.rmtree(target)
        print(f"[aotc] clean: removed {target}")
    else:
        print(f"[aotc] clean: nothing to remove at {target}")
    return 0


def cmd_bench(loop_count: int, repeats: int, threads: int, opt_level: str) -> int:
    results = run_suite(loop_n=loop_count, repeats=repeats, threads=threads, opt_level=opt_level)
    print(format_results(results))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aotc", description="AOTC compiler tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build Python source file")
    build.add_argument("file", help="Input Python file")
    build.add_argument(
        "--emit",
        choices=("so", "asm", "ll"),
        default="so",
        help="Output artifact type",
    )
    build.add_argument("--opt", choices=("O0", "O2", "O3"), default="O2", help="Optimization level")
    build.add_argument("--passes", default="cf,dce", help="Comma-separated pass list")
    build.add_argument("-o", "--output", help="Explicit output path")
    build.add_argument("--out-dir", help="Build directory (default: <src>/.aotc_build)")

    clean = subparsers.add_parser("clean", help="Clean build artifacts")
    clean.add_argument("--out-dir", help="Build directory to clean (default: .aotc_build)")

    bench = subparsers.add_parser("bench", help="Run benchmark suite")
    bench.add_argument("--loop-count", type=int, default=10_000_000, help="Loop benchmark iteration")
    bench.add_argument("--repeats", type=int, default=3, help="Number of timing repetitions")
    bench.add_argument("--threads", type=int, default=1, help="Thread count for parallel benchmarks")
    bench.add_argument("--opt", choices=("O0", "O2", "O3"), default="O2", help="Optimization level")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "build":
            return cmd_build(args.file, args.emit, args.output, args.out_dir, args.opt, args.passes)
        if args.command == "clean":
            return cmd_clean(args.out_dir)
        if args.command == "bench":
            return cmd_bench(args.loop_count, args.repeats, args.threads, args.opt)
    except AOTCError as exc:
        print(f"[aotc] error: {exc}")
        return 1

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
