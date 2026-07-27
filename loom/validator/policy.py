"""Per-node policy invariants beyond what the JSON Schema enforces."""
from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, Any

from loom.ir.models import (
    AgentNode,
    CodeNode,
    HTTPNode,
    LLMNode,
    LoopNode,
    OutputNode,
    ParallelNode,
    RetrievalNode,
)
from loom.validator.errors import ValidationFailure
from loom.validator.refs import RefParseError, VarRef, parse_refs

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from loom.ir.models import AnyNode, IRDocument


def check_policy(ir: IRDocument, *, audit_max_retention_days: int = 365) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []
    nodes = list(_walk(ir.nodes))
    node_ids = {n.id for n in nodes}
    node_by_id = {n.id: n for n in nodes}

    default_timeout = ir.policy.default_timeout_s
    default_retry_max = (
        ir.policy.default_retry.max_attempts if ir.policy.default_retry else None
    )
    default_budget = ir.policy.agent_budget

    for n in nodes:
        loc = f"nodes[{n.id}]"
        # Timeout tightening only.
        node_to = getattr(n, "timeout_s", None)
        if default_timeout is not None and node_to is not None and node_to > default_timeout:
            failures.append(ValidationFailure(
                "policy",
                f"node timeout_s {node_to} exceeds workflow default_timeout_s {default_timeout}",
                location=loc,
            ))
        # Retry tightening only.
        node_retry = getattr(n, "retry", None)
        if (
            default_retry_max is not None
            and node_retry is not None
            and node_retry.max_attempts > default_retry_max
        ):
            failures.append(ValidationFailure(
                "policy",
                f"node retry.max_attempts {node_retry.max_attempts} exceeds default {default_retry_max}",
                location=loc,
            ))
        # http POST/PUT/PATCH/DELETE: idempotency_key required (schema also enforces; we re-check).
        if isinstance(n, HTTPNode) and n.method in {"POST", "PUT", "PATCH", "DELETE"} and not n.idempotency_key:
            failures.append(ValidationFailure(
                "policy", f"{n.method} without idempotency_key", location=loc,
            ))
        # code: best-practice idempotency_key when retry is enabled.
        if isinstance(n, CodeNode) and node_retry is not None and not n.idempotency_key:
            failures.append(ValidationFailure(
                "policy", "code with retry must declare idempotency_key", location=loc,
            ))
        # code: sandbox allowlist — reject anything the Validator can't vet statically.
        if isinstance(n, CodeNode):
            for reason in _check_code_sandbox(n):
                failures.append(ValidationFailure("policy", reason, location=loc))
        # agent: budget tightening, fallback edge existence, tools subset.
        if isinstance(n, AgentNode):
            if default_budget is not None:
                if n.budget.max_iterations > default_budget.max_iterations:
                    failures.append(ValidationFailure(
                        "policy", "agent max_iterations exceeds workflow default", location=loc,
                    ))
                if n.budget.max_tokens > default_budget.max_tokens:
                    failures.append(ValidationFailure(
                        "policy", "agent max_tokens exceeds workflow default", location=loc,
                    ))
                if n.budget.max_wall_clock_s > default_budget.max_wall_clock_s:
                    failures.append(ValidationFailure(
                        "policy", "agent max_wall_clock_s exceeds workflow default", location=loc,
                    ))
            if n.on_budget_exhausted == "fallback" and (
                not n.fallback_edge or n.fallback_edge not in node_ids
            ):
                failures.append(ValidationFailure(
                    "policy", f"fallback_edge {n.fallback_edge!r} does not point at an existing node",
                    location=loc,
                ))
            for tool in n.tools:
                if tool not in ir.registry_ref.tools:
                    failures.append(ValidationFailure(
                        "policy", f"agent tool {tool!r} not in registry_ref.tools", location=loc,
                    ))

    if ir.ir_version == "0.4":
        failures.extend(_check_v04_policy(ir, node_by_id, audit_max_retention_days))

    failures.extend(_check_trust_boundaries(ir))

    return failures


# ---------------------------------------------------------------------------
# Code sandbox: AST/import allowlist. Anything the Validator can't vet
# statically (an import outside the allowlist, a dangerous builtin) is
# rejected — "if it can't be sandboxed, reject the code node."
# ---------------------------------------------------------------------------

