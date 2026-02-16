"""Optimization pass manager."""

from __future__ import annotations

from collections.abc import Iterable

from aotc.back_end.passes.constant_folding import ConstantFoldingPass
from aotc.back_end.passes.dead_code import DeadCodeEliminationPass
from aotc.back_end.passes.inline import InlinePass
from aotc.ir.cfg import ModuleIR

try:
    import llvmlite.binding as llvm_binding  # type: ignore

    _HAVE_LLVM_LITE = True
except Exception:  # pragma: no cover - optional dependency
    llvm_binding = None
    _HAVE_LLVM_LITE = False


class PassManager:
    def __init__(self) -> None:
        self._passes: list[object] = []

    def add_pass(self, optimization_pass: object) -> None:
        self._passes.append(optimization_pass)

    def extend(self, optimization_passes: Iterable[object]) -> None:
        self._passes.extend(optimization_passes)

    def run_module(self, module: ModuleIR) -> ModuleIR:
        for optimization_pass in self._passes:
            if hasattr(optimization_pass, "run_module"):
                optimization_pass.run_module(module)
                continue

            if hasattr(optimization_pass, "run"):
                for fn in module.functions:
                    optimization_pass.run(fn)

        return module


def default_pass_manager(pass_names: list[str] | None = None) -> PassManager:
    manager = PassManager()
    selected = pass_names or ["cf", "dce"]

    available = {
        "cf": ConstantFoldingPass,
        "dce": DeadCodeEliminationPass,
        "inline": InlinePass,
    }

    for name in selected:
        key = name.strip().lower()
        pass_cls = available.get(key)
        if pass_cls is None:
            raise ValueError(f"Unknown pass name '{name}'")
        manager.add_pass(pass_cls())

    return manager


def parse_passes(passes_spec: str | None) -> list[str] | None:
    if passes_spec is None or passes_spec.strip() == "":
        return None
    return [part.strip() for part in passes_spec.split(",") if part.strip()]


def apply_llvm_mem2reg(llvm_ir: str, opt_level: str) -> tuple[str, bool]:
    """Apply LLVM mem2reg/optimization pipeline when llvmlite is available."""
    if not _HAVE_LLVM_LITE:
        return llvm_ir, False

    assert llvm_binding is not None
    llvm_binding.initialize()
    llvm_binding.initialize_native_target()
    llvm_binding.initialize_native_asmprinter()

    module = llvm_binding.parse_assembly(llvm_ir)
    module.verify()

    mapping = {"O0": 0, "O2": 2, "O3": 3}
    normalized = opt_level.upper()
    level = mapping.get(normalized)
    if level is None:
        raise ValueError(f"Unsupported opt level '{opt_level}'")

    pass_manager_builder = llvm_binding.PassManagerBuilder()
    pass_manager_builder.opt_level = level

    module_pass_manager = llvm_binding.ModulePassManager()
    pass_manager_builder.populate(module_pass_manager)
    module_pass_manager.run(module)

    return str(module), True
