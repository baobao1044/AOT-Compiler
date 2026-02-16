"""Control-flow graph and module IR types."""

from __future__ import annotations

from dataclasses import dataclass, field

from aotc.ir.node import ExternDecl, Instruction, StructDef, Terminator, TypeName, Value


@dataclass(slots=True)
class BasicBlock:
    label: str
    nodes: list[Instruction] = field(default_factory=list)
    terminator: Terminator | None = None

    def add_node(self, node: Instruction) -> None:
        self.nodes.append(node)

    def add_phi_front(self, node: Instruction) -> None:
        self.nodes.insert(0, node)

    def set_terminator(self, node: Terminator) -> None:
        self.terminator = node


@dataclass(slots=True)
class FunctionSignature:
    name: str
    arg_types: list[TypeName]
    return_type: TypeName
    is_extern: bool = False
    lib: str | None = None
    parallel: bool = False


@dataclass(slots=True)
class FunctionIR:
    name: str
    args: list[Value]
    return_type: TypeName
    blocks: dict[str, BasicBlock] = field(default_factory=dict)
    block_order: list[str] = field(default_factory=list)
    locals: dict[str, Value] = field(default_factory=dict)
    parallel: bool = False

    def new_block(self, label: str) -> BasicBlock:
        block = BasicBlock(label=label)
        self.blocks[label] = block
        self.block_order.append(label)
        return block

    def ordered_blocks(self) -> list[BasicBlock]:
        return [self.blocks[label] for label in self.block_order]


@dataclass(slots=True)
class ModuleIR:
    functions: list[FunctionIR] = field(default_factory=list)
    externs: list[ExternDecl] = field(default_factory=list)
    structs: dict[str, StructDef] = field(default_factory=dict)
    signatures: dict[str, FunctionSignature] = field(default_factory=dict)

    def add_signature(self, signature: FunctionSignature) -> None:
        self.signatures[signature.name] = signature

    def add_function(self, function: FunctionIR) -> None:
        self.functions.append(function)

    def add_extern(self, extern_decl: ExternDecl) -> None:
        self.externs.append(extern_decl)

    def add_struct(self, struct_def: StructDef) -> None:
        self.structs[struct_def.name] = struct_def