_PY_IMPORT_ALLOWLIST = {
    "json", "re", "math", "statistics", "decimal", "datetime", "itertools",
    "functools", "collections", "typing", "dataclasses", "string", "textwrap",
    "uuid", "enum",
}
_PY_DANGEROUS_CALLS = {"eval", "exec", "compile", "__import__", "open", "input"}
_PY_DANGEROUS_ATTR_ROOTS = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "importlib",
    "ctypes", "multiprocessing", "threading", "requests", "urllib", "http",
    "ftplib", "smtplib", "pickle", "marshal", "ssl",
}
# Object-introspection attribute names used by classic sandbox-escape chains
# (e.g. `().__class__.__bases__[0].__subclasses__()` reaches arbitrary
# builtins without importing anything or naming a blocked root). None of the
# import-allowlisted stdlib modules need these on a workflow code node, so
# any use is rejected regardless of what object the attribute is accessed on.
_PY_DANGEROUS_ATTR_NAMES = {
    "__class__", "__bases__", "__base__", "__subclasses__", "__mro__",
    "__globals__", "__builtins__", "__import__", "__loader__", "__spec__",
    "__code__", "__closure__", "__func__", "__self__", "__dict__",
    "__getattribute__", "__reduce__", "__reduce_ex__", "__init_subclass__",
}
_JS_DANGEROUS_PATTERNS = [
    re.compile(r"\beval\("),
    re.compile(r"\bnew\s+Function\("),
    re.compile(r"\brequire\(\s*['\"](?:child_process|fs|net|dgram|http|https|os|cluster)['\"]\s*\)"),
    re.compile(r"\bfetch\("),
    re.compile(r"\bXMLHttpRequest\b"),
    re.compile(r"\bWebSocket\("),
]


def _check_code_sandbox(node: CodeNode) -> list[str]:
    if node.language == "python":
        return _check_python_sandbox(node.source)
    return _check_js_sandbox(node.source)


def _check_python_sandbox(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"code does not parse as python: {e}"]

    visitor = _PythonSandboxVisitor()
    visitor.visit(tree)
    return visitor.reasons


class _PythonNameScope:
    def __init__(self, bindings: set[str], global_names: set[str] | None = None) -> None:
        self.bindings = bindings
        self.global_names = global_names or set()


