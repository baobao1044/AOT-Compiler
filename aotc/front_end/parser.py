"""AST to IR lowering for the v0.2 MVP subset."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass

from aotc.errors import FrontEndError
from aotc.front_end.typer import annotation_to_typename, merge_types
from aotc.ir.cfg import BasicBlock, FunctionIR, FunctionSignature, ModuleIR
from aotc.ir.node import (
    Alloca,
    BinOp,
    Branch,
    Call,
    Cast,
    Const,
    ExternDecl,
    GEP,
    Jump,
    Load,
    Phi,
    Return,
    ScalarType,
    Store,
    StructDef,
    StructField,
    TypeName,
    Value,
    is_scalar_type,
    pointee_type,
    ptr_type,
)


@dataclass(slots=True)
class ArrayBinding:
    base_ptr: Value
    elem_type: ScalarType
    length: Value | None
    length_const: int | None = None


class FrontEndParser:
    """Lower Python AST into AOTC IR (v0.2 subset)."""

    def __init__(self) -> None:
        self._tmp_counter = 0
        self._block_counter = 0
        self._name_versions: dict[str, int] = {}

        self._arrays: dict[str, ArrayBinding] = {}
        self._signatures: dict[str, FunctionSignature] = {}
        self._arg_names: set[str] = set()
        self._struct_names: set[str] = set()

    def lower_module(self, src: str, filename: str = "<memory>") -> ModuleIR:
        tree = ast.parse(src, filename=filename)
        module = ModuleIR()

        class_defs = [stmt for stmt in tree.body if isinstance(stmt, ast.ClassDef)]
        for class_def in class_defs:
            struct_def = self._extract_struct_def(class_def)
            if struct_def is None:
                continue
            if struct_def.name in module.structs:
                raise FrontEndError(f"Duplicate struct definition '{struct_def.name}'")
            module.add_struct(struct_def)

        self._struct_names = set(module.structs)

        function_defs = [stmt for stmt in tree.body if isinstance(stmt, ast.FunctionDef)]
        if not function_defs and not module.structs:
            raise FrontEndError("No function definitions found in source module")

        for fn in function_defs:
            signature = self._extract_signature(fn)
            if signature.name in module.signatures:
                raise FrontEndError(f"Duplicate function definition '{signature.name}'")
            module.add_signature(signature)

        self._signatures = module.signatures

        for fn in function_defs:
            signature = module.signatures[fn.name]
            if signature.is_extern:
                module.add_extern(
                    ExternDecl(
                        name=signature.name,
                        lib=signature.lib or "",
                        arg_types=signature.arg_types,
                        return_type=signature.return_type,
                    )
                )
                continue

            module.add_function(self._lower_function(fn, signature))

        if not module.functions and not module.externs:
            raise FrontEndError("No compilable functions found in source module")

        return module

    def _extract_signature(self, fn: ast.FunctionDef) -> FunctionSignature:
        try:
            arg_types = [self._annotation_to_signature_type(arg.annotation) for arg in fn.args.args]
            return_type = self._annotation_to_signature_type(fn.returns)
        except TypeError as exc:
            raise FrontEndError(str(exc)) from exc

        extern_lib = self._extract_extern_lib(fn.decorator_list)
        parallel = self._extract_parallel_flag(fn.decorator_list)
        if extern_lib is not None:
            self._validate_extern_body(fn)

        return FunctionSignature(
            name=fn.name,
            arg_types=arg_types,
            return_type=return_type,
            is_extern=extern_lib is not None,
            lib=extern_lib,
            parallel=parallel,
        )

    def _extract_extern_lib(self, decorators: list[ast.expr]) -> str | None:
        found: str | None = None
        for deco in decorators:
            if (
                isinstance(deco, ast.Call)
                and isinstance(deco.func, ast.Name)
                and deco.func.id == "extern"
            ):
                if len(deco.args) != 1:
                    raise FrontEndError("@extern requires exactly one library name argument")
                arg = deco.args[0]
                if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                    raise FrontEndError("@extern library argument must be a string literal")
                found = arg.value
        return found

    def _extract_parallel_flag(self, decorators: list[ast.expr]) -> bool:
        for deco in decorators:
            if isinstance(deco, ast.Name) and deco.id == "parallel":
                return True

            if (
                isinstance(deco, ast.Call)
                and isinstance(deco.func, ast.Name)
                and deco.func.id in {"native", "parallel"}
            ):
                for keyword in deco.keywords:
                    if keyword.arg == "parallel":
                        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, bool):
                            return keyword.value.value
                        raise FrontEndError("@native(parallel=...) expects a boolean literal")
                if deco.func.id == "parallel":
                    return True

        return False

    def _lower_function(self, fn: ast.FunctionDef, signature: FunctionSignature) -> FunctionIR:
        self._tmp_counter = 0
        self._block_counter = 0
        self._name_versions = {}
        self._arrays = {}
        self._arg_names = set()

        args: list[Value] = []
        env: dict[str, Value] = {}
        for ast_arg, arg_type in zip(fn.args.args, signature.arg_types):
            value = self._new_named_value(ast_arg.arg, arg_type)
            args.append(value)
            env[ast_arg.arg] = value
            self._arg_names.add(ast_arg.arg)

            arg_elem_type = pointee_type(arg_type)
            if arg_elem_type is not None:
                if not is_scalar_type(arg_elem_type):
                    continue
                if arg_elem_type == "void":
                    raise FrontEndError(
                        f"Unsupported pointer argument type for '{ast_arg.arg}': {arg_type}"
                    )
                self._arrays[ast_arg.arg] = ArrayBinding(
                    base_ptr=value,
                    elem_type=arg_elem_type,
                    length=None,
                )

        ir_fn = FunctionIR(
            name=fn.name,
            args=args,
            return_type=signature.return_type,
            parallel=signature.parallel,
        )
        entry = ir_fn.new_block("entry")
        current = entry

        body = [s for s in fn.body if not self._is_docstring_stmt(s)]
        if not body:
            raise FrontEndError(f"Function '{fn.name}' has empty body")

        for stmt in body:
            current, env = self._lower_stmt(ir_fn, current, env, stmt)

        if current.terminator is None:
            if signature.return_type == "void":
                current.set_terminator(Return(value=None))
            else:
                raise FrontEndError(f"Function '{fn.name}' must end with return")

        return ir_fn

    def _lower_stmt(
        self,
        fn: FunctionIR,
        block: BasicBlock,
        env: dict[str, Value],
        stmt: ast.stmt,
    ) -> tuple[BasicBlock, dict[str, Value]]:
        if isinstance(stmt, ast.Assign):
            return self._lower_assign(fn, block, env, stmt)

        if isinstance(stmt, ast.AugAssign):
            return self._lower_augassign(fn, block, env, stmt)

        if isinstance(stmt, ast.Return):
            value = self._lower_expr(fn, block, env, stmt.value) if stmt.value else None
            block.set_terminator(Return(value=value))
            return block, env

        if isinstance(stmt, ast.If):
            return self._lower_if(fn, block, env, stmt)

        if isinstance(stmt, ast.While):
            return self._lower_while(fn, block, env, stmt)

        if isinstance(stmt, ast.For):
            return self._lower_for_range(fn, block, env, stmt)

        if isinstance(stmt, ast.Expr):
            if isinstance(stmt.value, ast.Call):
                self._lower_expr(fn, block, env, stmt.value, expect_value=False)
                return block, env
            if isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis:
                return block, env
            raise FrontEndError(f"Unsupported expression statement: {type(stmt.value).__name__}")

        if isinstance(stmt, ast.Pass):
            return block, env

        raise FrontEndError(f"Unsupported statement: {type(stmt).__name__}")

    def _lower_assign(
        self,
        fn: FunctionIR,
        block: BasicBlock,
        env: dict[str, Value],
        stmt: ast.Assign,
    ) -> tuple[BasicBlock, dict[str, Value]]:
        if len(stmt.targets) != 1:
            raise FrontEndError("Only single-target assignment is supported")

        target = stmt.targets[0]
        if isinstance(target, ast.Name):
            array_repeat = self._extract_static_array_repeat(stmt.value)
            if array_repeat is not None:
                return self._lower_array_alloc_assign(fn, block, env, target.id, array_repeat)

            if target.id in self._arrays:
                raise FrontEndError(
                    f"Variable '{target.id}' is already an array. Re-assignment is not supported"
                )

            value = self._lower_expr(fn, block, env, stmt.value)
            updated = dict(env)
            renamed = self._new_named_value(target.id, value.typ)
            if value.name != renamed.name:
                block.add_node(BinOp(op="id", lhs=value, rhs=value, result=renamed))
            updated[target.id] = renamed
            return block, updated

        if isinstance(target, ast.Subscript):
            return self._lower_subscript_store(fn, block, env, target, stmt.value)

        raise FrontEndError("Unsupported assignment target")

    def _lower_array_alloc_assign(
        self,
        fn: FunctionIR,
        block: BasicBlock,
        env: dict[str, Value],
        target_name: str,
        array_repeat: tuple[int | float | bool, ast.expr, ScalarType],
    ) -> tuple[BasicBlock, dict[str, Value]]:
        init_value, count_expr, elem_type = array_repeat

        if not self._is_allowed_array_length(count_expr, env):
            raise FrontEndError(
                "Array length must be an integer constant or an integer function parameter"
            )

        count_value = self._lower_expr(fn, block, env, count_expr)
        if count_value.typ != "int":
            raise FrontEndError("Array length must have type int")

        if init_value not in (0, 0.0, False):
            raise FrontEndError("v0.2 currently supports zero-initialized arrays only")

        ptr = self._new_named_value(target_name, ptr_type(elem_type))
        block.add_node(Alloca(result=ptr, elem_type=elem_type, count=count_value, zero_init=True))

        self._arrays[target_name] = ArrayBinding(
            base_ptr=ptr,
            elem_type=elem_type,
            length=count_value,
            length_const=self._int_literal(count_expr),
        )
        fn.locals[target_name] = ptr

        updated = dict(env)
        updated.pop(target_name, None)
        return block, updated

    def _lower_subscript_store(
        self,
        fn: FunctionIR,
        block: BasicBlock,
        env: dict[str, Value],
        target: ast.Subscript,
        rhs_expr: ast.expr,
    ) -> tuple[BasicBlock, dict[str, Value]]:
        array_name, index_expr = self._extract_subscript_parts(target)
        array_binding = self._arrays.get(array_name)
        if array_binding is None:
            raise FrontEndError(f"Unknown array '{array_name}'")

        self._validate_static_index_bounds(array_name, array_binding, index_expr)

        index = self._lower_expr(fn, block, env, index_expr)
        if index.typ != "int":
            raise FrontEndError("Array index must have type int")

        rhs = self._lower_expr(fn, block, env, rhs_expr)
        if rhs.typ != array_binding.elem_type:
            raise FrontEndError(
                f"Array '{array_name}' stores {array_binding.elem_type}, got {rhs.typ}"
            )

        ptr = self._new_temp_value(ptr_type(array_binding.elem_type))
        block.add_node(
            GEP(
                base_ptr=array_binding.base_ptr,
                index=index,
                result=ptr,
                elem_type=array_binding.elem_type,
            )
        )
        block.add_node(Store(ptr=ptr, value=rhs, elem_type=array_binding.elem_type))
        return block, env

    def _lower_augassign(
        self,
        fn: FunctionIR,
        block: BasicBlock,
        env: dict[str, Value],
        stmt: ast.AugAssign,
    ) -> tuple[BasicBlock, dict[str, Value]]:
        if not isinstance(stmt.target, ast.Name):
            raise FrontEndError("Only scalar name targets are supported in augmented assignment")
        name = stmt.target.id
        if name not in env:
            raise FrontEndError(f"Unknown variable '{name}' in augmented assignment")
        lhs = env[name]
        rhs = self._lower_expr(fn, block, env, stmt.value)
        op = self._map_binop(stmt.op)
        try:
            result_type = merge_types(lhs.typ, rhs.typ)
        except TypeError as exc:
            raise FrontEndError(str(exc)) from exc
        result = self._new_named_value(name, result_type)
        block.add_node(BinOp(op=op, lhs=lhs, rhs=rhs, result=result))
        updated = dict(env)
        updated[name] = result
        return block, updated

    def _lower_if(
        self,
        fn: FunctionIR,
        block: BasicBlock,
        env: dict[str, Value],
        stmt: ast.If,
    ) -> tuple[BasicBlock, dict[str, Value]]:
        cond = self._lower_expr(fn, block, env, stmt.test)
        if cond.typ != "bool":
            raise FrontEndError("If condition must lower to bool")

        then_label = self._new_block_label("if_then")
        else_label = self._new_block_label("if_else")
        join_label = self._new_block_label("if_join")

        then_block = fn.new_block(then_label)
        else_block = fn.new_block(else_label)
        join_block = fn.new_block(join_label)

        block.set_terminator(Branch(cond=cond, true_label=then_label, false_label=else_label))

        then_env = deepcopy(env)
        current_then = then_block
        for body_stmt in stmt.body:
            current_then, then_env = self._lower_stmt(fn, current_then, then_env, body_stmt)
        if current_then.terminator is None:
            current_then.set_terminator(Jump(target=join_label))

        else_env = deepcopy(env)
        current_else = else_block
        for else_stmt in stmt.orelse:
            current_else, else_env = self._lower_stmt(fn, current_else, else_env, else_stmt)
        if current_else.terminator is None:
            current_else.set_terminator(Jump(target=join_label))

        merged_env = self._merge_env_with_phi(join_block, env, then_env, else_env, then_label, else_label)
        return join_block, merged_env

    def _lower_while(
        self,
        fn: FunctionIR,
        block: BasicBlock,
        env: dict[str, Value],
        stmt: ast.While,
    ) -> tuple[BasicBlock, dict[str, Value]]:
        cond_label = self._new_block_label("while_cond")
        body_label = self._new_block_label("while_body")
        exit_label = self._new_block_label("while_exit")

        cond_block = fn.new_block(cond_label)
        body_block = fn.new_block(body_label)
        exit_block = fn.new_block(exit_label)

        block.set_terminator(Jump(target=cond_label))

        cond_env = dict(env)
        loop_phis: dict[str, Phi] = {}
        for name, value in env.items():
            phi_result = self._new_named_value(name, value.typ)
            phi = Phi(result=phi_result, incomings={block.label: value, body_label: value})
            cond_block.add_node(phi)
            cond_env[name] = phi_result
            loop_phis[name] = phi

        cond_value = self._lower_expr(fn, cond_block, cond_env, stmt.test)
        if cond_value.typ != "bool":
            raise FrontEndError("While condition must lower to bool")
        cond_block.set_terminator(Branch(cond=cond_value, true_label=body_label, false_label=exit_label))

        body_env = dict(cond_env)
        current_body = body_block
        for body_stmt in stmt.body:
            current_body, body_env = self._lower_stmt(fn, current_body, body_env, body_stmt)
        if current_body.terminator is None:
            current_body.set_terminator(Jump(target=cond_label))

        for name, phi in loop_phis.items():
            phi.incomings[body_label] = body_env.get(name, cond_env[name])

        exit_env = dict(cond_env)
        return exit_block, exit_env

    def _lower_for_range(
        self,
        fn: FunctionIR,
        block: BasicBlock,
        env: dict[str, Value],
        stmt: ast.For,
    ) -> tuple[BasicBlock, dict[str, Value]]:
        if not isinstance(stmt.target, ast.Name):
            raise FrontEndError("For-loop target must be a variable name")
        if not isinstance(stmt.iter, ast.Call) or not isinstance(stmt.iter.func, ast.Name):
            raise FrontEndError("Only range() is supported in for loops")
        if stmt.iter.func.id != "range":
            raise FrontEndError("Only range() is supported in for loops")

        args = stmt.iter.args
        if len(args) == 1:
            start_expr = ast.Constant(value=0)
            stop_expr = args[0]
            step_expr: ast.expr = ast.Constant(value=1)
        elif len(args) == 2:
            start_expr, stop_expr = args
            step_expr = ast.Constant(value=1)
        elif len(args) == 3:
            start_expr, stop_expr, step_expr = args
        else:
            raise FrontEndError("range() supports 1 to 3 arguments")

        assign_stmt = ast.Assign(targets=[ast.Name(id=stmt.target.id, ctx=ast.Store())], value=start_expr)
        current, loop_env = self._lower_assign(fn, block, env, assign_stmt)

        op: ast.cmpop = ast.Lt()
        if isinstance(step_expr, ast.Constant) and isinstance(step_expr.value, int) and step_expr.value < 0:
            op = ast.Gt()

        while_stmt = ast.While(
            test=ast.Compare(
                left=ast.Name(id=stmt.target.id, ctx=ast.Load()),
                ops=[op],
                comparators=[stop_expr],
            ),
            body=[
                *stmt.body,
                ast.Assign(
                    targets=[ast.Name(id=stmt.target.id, ctx=ast.Store())],
                    value=ast.BinOp(
                        left=ast.Name(id=stmt.target.id, ctx=ast.Load()),
                        op=ast.Add(),
                        right=step_expr,
                    ),
                ),
            ],
            orelse=[],
        )
        return self._lower_while(fn, current, loop_env, while_stmt)

    def _lower_expr(
        self,
        fn: FunctionIR,
        block: BasicBlock,
        env: dict[str, Value],
        expr: ast.expr | None,
        expect_value: bool = True,
    ) -> Value:
        if expr is None:
            raise FrontEndError("Expected expression, got None")

        if isinstance(expr, ast.Constant):
            return self._emit_const(block, expr.value)

        if isinstance(expr, ast.Name):
            if expr.id in env:
                return env[expr.id]
            if expr.id in self._arrays:
                raise FrontEndError(f"Array '{expr.id}' must be indexed before use")
            raise FrontEndError(f"Unknown variable '{expr.id}'")

        if isinstance(expr, ast.Subscript):
            array_name, index_expr = self._extract_subscript_parts(expr)
            array_binding = self._arrays.get(array_name)
            if array_binding is None:
                raise FrontEndError(f"Unknown array '{array_name}'")

            self._validate_static_index_bounds(array_name, array_binding, index_expr)

            index = self._lower_expr(fn, block, env, index_expr)
            if index.typ != "int":
                raise FrontEndError("Array index must have type int")

            ptr = self._new_temp_value(ptr_type(array_binding.elem_type))
            block.add_node(
                GEP(
                    base_ptr=array_binding.base_ptr,
                    index=index,
                    result=ptr,
                    elem_type=array_binding.elem_type,
                )
            )
            out = self._new_temp_value(array_binding.elem_type)
            block.add_node(Load(ptr=ptr, result=out, elem_type=array_binding.elem_type))
            return out

        if isinstance(expr, ast.BinOp):
            lhs = self._lower_expr(fn, block, env, expr.left)
            rhs = self._lower_expr(fn, block, env, expr.right)
            if pointee_type(lhs.typ) is not None or pointee_type(rhs.typ) is not None:
                raise FrontEndError("Pointer arithmetic is not supported in v0.3 MVP")
            op = self._map_binop(expr.op)
            try:
                result_typ: TypeName = "float" if op == "/" else merge_types(lhs.typ, rhs.typ)
            except TypeError as exc:
                raise FrontEndError(str(exc)) from exc
            if result_typ == "float":
                lhs = self._coerce_type(block, lhs, "float")
                rhs = self._coerce_type(block, rhs, "float")
            result = self._new_temp_value(result_typ)
            block.add_node(BinOp(op=op, lhs=lhs, rhs=rhs, result=result))
            return result

        if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.USub):
            operand = self._lower_expr(fn, block, env, expr.operand)
            zero = self._emit_const(block, 0.0 if operand.typ == "float" else 0)
            result = self._new_temp_value(operand.typ)
            block.add_node(BinOp(op="-", lhs=zero, rhs=operand, result=result))
            return result

        if isinstance(expr, ast.Compare):
            if len(expr.ops) != 1 or len(expr.comparators) != 1:
                raise FrontEndError("Only single comparisons are supported")
            lhs = self._lower_expr(fn, block, env, expr.left)
            rhs = self._lower_expr(fn, block, env, expr.comparators[0])
            if pointee_type(lhs.typ) is not None or pointee_type(rhs.typ) is not None:
                raise FrontEndError("Pointer comparisons are not supported in v0.3 MVP")
            if lhs.typ != rhs.typ:
                if "float" in {lhs.typ, rhs.typ}:
                    lhs = self._coerce_type(block, lhs, "float")
                    rhs = self._coerce_type(block, rhs, "float")
                else:
                    raise FrontEndError(
                        f"Compare operands must have matching types, got {lhs.typ} and {rhs.typ}"
                    )
            op = self._map_cmpop(expr.ops[0])
            result = self._new_temp_value("bool")
            block.add_node(BinOp(op=op, lhs=lhs, rhs=rhs, result=result))
            return result

        if isinstance(expr, ast.Call):
            if not isinstance(expr.func, ast.Name):
                raise FrontEndError("Only direct function calls are supported")
            func_name = expr.func.id

            signature = self._signatures.get(func_name)
            if signature is None:
                raise FrontEndError(f"Unknown function call target '{func_name}'")

            if len(expr.args) != len(signature.arg_types):
                raise FrontEndError(
                    f"Function '{func_name}' expects {len(signature.arg_types)} arguments, "
                    f"got {len(expr.args)}"
                )

            lowered_args: list[Value] = []
            for arg_expr, expected_type in zip(expr.args, signature.arg_types):
                lowered = self._lower_expr(fn, block, env, arg_expr)
                if lowered.typ != expected_type:
                    raise FrontEndError(
                        f"Call '{func_name}': expected arg type {expected_type}, got {lowered.typ}"
                    )
                lowered_args.append(lowered)

            if signature.return_type == "void":
                block.add_node(
                    Call(
                        func_name=func_name,
                        args=lowered_args,
                        return_type=signature.return_type,
                        result=None,
                    )
                )
                if expect_value:
                    raise FrontEndError(f"Function '{func_name}' returns void and cannot be used in value context")
                return self._emit_const(block, 0)

            result = self._new_temp_value(signature.return_type)
            block.add_node(
                Call(
                    func_name=func_name,
                    args=lowered_args,
                    return_type=signature.return_type,
                    result=result,
                )
            )
            return result

        raise FrontEndError(f"Unsupported expression: {type(expr).__name__}")

    def _emit_const(self, block: BasicBlock, raw_value: object) -> Value:
        if isinstance(raw_value, bool):
            typ: TypeName = "bool"
            value = raw_value
        elif isinstance(raw_value, int):
            typ = "int"
            value = raw_value
        elif isinstance(raw_value, float):
            typ = "float"
            value = raw_value
        else:
            raise FrontEndError(f"Unsupported constant type: {type(raw_value).__name__}")

        result = self._new_temp_value(typ)
        block.add_node(Const(result=result, value=value))
        return result

    def _merge_env_with_phi(
        self,
        join_block: BasicBlock,
        base_env: dict[str, Value],
        then_env: dict[str, Value],
        else_env: dict[str, Value],
        then_label: str,
        else_label: str,
    ) -> dict[str, Value]:
        merged: dict[str, Value] = {}
        all_names = set(base_env) | set(then_env) | set(else_env)

        for name in sorted(all_names):
            base = base_env.get(name)
            left = then_env.get(name, base)
            right = else_env.get(name, base)
            if left is None and right is None:
                continue
            if left is None:
                merged[name] = right
                continue
            if right is None:
                merged[name] = left
                continue

            if left.name == right.name:
                merged[name] = left
                continue

            if left.typ != right.typ:
                raise FrontEndError(f"Cannot merge variable '{name}' with types {left.typ} and {right.typ}")

            phi_result = self._new_named_value(name, left.typ)
            join_block.add_node(Phi(result=phi_result, incomings={then_label: left, else_label: right}))
            merged[name] = phi_result

        return merged

    def _extract_static_array_repeat(
        self,
        value: ast.expr,
    ) -> tuple[int | float | bool, ast.expr, ScalarType] | None:
        if not isinstance(value, ast.BinOp) or not isinstance(value.op, ast.Mult):
            return None

        list_expr: ast.List | None = None
        count_expr: ast.expr | None = None

        if isinstance(value.left, ast.List):
            list_expr = value.left
            count_expr = value.right
        elif isinstance(value.right, ast.List):
            list_expr = value.right
            count_expr = value.left

        if list_expr is None or count_expr is None:
            return None

        if len(list_expr.elts) != 1:
            raise FrontEndError("Only single-element static array repeats are supported")

        elt = list_expr.elts[0]
        if not isinstance(elt, ast.Constant):
            raise FrontEndError("Static array initializer element must be constant")

        raw = elt.value
        if isinstance(raw, bool):
            elem_type: ScalarType = "bool"
        elif isinstance(raw, int):
            elem_type = "int"
        elif isinstance(raw, float):
            elem_type = "float"
        else:
            raise FrontEndError(f"Unsupported array element constant type: {type(raw).__name__}")

        return raw, count_expr, elem_type

    def _extract_struct_def(self, class_def: ast.ClassDef) -> StructDef | None:
        if not self._has_struct_decorator(class_def.decorator_list):
            return None

        fields: list[StructField] = []
        for stmt in class_def.body:
            if self._is_docstring_stmt(stmt) or isinstance(stmt, ast.Pass):
                continue

            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                field_type = annotation_to_typename(stmt.annotation)
                if field_type not in {"int", "float", "bool"}:
                    raise FrontEndError(
                        f"Struct '{class_def.name}' field '{stmt.target.id}' has unsupported type '{field_type}'"
                    )
                fields.append(StructField(name=stmt.target.id, typ=field_type))
                continue

            raise FrontEndError(
                f"Struct '{class_def.name}' only supports annotated scalar fields in v0.3"
            )

        if not fields:
            raise FrontEndError(f"Struct '{class_def.name}' must define at least one field")

        offsets, size, alignment = self._compute_struct_layout(fields)
        return StructDef(
            name=class_def.name,
            fields=fields,
            field_offsets=offsets,
            size=size,
            alignment=alignment,
        )

    @staticmethod
    def _has_struct_decorator(decorators: list[ast.expr]) -> bool:
        names = {FrontEndParser._decorator_name(deco) for deco in decorators}
        return "dataclass" in names or "native_struct" in names

    @staticmethod
    def _decorator_name(decorator: ast.expr) -> str:
        node = decorator
        if isinstance(node, ast.Call):
            node = node.func
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    def _compute_struct_layout(self, fields: list[StructField]) -> tuple[dict[str, int], int, int]:
        offsets: dict[str, int] = {}
        cursor = 0
        max_align = 1

        for field in fields:
            field_size, field_align = self._scalar_layout(field.typ)
            cursor = self._align_to(cursor, field_align)
            offsets[field.name] = cursor
            cursor += field_size
            if field_align > max_align:
                max_align = field_align

        total_size = self._align_to(cursor, max_align)
        return offsets, total_size, max_align

    @staticmethod
    def _scalar_layout(typ: TypeName) -> tuple[int, int]:
        if typ == "bool":
            return 1, 1
        if typ in {"int", "float"}:
            return 8, 8
        raise FrontEndError(f"Unsupported struct field type '{typ}'")

    @staticmethod
    def _align_to(value: int, alignment: int) -> int:
        return ((value + alignment - 1) // alignment) * alignment

    def _annotation_to_signature_type(self, node: ast.expr | None) -> TypeName:
        if isinstance(node, ast.Name) and node.id in self._struct_names:
            return ptr_type(f"struct_{node.id}")
        return annotation_to_typename(node)

    def _validate_static_index_bounds(
        self,
        array_name: str,
        array_binding: ArrayBinding,
        index_expr: ast.expr,
    ) -> None:
        if array_binding.length_const is None:
            return
        index = self._int_literal(index_expr)
        if index is None:
            return
        if index < 0 or index >= array_binding.length_const:
            raise FrontEndError(
                f"Static out-of-bounds access on '{array_name}': index {index}, "
                f"length {array_binding.length_const}"
            )

    @staticmethod
    def _int_literal(node: ast.expr) -> int | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return int(node.value)
        if (
            isinstance(node, ast.UnaryOp)
            and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, int)
        ):
            return -int(node.operand.value)
        return None

    def _is_allowed_array_length(self, expr: ast.expr, env: dict[str, Value]) -> bool:
        if isinstance(expr, ast.Constant) and isinstance(expr.value, int):
            return expr.value >= 0

        if isinstance(expr, ast.Name) and expr.id in self._arg_names:
            value = env.get(expr.id)
            return value is not None and value.typ == "int"

        return False

    @staticmethod
    def _extract_subscript_parts(expr: ast.Subscript) -> tuple[str, ast.expr]:
        if not isinstance(expr.value, ast.Name):
            raise FrontEndError("Array base must be a variable name")

        index_expr = expr.slice
        if isinstance(index_expr, ast.Slice):
            raise FrontEndError("Array slicing is not supported")

        return expr.value.id, index_expr

    def _new_temp_value(self, typ: TypeName) -> Value:
        self._tmp_counter += 1
        return Value(name=f"t{self._tmp_counter}", typ=typ)

    def _coerce_type(self, block: BasicBlock, value: Value, target_type: ScalarType) -> Value:
        if value.typ == target_type:
            return value

        if target_type == "float" and value.typ in {"int", "bool"}:
            out = self._new_temp_value("float")
            block.add_node(Cast(value=value, target_type="float", result=out))
            return out

        if target_type == "int" and value.typ == "bool":
            out = self._new_temp_value("int")
            block.add_node(Cast(value=value, target_type="int", result=out))
            return out

        raise FrontEndError(f"Cannot coerce {value.typ} to {target_type}")

    def _new_named_value(self, base: str, typ: TypeName) -> Value:
        version = self._name_versions.get(base, 0)
        self._name_versions[base] = version + 1
        return Value(name=f"{base}.{version}", typ=typ)

    def _new_block_label(self, prefix: str) -> str:
        self._block_counter += 1
        return f"{prefix}_{self._block_counter}"

    @staticmethod
    def _map_binop(op: ast.operator) -> str:
        if isinstance(op, ast.Add):
            return "+"
        if isinstance(op, ast.Sub):
            return "-"
        if isinstance(op, ast.Mult):
            return "*"
        if isinstance(op, ast.Div):
            return "/"
        raise FrontEndError(f"Unsupported binary operator: {type(op).__name__}")

    @staticmethod
    def _map_cmpop(op: ast.cmpop) -> str:
        if isinstance(op, ast.Lt):
            return "lt"
        if isinstance(op, ast.LtE):
            return "le"
        if isinstance(op, ast.Gt):
            return "gt"
        if isinstance(op, ast.GtE):
            return "ge"
        if isinstance(op, ast.Eq):
            return "eq"
        if isinstance(op, ast.NotEq):
            return "ne"
        raise FrontEndError(f"Unsupported compare operator: {type(op).__name__}")

    @staticmethod
    def _is_docstring_stmt(stmt: ast.stmt) -> bool:
        return (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        )

    def _validate_extern_body(self, fn: ast.FunctionDef) -> None:
        body = [stmt for stmt in fn.body if not self._is_docstring_stmt(stmt)]
        if len(body) != 1:
            raise FrontEndError(f"Extern function '{fn.name}' must only contain ellipsis or pass")

        only = body[0]
        if isinstance(only, ast.Pass):
            return
        if isinstance(only, ast.Expr) and isinstance(only.value, ast.Constant) and only.value.value is Ellipsis:
            return

        raise FrontEndError(f"Extern function '{fn.name}' must only contain ellipsis or pass")
