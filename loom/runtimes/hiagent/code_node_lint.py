"""Pure AST checks for the HiAgent Python Code-node runtime contract."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Literal

CodeNodeLintSeverity = Literal["fatal", "warning"]


@dataclass(frozen=True)
class CodeNodeLintFinding:
    """One contract violation found in final emitted Python source."""

    severity: CodeNodeLintSeverity
    code: str
    message: str
    line: int | None = None


def lint_hiagent_python(source: str) -> list[CodeNodeLintFinding]:
    """Analyze final emitted HiAgent Python Code-node source without I/O."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        detail = error.msg
        if error.lineno is not None:
            detail += f" (line {error.lineno})"
        return [
            CodeNodeLintFinding(
                severity="fatal",
                code="code_node.handler.syntax_error",
                message=f"Invalid Python syntax: {detail}",
                line=error.lineno,
            )
        ]

    handlers = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "handler"
    ]
    if not handlers:
        return [
            CodeNodeLintFinding(
                severity="fatal",
                code="code_node.handler.missing",
                message='Missing HiAgent entry function def handler(input=""):',
            )
        ]
    if len(handlers) > 1:
        return [
            CodeNodeLintFinding(
                severity="fatal",
                code="code_node.handler.multiple",
                message=(
                    "HiAgent Python Code nodes must define exactly one top-level handler "
                    f"function; found {len(handlers)}."
                ),
            )
        ]

    handler = handlers[0]
    args = handler.args
    positional = [*args.posonlyargs, *args.args]
    signature_problem = _fatal_signature_problem(handler)
    if signature_problem is not None:
        return [signature_problem]

    findings: list[CodeNodeLintFinding] = []
    if len(positional) == 1 and not _has_canonical_signature(handler):
        findings.append(CodeNodeLintFinding(
            severity="warning",
            code="code_node.handler.signature_style",
            message='Use the canonical HiAgent entry signature def handler(input=""):.',
            line=handler.lineno,
        ))

    parents = _parent_map(handler)
    unpack_nodes: set[ast.AST] = set()
    unpack = _first_unpack_statement(handler)
    if unpack is None:
        findings.append(CodeNodeLintFinding(
            severity="warning",
            code="code_node.handler.unpack_missing",
            message=(
                "The first executable statement must be "
                "params = input if isinstance(input, dict) else {}."
            ),
            line=handler.lineno,
        ))
    else:
        unpack_nodes.update(ast.walk(unpack))

    return_params_line: int | None = None
    direct_index_line: int | None = None
    get_without_default_line: int | None = None
    bypass_direct_get_line: int | None = None
    for node in ast.walk(handler):
        if (
            return_params_line is None
            and isinstance(node, ast.Return)
            and isinstance(node.value, ast.Name)
            and node.value.id == "params"
        ):
            return_params_line = node.lineno

        if (
            direct_index_line is None
            and isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id in {"input", "params"}
        ):
            direct_index_line = node.lineno

        if get_without_default_line is None and _is_params_get_call(node):
            assert isinstance(node, ast.Call)
            if len(node.args) != 2 or node.keywords:
                get_without_default_line = node.lineno

        if (
            bypass_direct_get_line is None
            and isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in {"input", "params"}
            and node not in unpack_nodes
            and not _is_params_get_receiver(node, parents)
        ):
            bypass_direct_get_line = node.lineno

    if get_without_default_line is not None:
        findings.append(CodeNodeLintFinding(
            severity="warning",
            code="code_node.handler.get_without_default",
            message=(
                'Every params.get(...) call must provide an explicit default, for example '
                'params.get("query", "").'
            ),
            line=get_without_default_line,
        ))
    if direct_index_line is not None:
        findings.append(CodeNodeLintFinding(
            severity="warning",
            code="code_node.handler.direct_index",
            message='Do not index input/params directly; use params.get("name", default).',
            line=direct_index_line,
        ))
    if return_params_line is not None:
        findings.append(CodeNodeLintFinding(
            severity="warning",
            code="code_node.handler.return_params",
            message=(
                "Do not return the merged params object wholesale; construct declared "
                "outputs explicitly."
            ),
            line=return_params_line,
        ))
    if bypass_direct_get_line is not None:
        findings.append(CodeNodeLintFinding(
            severity="warning",
            code="code_node.handler.bypass_direct_get",
            message=(
                'Read business inputs only through params.get("name", default); direct '
                "input/params reads bypass the HiAgent contract."
            ),
            line=bypass_direct_get_line,
        ))
    return findings


def _fatal_signature_problem(handler: ast.FunctionDef) -> CodeNodeLintFinding | None:
    args = handler.args
    positional = [*args.posonlyargs, *args.args]
    if not positional and args.vararg is None:
        return CodeNodeLintFinding(
            severity="fatal",
            code="code_node.handler.signature",
            message=(
                "Invalid HiAgent handler signature (zero positional parameters). "
                "HiAgent always passes one merged dict argument, so def handler(): "
                "raises TypeError at runtime. Use def handler(input=\"\"):."
            ),
            line=handler.lineno,
        )
    problems: list[str] = []
    if len(positional) > 1:
        problems.append(f"{len(positional)} positional parameters")
    if args.vararg is not None:
        problems.append("*args")
    if args.kwarg is not None:
        problems.append("**kwargs")
    if args.kwonlyargs:
        problems.append("keyword-only parameters")
    if not problems:
        return None
    return CodeNodeLintFinding(
        severity="fatal",
        code="code_node.handler.signature",
        message=(
            "Invalid HiAgent handler signature ("
            + ", ".join(problems)
            + "). HiAgent passes every configured node input as one merged dict only to "
            "the first parameter; later parameters keep their defaults and silently read "
            "empty. Use def handler(input=\"\"):."
        ),
        line=handler.lineno,
    )


def _has_canonical_signature(handler: ast.FunctionDef) -> bool:
    args = handler.args
    positional = [*args.posonlyargs, *args.args]
    return (
        len(positional) == 1
        and positional[0].arg == "input"
        and len(args.defaults) == 1
        and isinstance(args.defaults[0], ast.Constant)
        and args.defaults[0].value == ""
    )


def _parent_map(root: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(root):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def _first_unpack_statement(handler: ast.FunctionDef) -> ast.Assign | None:
    body = list(handler.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    if not body or not isinstance(body[0], ast.Assign):
        return None
    node = body[0]
    if len(node.targets) != 1:
        return None
    target = node.targets[0]
    value = node.value
    if not (
        isinstance(target, ast.Name)
        and target.id == "params"
        and isinstance(value, ast.IfExp)
        and isinstance(value.test, ast.Call)
        and isinstance(value.test.func, ast.Name)
        and value.test.func.id == "isinstance"
        and len(value.test.args) == 2
        and isinstance(value.test.args[0], ast.Name)
        and value.test.args[0].id == "input"
        and isinstance(value.test.args[1], ast.Name)
        and value.test.args[1].id == "dict"
        and isinstance(value.body, ast.Name)
        and value.body.id == "input"
        and isinstance(value.orelse, ast.Dict)
        and not value.orelse.keys
    ):
        return None
    return node


def _is_params_get_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "params"
        and node.func.attr == "get"
    )


def _is_params_get_receiver(
    node: ast.Name,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    parent = parents.get(node)
    if not (
        node.id == "params"
        and isinstance(parent, ast.Attribute)
        and parent.value is node
        and parent.attr == "get"
    ):
        return False
    call = parents.get(parent)
    return isinstance(call, ast.Call) and call.func is parent