class _PythonSandboxVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.reasons: list[str] = []
        self._scopes: list[_PythonNameScope] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root not in _PY_IMPORT_ALLOWLIST:
                self.reasons.append(
                    f"import {alias.name!r} is not in the sandbox allowlist"
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        root = (node.module or "").split(".")[0]
        if node.level or root not in _PY_IMPORT_ALLOWLIST:
            self.reasons.append(
                f"import from {node.module!r} is not in the sandbox allowlist"
            )

    def visit_Name(self, node: ast.Name) -> None:
        if (
            isinstance(node.ctx, ast.Load)
            and node.id in _PY_DANGEROUS_CALLS
            and not self._is_locally_bound(node.id)
        ):
            self.reasons.append(
                f"reference to {node.id!r} is forbidden in a sandboxed code node"
            )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in _PY_DANGEROUS_ATTR_NAMES:
            self.reasons.append(
                f"access to {node.attr!r} is forbidden in a sandboxed code node "
                "(object-introspection attributes can escape the import allowlist)"
            )
        root: ast.expr = node
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name) and root.id in _PY_DANGEROUS_ATTR_ROOTS:
            self.reasons.append(
                f"access to {root.id!r} is forbidden in a sandboxed code node"
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_definition(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function_definition(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._visit_argument_expressions(node.args)
        self._scopes.append(_function_scope(node))
        self.visit(node.body)
        self._scopes.pop()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node.generators, [node.elt])

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node.generators, [node.elt])

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node.generators, [node.key, node.value])

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node.generators, [node.elt])

    def _visit_function_definition(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        self._visit_argument_expressions(node.args)
        if node.returns is not None:
            self.visit(node.returns)

        self._scopes.append(_function_scope(node))
        for statement in node.body:
            self.visit(statement)
        self._scopes.pop()

    def _visit_argument_expressions(self, arguments: ast.arguments) -> None:
        all_arguments = [
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ]
        if arguments.vararg is not None:
            all_arguments.append(arguments.vararg)
        if arguments.kwarg is not None:
            all_arguments.append(arguments.kwarg)
        for argument in all_arguments:
            if argument.annotation is not None:
                self.visit(argument.annotation)
        for default in [*arguments.defaults, *arguments.kw_defaults]:
            if default is not None:
                self.visit(default)

    def _visit_comprehension(
        self,
        generators: list[ast.comprehension],
        result_nodes: list[ast.expr],
    ) -> None:
        # The first iterable is evaluated outside the comprehension's implicit scope.
        first, *remaining = generators
        self.visit(first.iter)

        bindings: set[str] = set()
        for generator in generators:
            bindings.update(_bound_target_names(generator.target))
        self._scopes.append(_PythonNameScope(bindings))
        self.visit(first.target)
        for condition in first.ifs:
            self.visit(condition)
        for generator in remaining:
            self.visit(generator.iter)
            self.visit(generator.target)
            for condition in generator.ifs:
                self.visit(condition)
        for result_node in result_nodes:
            self.visit(result_node)
        self._scopes.pop()

    def _is_locally_bound(self, name: str) -> bool:
        for scope in reversed(self._scopes):
            if name in scope.global_names:
                return False
            if name in scope.bindings:
                return True
        return False


def _function_scope(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
) -> _PythonNameScope:
    # Python decides function locals from the whole body before executing it.
    collector = _FunctionBindingCollector()
    if isinstance(node, ast.Lambda):
        collector.visit(node.body)
    else:
        for statement in node.body:
            collector.visit(statement)

    bindings = _argument_names(node.args) | collector.bindings
    bindings.difference_update(collector.global_names | collector.nonlocal_names)
    return _PythonNameScope(bindings, collector.global_names)


class _FunctionBindingCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.bindings: set[str] = set()
        self.global_names: set[str] = set()
        self.nonlocal_names: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bindings.add(node.id)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.bindings.add(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self.bindings.add(alias.asname or alias.name)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            self.bindings.add(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.bindings.add(node.name)
        self._visit_nested_function_expressions(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.bindings.add(node.name)
        self._visit_nested_function_expressions(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.visit(default)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node.generators, [node.elt])

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node.generators, [node.elt])

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node.generators, [node.key, node.value])

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node.generators, [node.elt])

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.bindings.add(node.name)
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_Global(self, node: ast.Global) -> None:
        self.global_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocal_names.update(node.names)

    def _visit_nested_function_expressions(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.visit(default)

    def _visit_comprehension(
        self,
        generators: list[ast.comprehension],
        result_nodes: list[ast.expr],
    ) -> None:
        # Comprehension targets do not leak into the containing function scope.
        for generator in generators:
            self.visit(generator.iter)
            for condition in generator.ifs:
                self.visit(condition)
        for result_node in result_nodes:
            self.visit(result_node)


def _argument_names(arguments: ast.arguments) -> set[str]:
    names = {
        argument.arg
        for argument in [
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ]
    }
    if arguments.vararg is not None:
        names.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        names.add(arguments.kwarg.arg)
    return names


def _bound_target_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Starred):
        return _bound_target_names(target.value)
    if isinstance(target, (ast.Tuple, ast.List)):
        return {
            name
            for element in target.elts
            for name in _bound_target_names(element)
        }
    return set()


def _check_js_sandbox(source: str) -> list[str]:
    return [
        f"js source matches forbidden pattern {p.pattern!r}"
        for p in _JS_DANGEROUS_PATTERNS if p.search(source)
    ]


# ---------------------------------------------------------------------------
# Trust-boundary delimiters: prompts must not splice untrusted content
# (raw user input, retrieved KB text, external HTTP responses) directly
# into instructions without an explicit <untrusted>...</untrusted> wrapper.
# ---------------------------------------------------------------------------

_UNTRUSTED_BLOCK_RE = re.compile(r"<untrusted>.*?</untrusted>", re.S)


def _untrusted_producer_ids(ir: IRDocument) -> set[str]:
    ids = {"input"}
    for n in _walk(ir.nodes):
        if isinstance(n, (RetrievalNode, HTTPNode)):
            ids.add(n.id)
    return ids


def _check_trust_boundaries(ir: IRDocument) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []
    untrusted = _untrusted_producer_ids(ir)

    for n in _walk(ir.nodes):
        fields: list[tuple[str, str]] = []
        if isinstance(n, LLMNode):
            fields.append(("prompt", n.prompt))
            if n.system_prompt:
                fields.append(("system_prompt", n.system_prompt))
        elif isinstance(n, AgentNode) and n.system_prompt:
            fields.append(("system_prompt", n.system_prompt))

        for field_label, text in fields:
            spans = [(m.start(), m.end()) for m in _UNTRUSTED_BLOCK_RE.finditer(text)]
            for pid in untrusted:
                ref_re = re.compile(rf"\$\{{{re.escape(pid)}(?:\.[a-zA-Z_][a-zA-Z0-9_]*|\[\d+\])*\}}")
                for m in ref_re.finditer(text):
                    if not any(s <= m.start() and m.end() <= e for s, e in spans):
                        failures.append(ValidationFailure(
                            "policy",
                            f"prompt references untrusted producer {pid!r} outside a <untrusted> delimiter",
                            location=f"nodes[{n.id}].{field_label}",
                        ))
    return failures


def _check_v04_policy(
    ir: IRDocument,
    node_by_id: dict[str, AnyNode],
    audit_max_retention_days: int,
) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []

    guardrails = ir.policy.guardrails
    if guardrails is not None:
        for idx, pattern in enumerate(guardrails.custom_patterns):
            try:
                re.compile(pattern)
            except re.error as e:
                failures.append(ValidationFailure(
                    "policy",
                    f"guardrails.custom_patterns[{idx}] is not a valid regex: {e}",
                    location=f"policy.guardrails.custom_patterns[{idx}]",
                ))

    escalation = ir.policy.escalation
    if escalation is not None:
        handoff = node_by_id.get(escalation.handoff_node)
        if not isinstance(handoff, OutputNode):
            failures.append(ValidationFailure(
                "policy",
                f"escalation.handoff_node {escalation.handoff_node!r} must reference an output node",
                location="policy.escalation.handoff_node",
            ))
        failures.extend(_check_confidence_ref(escalation.confidence_from, node_by_id))

    audit = ir.policy.audit
    if audit is not None and audit.retention_days > audit_max_retention_days:
        failures.append(ValidationFailure(
            "policy",
            f"audit.retention_days {audit.retention_days} exceeds org cap {audit_max_retention_days}",
            location="policy.audit.retention_days",
        ))

    return failures


def _check_confidence_ref(
    confidence_from: str,
    node_by_id: dict[str, AnyNode],
) -> list[ValidationFailure]:
    try:
        refs = parse_refs(confidence_from)
    except RefParseError as e:
        return [ValidationFailure("policy", str(e), location="policy.escalation.confidence_from")]

    if len(refs) != 1 or confidence_from.strip() != _format_ref(refs[0]):
        return [ValidationFailure(
            "policy",
            "escalation.confidence_from must be a single VarRef",
            location="policy.escalation.confidence_from",
        )]

    ref = refs[0]
    producer = node_by_id.get(ref.node_id)
    if not isinstance(producer, LLMNode):
        return [ValidationFailure(
            "policy",
            f"escalation.confidence_from must reference an llm node output, got {ref.node_id!r}",
            location="policy.escalation.confidence_from",
        )]
    if not ref.path or ref.path[0].startswith("["):
        return [ValidationFailure(
            "policy",
            "escalation.confidence_from must reference an llm output_schema field",
            location="policy.escalation.confidence_from",
        )]

    field = ref.path[0]
    field_type = _json_schema_field_type(producer.output_schema, field)
    if field_type not in {"number", "integer"}:
        return [ValidationFailure(
            "policy",
            f"escalation.confidence_from field {field!r} must be numeric in llm.output_schema",
            location="policy.escalation.confidence_from",
        )]
    return []


def _format_ref(ref: VarRef) -> str:
    path = "".join(segment if segment.startswith("[") else f".{segment}" for segment in ref.path)
    return f"${{{ref.node_id}{path}}}"


def _json_schema_field_type(output_schema: dict[str, Any] | None, field: str) -> str | None:
    if not isinstance(output_schema, dict):
        return None
    props = output_schema.get("properties")
    if not isinstance(props, dict):
        return None
    field_schema = props.get(field)
    if not isinstance(field_schema, dict):
        return None
    raw_type = field_schema.get("type")
    if isinstance(raw_type, str):
        return raw_type
    if isinstance(raw_type, list):
        for candidate in ("number", "integer"):
            if candidate in raw_type:
                return candidate
    return None


def _walk(nodes: Iterable[AnyNode]) -> Iterator[AnyNode]:
    for n in nodes:
        yield n
        if isinstance(n, LoopNode):
            yield from _walk(n.body)
        elif isinstance(n, ParallelNode):
            for branch in n.branches.values():
                yield from _walk(branch)
