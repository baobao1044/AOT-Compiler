"""AOTC compile pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aotc.back_end.builder import compile_llvm_ir, shared_lib_suffix
from aotc.back_end.codegen import LLVMCodeGenerator
from aotc.back_end.optimizer import default_pass_manager
from aotc.errors import AOTCError
from aotc.front_end.parser import FrontEndParser


@dataclass(slots=True)
class BuildArtifacts:
    source_path: Path
    llvm_ir_path: Path
    artifact_path: Path | None
    used_llvmlite: bool
    opt_level: str
    passes: list[str]
    link_libs: list[str]


class Pipeline:
    def __init__(
        self,
        opt_level: str = "O2",
        passes: list[str] | None = None,
        enable_mem2reg: bool = True,
    ) -> None:
        self.opt_level = opt_level.upper()
        self.passes = passes or ["cf", "dce"]

        self.front_end = FrontEndParser()
        try:
            self.optimizer = default_pass_manager(self.passes)
        except ValueError as exc:
            raise AOTCError(str(exc)) from exc
        self.codegen = LLVMCodeGenerator(opt_level=self.opt_level, enable_mem2reg=enable_mem2reg)

    def compile_file(
        self,
        source_path: Path,
        emit: str = "so",
        output: Path | None = None,
        out_dir: Path | None = None,
    ) -> BuildArtifacts:
        src = source_path.read_text(encoding="utf-8")
        module = self.front_end.lower_module(src, filename=str(source_path))
        module = self.optimizer.run_module(module)
        codegen_result = self.codegen.emit_module(module)

        build_dir = out_dir or (source_path.parent / ".aotc_build")
        build_dir.mkdir(parents=True, exist_ok=True)

        ll_path = build_dir / f"{source_path.stem}.ll"
        ll_path.write_text(codegen_result.llvm_ir, encoding="utf-8")

        link_libs = sorted({extern.lib for extern in module.externs if extern.lib})

        if emit == "ll":
            artifact_path: Path | None = ll_path
        elif emit == "asm":
            artifact = output or (build_dir / f"{source_path.stem}.s")
            artifact_path = compile_llvm_ir(
                ll_path=ll_path,
                output_path=artifact,
                emit="asm",
                opt_level=self.opt_level,
            )
        else:
            artifact = output or (build_dir / f"{source_path.stem}{shared_lib_suffix()}")
            artifact_path = compile_llvm_ir(
                ll_path=ll_path,
                output_path=artifact,
                emit="so",
                opt_level=self.opt_level,
                link_libs=link_libs,
            )

        return BuildArtifacts(
            source_path=source_path,
            llvm_ir_path=ll_path,
            artifact_path=artifact_path,
            used_llvmlite=codegen_result.used_llvmlite,
            opt_level=self.opt_level,
            passes=list(self.passes),
            link_libs=link_libs,
        )
