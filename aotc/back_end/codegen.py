"""LLVM code generation for AOTC IR."""

from __future__ import annotations

import platform
from dataclasses import dataclass

from aotc.errors import CodegenError
from aotc.ir.cfg import FunctionIR, ModuleIR
from aotc.ir.node import (
    Alloca,
    BinOp,
    Branch,
    Call,
    Cast,
    Const,
    GEP,
    GetField,
    Jump,
    Load,
    Phi,
    PtrCast,
    Return,
    Store,
    StructDef,
    Value,
)

try:
    import llvmlite.binding as llvm_binding  # type: ignore

    _HAVE_LLVM_LITE = True
except Exception:  # pragma: no cover - optional dependency
    llvm_binding = None
    _HAVE_LLVM_LITE = False


@dataclass(slots=True)
class CodegenResult:
    llvm_ir: str
    used_llvmlite: bool


class LLVMCodeGenerator:
    def __init__(self, opt_level: str = "O2", enable_mem2reg: bool = True) -> None:
        self._type_map = {
            "int": "i64",
            "float": "double",
            "bool": "i1",
            "void": "void",
        }
        self._opt_level = self._normalize_opt_level(opt_level)
        self._enable_mem2reg = enable_mem2reg
        self._temp_counter = 0

    def emit_module(self, module: ModuleIR) -> CodegenResult:
        self._temp_counter = 0
        needs_memset = self._module_uses_memset(module)

        parts = [f'target triple = "{self._target_triple()}"', ""]

        if module.structs:
            for struct_name in sorted(module.structs):
                parts.append(self._emit_struct_def(module.structs[struct_name]))
            parts.append("")

        if needs_memset:
            parts.append("declare void @llvm.memset.p0.i64(ptr nocapture writeonly, i8, i64, i1 immarg)")

        for extern in module.externs:
            ret_ty = self._llvm_type(extern.return_type)
            args = ", ".join(self._llvm_type(arg) for arg in extern.arg_types)
            parts.append(f"declare dso_local {ret_ty} @{extern.name}({args})")

        if needs_memset or module.externs:
            parts.append("")

        for fn in module.functions:
            parts.append(self.emit_function(fn))
            parts.append("")

        llvm_ir = "\n".join(parts).strip() + "\n"

        if _HAVE_LLVM_LITE:
            llvm_ir = self._normalize_with_llvmlite(llvm_ir)
            return CodegenResult(llvm_ir=llvm_ir, used_llvmlite=True)

        return CodegenResult(llvm_ir=llvm_ir, used_llvmlite=False)

    def emit_function(self, fn_ir: FunctionIR) -> str:
        ret_ty = self._llvm_type(fn_ir.return_type)
        args = ", ".join(f"{self._llvm_type(arg.typ)} %{arg.name}" for arg in fn_ir.args)
        lines = [f"define dso_local {ret_ty} @{fn_ir.name}({args}) {{"]

        for block in fn_ir.ordered_blocks():
            lines.append(f"{block.label}:")
            for node in block.nodes:
                for emitted in self._emit_instruction(node):
                    lines.append(f"  {emitted}")
            if block.terminator is None:
                raise CodegenError(f"Block '{block.label}' is missing terminator")
            lines.append(f"  {self._emit_terminator(block.terminator)}")

        lines.append("}")
        return "\n".join(lines)

    def _emit_instruction(self, node: object) -> list[str]:
        if isinstance(node, Const):
            ty = self._llvm_type(node.result.typ)
            literal = self._literal(node.result, node.value)
            if node.result.typ == "float":
                return [f"%{node.result.name} = fadd {ty} 0.000000e+00, {literal}"]
            if node.result.typ == "bool":
                return [f"%{node.result.name} = or {ty} false, {literal}"]
            return [f"%{node.result.name} = add {ty} 0, {literal}"]

        if isinstance(node, BinOp):
            if node.op == "id":
                ty = self._llvm_type(node.result.typ)
                if node.result.typ == "float":
                    return [f"%{node.result.name} = fadd {ty} %{node.lhs.name}, 0.000000e+00"]
                if node.result.typ == "bool":
                    return [f"%{node.result.name} = or {ty} %{node.lhs.name}, false"]
                return [f"%{node.result.name} = add {ty} %{node.lhs.name}, 0"]

            if node.op in {"+", "-", "*", "/"}:
                return [self._emit_arith(node)]

            if node.op in {"lt", "le", "gt", "ge", "eq", "ne"}:
                return [self._emit_compare(node)]

            raise CodegenError(f"Unsupported BinOp opcode '{node.op}'")

        if isinstance(node, Phi):
            ty = self._llvm_type(node.result.typ)
            incoming_items = ", ".join(
                f"[ %{value.name}, %{label} ]" for label, value in node.incomings.items()
            )
            return [f"%{node.result.name} = phi {ty} {incoming_items}"]

        if isinstance(node, Alloca):
            elem_ty = self._llvm_type(node.elem_type)
            align = self._alignment(node.elem_type)
            lines: list[str] = []

            if node.count is None:
                lines.append(f"%{node.result.name} = alloca {elem_ty}, align {align}")
            else:
                lines.append(
                    f"%{node.result.name} = alloca {elem_ty}, i64 %{node.count.name}, align {align}"
                )

            if node.zero_init:
                if node.count is None:
                    count_bytes = self._byte_size(node.elem_type)
                    lines.append(
                        f"call void @llvm.memset.p0.i64(ptr %{node.result.name}, i8 0, "
                        f"i64 {count_bytes}, i1 false)"
                    )
                else:
                    byte_size = self._byte_size(node.elem_type)
                    if byte_size == 1:
                        byte_count = f"%{node.count.name}"
                    else:
                        tmp = self._next_temp("bytes")
                        lines.append(f"%{tmp} = mul i64 %{node.count.name}, {byte_size}")
                        byte_count = f"%{tmp}"
                    lines.append(
                        f"call void @llvm.memset.p0.i64(ptr %{node.result.name}, i8 0, "
                        f"i64 {byte_count}, i1 false)"
                    )

            return lines

        if isinstance(node, Cast):
            if node.target_type == "float" and node.value.typ == "int":
                return [f"%{node.result.name} = sitofp i64 %{node.value.name} to double"]
            if node.target_type == "float" and node.value.typ == "bool":
                tmp = self._next_temp("b2i")
                return [
                    f"%{tmp} = zext i1 %{node.value.name} to i64",
                    f"%{node.result.name} = sitofp i64 %{tmp} to double",
                ]
            if node.target_type == "int" and node.value.typ == "bool":
                return [f"%{node.result.name} = zext i1 %{node.value.name} to i64"]
            if node.target_type == "int" and node.value.typ == "float":
                return [f"%{node.result.name} = fptosi double %{node.value.name} to i64"]
            raise CodegenError(
                f"Unsupported cast from {node.value.typ} to {node.target_type}"
            )

        if isinstance(node, GEP):
            elem_ty = self._llvm_type(node.elem_type)
            return [
                f"%{node.result.name} = getelementptr inbounds {elem_ty}, "
                f"ptr %{node.base_ptr.name}, i64 %{node.index.name}"
            ]

        if isinstance(node, GetField):
            struct_ty = f"%struct.{node.struct_name}"
            return [
                f"%{node.result.name} = getelementptr inbounds {struct_ty}, "
                f"ptr %{node.base_ptr.name}, i32 0, i32 {node.field_index}"
            ]

        if isinstance(node, PtrCast):
            src_is_ptr = node.value.typ.startswith("ptr_")
            dst_is_ptr = node.target_type.startswith("ptr_")
            if src_is_ptr and dst_is_ptr:
                return [f"%{node.result.name} = getelementptr i8, ptr %{node.value.name}, i64 0"]
            if src_is_ptr and node.target_type == "int":
                return [f"%{node.result.name} = ptrtoint ptr %{node.value.name} to i64"]
            if node.value.typ == "int" and dst_is_ptr:
                return [f"%{node.result.name} = inttoptr i64 %{node.value.name} to ptr"]
            raise CodegenError(
                f"Unsupported pointer cast from {node.value.typ} to {node.target_type}"
            )

        if isinstance(node, Load):
            elem_ty = self._llvm_type(node.elem_type)
            align = self._alignment(node.elem_type)
            return [f"%{node.result.name} = load {elem_ty}, ptr %{node.ptr.name}, align {align}"]

        if isinstance(node, Store):
            elem_ty = self._llvm_type(node.elem_type)
            align = self._alignment(node.elem_type)
            return [f"store {elem_ty} %{node.value.name}, ptr %{node.ptr.name}, align {align}"]

        if isinstance(node, Call):
            ret_ty = self._llvm_type(node.return_type)
            arg_text = ", ".join(f"{self._llvm_type(arg.typ)} %{arg.name}" for arg in node.args)
            if node.result is None:
                return [f"call {ret_ty} @{node.func_name}({arg_text})"]
            return [f"%{node.result.name} = call {ret_ty} @{node.func_name}({arg_text})"]

        raise CodegenError(f"Unsupported instruction type '{type(node).__name__}'")

    def _emit_arith(self, node: BinOp) -> str:
        ty = self._llvm_type(node.result.typ)
        lhs = f"%{node.lhs.name}"
        rhs = f"%{node.rhs.name}"

        if node.result.typ == "float":
            op_map = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv"}
        else:
            op_map = {"+": "add", "-": "sub", "*": "mul", "/": "sdiv"}

        inst = op_map.get(node.op)
        if inst is None:
            raise CodegenError(f"Arithmetic opcode '{node.op}' not mapped")

        return f"%{node.result.name} = {inst} {ty} {lhs}, {rhs}"

    def _emit_compare(self, node: BinOp) -> str:
        op_map = {
            "lt": "slt",
            "le": "sle",
            "gt": "sgt",
            "ge": "sge",
            "eq": "eq",
            "ne": "ne",
        }
        pred = op_map[node.op]

        lhs_ty = self._llvm_type(node.lhs.typ)
        lhs = f"%{node.lhs.name}"
        rhs = f"%{node.rhs.name}"

        if node.lhs.typ == "float" or node.rhs.typ == "float":
            float_pred_map = {
                "lt": "olt",
                "le": "ole",
                "gt": "ogt",
                "ge": "oge",
                "eq": "oeq",
                "ne": "one",
            }
            pred = float_pred_map[node.op]
            return f"%{node.result.name} = fcmp {pred} {lhs_ty} {lhs}, {rhs}"

        return f"%{node.result.name} = icmp {pred} {lhs_ty} {lhs}, {rhs}"

    def _emit_terminator(self, node: object) -> str:
        if isinstance(node, Branch):
            return f"br i1 %{node.cond.name}, label %{node.true_label}, label %{node.false_label}"
        if isinstance(node, Jump):
            return f"br label %{node.target}"
        if isinstance(node, Return):
            if node.value is None:
                return "ret void"
            return f"ret {self._llvm_type(node.value.typ)} %{node.value.name}"
        raise CodegenError(f"Unsupported terminator type '{type(node).__name__}'")

    def _literal(self, value: Value, raw: int | float | bool) -> str:
        if value.typ == "bool":
            return "true" if bool(raw) else "false"
        if value.typ == "float":
            return f"{float(raw):.6e}"
        return str(int(raw))

    def _llvm_type(self, typ: str) -> str:
        if typ.startswith("struct_"):
            return f"%struct.{typ[len('struct_') :]}"
        if typ.startswith("ptr_"):
            return "ptr"
        mapped = self._type_map.get(typ)
        if mapped is None:
            raise CodegenError(f"Unsupported type '{typ}'")
        return mapped

    def _emit_struct_def(self, struct_def: StructDef) -> str:
        fields = ", ".join(self._llvm_type(field.typ) for field in struct_def.fields)
        if struct_def.packed:
            return f"%struct.{struct_def.name} = type <{{ {fields} }}>"
        return f"%struct.{struct_def.name} = type {{ {fields} }}"

    @staticmethod
    def _alignment(typ: str) -> int:
        if typ in {"int", "float"}:
            return 8
        if typ == "bool":
            return 1
        return 8

    @staticmethod
    def _byte_size(typ: str) -> int:
        if typ in {"int", "float"}:
            return 8
        if typ == "bool":
            return 1
        return 8

    def _module_uses_memset(self, module: ModuleIR) -> bool:
        for fn in module.functions:
            for block in fn.ordered_blocks():
                for node in block.nodes:
                    if isinstance(node, Alloca) and node.zero_init:
                        return True
        return False

    def _next_temp(self, prefix: str) -> str:
        self._temp_counter += 1
        return f"cg_{prefix}_{self._temp_counter}"

    def _target_triple(self) -> str:
        machine = platform.machine().lower()
        if machine in {"x86_64", "amd64"}:
            arch = "x86_64"
        elif machine in {"aarch64", "arm64"}:
            arch = "aarch64"
        else:
            arch = "x86_64"
        system = platform.system().lower()
        if system == "darwin":
            return f"{arch}-apple-darwin"
        if system == "windows":
            return f"{arch}-pc-windows-msvc"
        return f"{arch}-unknown-linux-gnu"

    def _normalize_with_llvmlite(self, llvm_ir: str) -> str:
        assert llvm_binding is not None
        llvm_binding.initialize()
        llvm_binding.initialize_native_target()
        llvm_binding.initialize_native_asmprinter()

        module = llvm_binding.parse_assembly(llvm_ir)
        module.verify()

        if self._enable_mem2reg or self._opt_level > 0:
            pass_manager_builder = llvm_binding.PassManagerBuilder()
            pass_manager_builder.opt_level = self._opt_level
            pass_manager_builder.loop_vectorize = self._opt_level >= 2
            pass_manager_builder.slp_vectorize = self._opt_level >= 2

            module_pass_manager = llvm_binding.ModulePassManager()
            pass_manager_builder.populate(module_pass_manager)
            module_pass_manager.run(module)

        return str(module)

    @staticmethod
    def _normalize_opt_level(opt_level: str) -> int:
        normalized = opt_level.upper()
        mapping = {"O0": 0, "O2": 2, "O3": 3}
        if normalized not in mapping:
            raise CodegenError(f"Unsupported opt level '{opt_level}'")
        return mapping[normalized]
