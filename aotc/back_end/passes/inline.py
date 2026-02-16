"""Simple inlining pass placeholder for v0.2."""

from __future__ import annotations

from aotc.ir.cfg import ModuleIR


class InlinePass:
    """Optional inline pass.

    v0.2 keeps this conservative: the pass currently acts as a hook point so
    users can include/exclude it via CLI without changing pipeline behavior.
    """

    name = "inline"

    def run_module(self, module: ModuleIR) -> ModuleIR:
        return module
