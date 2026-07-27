# Review: `AlataChan/integrate-deep-dive-fixes`

Date: 2026-07-27
Review mode: read-only, with an uncommitted throwaway merge of current `main` and the target branch

## Verdict

**DO NOT MERGE**

The branch contains worthwhile authorization, concurrency, validation, and compiler hardening, but the prospective merged result is not shippable:

1. The branch's Python sandbox check conflicts directly with main's mandatory HiAgent Code-node contract. A canonical `def handler(input="")` implementation is rejected by the validator because the sandbox forbids every `ast.Name` named `input`.
2. The sandbox escape fixed by `8d8deec` is only narrowed. Dynamic attribute lookup through `getattr` bypasses the new attribute-name checks, reaches `object.__subclasses__()`, loads the built-in `os` module, and passes validation.
3. The capability fail-closed layer and Code-node lint do not double-raise, but they produce path-dependent error precedence. The adapter path reports the first unsupported capability; direct CLI/compiler paths bypass that gate and report the Code-node lint error instead.
4. The merged tree fails the Python test suite, Python lint, mypy, and the web production build.

### Scores

| Dimension | Score | Reason |
|---|---:|---|
| Correctness | 4/10 | Most tests pass, but a deterministic Python regression, a failing web build, path-dependent compile behavior, and the validator/compiler Code-node contradiction remain. |
| Simplicity | 5/10 | The centralized capability matrix is a good direction, but compile policy is split across validator, adapter, direct compiler helpers, and CLI call sites, producing bypasses and inconsistent error ordering. |
| Security | 2/10 | Actor/tenant checks improve, but the claimed sandbox closure is bypassable and the bypass can recover arbitrary built-in modules. |
| Conformance | 2/10 | The merged result fails required tests, ruff, mypy, web typecheck/build, and the user-mandated HiAgent handler contract. |
| **Overall** | **3.25/10** | Below the 7.0 threshold, with Security and Conformance both at or below 3. |

## Premise verification

The supplied branch facts were accurate:

- `main`: `2c1a3a946b84d070d45be186c3a4e396997bd17e`
- target: `fc08073d662674d4c87c1aaea72a868d62335b03`
- merge base: `5a088ed172e2d5208dd9c6de8ba5f2747d410e19`
- divergence: 4 commits unique to `main`, 18 unique to the target
- target tip timestamp: `2026-07-15T16:18:09-07:00`
- target diff: `75 files changed, 5412 insertions(+), 747 deletions(-)`
- the real throwaway merge completed without textual conflicts
- `git diff --check HEAD` on the merged tree exited 0 with no output

Actual merge output:

```text
$ git merge --no-commit --no-ff AlataChan/integrate-deep-dive-fixes
Automatic merge went well; stopped before committing as requested
```

## 1. Semantic conflict analysis

### Actual prospective execution order

For the service path, the merged code executes these layers in order:

1. `validate()` validates the raw IR and the raw Code-node source.
2. `HiagentAdapter.compile()` calls `assert_runtime_ir_supported()`.
3. The HiAgent compiler emits the final Code-node source, including the canonical fallback wrapper.
4. `_lint_emitted_python_code_nodes()` lints the final emitted Python.
5. `check_generated_chatflow_config()` validates the emitted HiAgent shape.

Relevant locations in the prospective merged tree:

- `loom/validator/validate.py:40-87`
- `loom/validator/policy.py:149-185`
- `loom/runtimes/hiagent/adapter.py:51-69`
- `loom/runtimes/base.py:247-321`
- `loom/runtimes/hiagent/v2_6/compiler.py:163-199`
- `loom/runtimes/hiagent/v2_6/compiler.py:202-231`
- `loom/runtimes/hiagent/v2_6/compiler_nodes.py:555-565`

### No double raise, but the first error is path-dependent

Exceptions short-circuit normally, so there is no double raise. On an IR containing both unsupported Code-node retry semantics and a two-parameter handler:

```text
adapter_path= UnsupportedConstruct hiagent 2.6 does not safely support code.retry at node 'code': only an attempt count is emitted; backoff and retry_on semantics are lost Remediation: remove the retry requirement or add a conformance-tested mapping
direct_compiler_path= HiagentSpecError HiAgent Python Code node 'code' source: Invalid HiAgent handler signature (2 positional parameters). HiAgent passes every configured node input as one merged dict only to the first parameter; later parameters keep their defaults and silently read empty. Use def handler(input=""):. [code_node.handler.signature]
```

This ordering is reasonable inside the adapter: the unsupported capability is detected before emission, so the Code-node lint is not reached. The problem is that not all production-capable entry points use the adapter:

- `loom/cli/commands/compile.py:77-80` calls `compile_ir_chatflow()` directly for HiAgent chatflow mode.
- `loom/cli/commands/hiagent_push.py:75-89` calls `build_chatflow_config_draft()`, `build_agent_config_draft()`, or `build_agent_config_request()` directly.
- The capability assertion lives in `loom/runtimes/hiagent/adapter.py:58-66`, not in the core compiler helpers.

Therefore "fail closed" is only true for callers that choose the adapter path. The CLI can still emit or push constructs that the capability matrix explicitly declares unsafe.

The service path also catches only `UnsupportedConstruct` at `loom/service/routes/sessions.py:1375-1378`. A fatal Code-node lint raises `HiagentSpecError`, a `ValueError`, and is not converted there into the same structured HTTP 400 error. A bad handler can therefore surface as an internal server error rather than a controlled compile rejection.

### Hard validator/linter contradiction

The branch defines:

```python
_PY_DANGEROUS_CALLS = {"eval", "exec", "compile", "__import__", "open", "input"}
```

and then rejects any `ast.Name` with one of those identifiers at `loom/validator/policy.py:172-173`. This is not limited to a call to the dangerous built-in `input()` function.

Main's linter and documentation require:

```python
def handler(input=""):
    params = input if isinstance(input, dict) else {}
```

The merged result therefore rejects the exact runtime contract main added. The proof run produced:

```text
canonical validation= [('policy', "reference to 'input' is forbidden in a sandboxed code node", 'nodes[code]'), ('policy', "reference to 'input' is forbidden in a sandboxed code node", 'nodes[code]')]
canonical compile_warnings= []
```

This is a genuine semantic conflict caused by the four commits on main, despite the absence of textual conflicts. The validator inspects the raw source, while the compiler lint inspects final emitted source; no test currently asserts that one Code-node program passes both layers.

## 2. Does the merged result work?

No. The isolated merged tree fails multiple required gates.

Test environment:

```text
Python 3.12.8
pytest 8.4.2
ruff 0.16.0
mypy 1.20.2
Node v24.14.0
npm 11.9.0
```

### Python full suite

Command:

```text
.venv/bin/pytest -v
```

Actual summary:

```text
collected 531 items
FAILED tests/cli/test_session.py::test_session_show_turns_does_not_modify_db_file
1 failed, 524 passed, 4 skipped, 2 xfailed, 1 warning in 26.46s
```

Failure:

```text
>       assert (tmp_path / "data" / "sessions.db").read_bytes() == before
E       assert b"SQLite form...0\x00\x00\x00" == b'SQLite form...0\x00\x00\x00'
E
E         At index 27 diff: b'\x02' != b'\x01'
```

The same focused test passes on current `main`:

```text
$ pytest -q tests/cli/test_session.py::test_session_show_turns_does_not_modify_db_file
.                                                                        [100%]
1 passed in 0.62s
```

It failed twice consecutively on the merged tree. The branch's session schema/concurrency work changes WAL/database behavior enough that a command advertised and tested as read-only can alter the main database bytes. Investigate explicit connection closure and WAL checkpoint behavior around `SessionStore._connect()` / `_init()` at `loom/state/store.py:854-980`; do not weaken the read-only regression test.

### Ruff

Command:

```text
.venv/bin/ruff check .
```

Actual summary:

```text
Found 71 errors.
[*] 25 fixable with the `--fix` option (44 hidden fixes can be enabled with the `--unsafe-fixes` option).
```

Current `main` is not clean either under the same installed ruff version:

```text
Found 75 errors.
[*] 29 fixable with the `--fix` option (44 hidden fixes can be enabled with the `--unsafe-fixes` option).
```

The branch reduces the net count by four, so the pre-existing ruff debt is not evidence that the branch alone regressed the gate. It does add new import-order findings in:

- `tests/validator/test_policy.py:139`
- `tests/validator/test_validate.py:1`

The key point is that the requested merged-tree ruff gate is still red.

### Mypy

Command:

```text
.venv/bin/mypy loom
```

Actual merged-tree output:

```text
loom/ir/canonicalize.py:106: error: Returning Any from function declared to return "str"  [no-any-return]
loom/diff/ir_diff.py:128: error: Argument 1 to "_diff_node_list" has incompatible type "Any | list[Any] | None"; expected "list[Any]"  [arg-type]
loom/diff/ir_diff.py:128: error: Argument 2 to "_diff_node_list" has incompatible type "Any | list[Any] | None"; expected "list[Any]"  [arg-type]
loom/diff/ir_diff.py:133: error: Argument 1 to "set" has incompatible type "Any | dict[Any, Any] | None"; expected "Iterable[Any]"  [arg-type]
loom/diff/ir_diff.py:134: error: Item "None" of "Any | dict[Any, Any] | None" has no attribute "get"  [union-attr]
loom/diff/ir_diff.py:135: error: Item "None" of "Any | dict[Any, Any] | None" has no attribute "get"  [union-attr]
loom/diff/ir_diff.py:156: error: Incompatible default for parameter "exclude" (default has type "frozenset[Never]", parameter has type "set[str]")  [assignment]
loom/validator/policy.py:180: error: Incompatible types in assignment (expression has type "Attribute", variable has type "str")  [assignment]
loom/validator/policy.py:182: error: Incompatible types in assignment (expression has type "expr", variable has type "str")  [assignment]
loom/registry/design_knowledge.py:81: error: Function "loom.registry.design_knowledge.DesignKnowledgeCatalog.list" is not valid as a type  [valid-type]
loom/service/routes/personas.py:13: error: Returning Any from function declared to return "list[PersonaBrief]"  [no-any-return]
loom/service/routes/sessions.py:1185: error: Call to untyped function (unknown) in typed context  [no-untyped-call]
Found 12 errors in 6 files (checked 105 source files)
```

Current `main` has two of those errors (`design_knowledge.py` and `personas.py`). The prospective merge adds ten errors across the branch-modified canonicalization, diff, validator, and session-route code.

### Web tests and lint

Commands:

```text
npm test
npm run lint
```

Actual results:

```text
Test Files  21 passed (21)
Tests  79 passed (79)
Duration  4.27s
```

```text
> eslint . --ext ts,tsx --max-warnings 0
```

Both commands exited 0.

### Web production build

Command:

```text
npm run build
```

Actual result: exit 2.

The branch-added `web/src/components/console/FlowNode.test.tsx` has 11 `TS2740` errors because `nodeProps()` at lines 29-31 omits required `NodeProps` fields. The branch-modified `web/src/lib/flow-layout.test.ts` also has:

```text
src/lib/flow-layout.test.ts(1,30): error TS2307: Cannot find module 'node:fs' or its corresponding type declarations.
src/lib/flow-layout.test.ts(2,25): error TS2307: Cannot find module 'node:path' or its corresponding type declarations.
src/lib/flow-layout.test.ts(96,33): error TS2304: Cannot find name '__dirname'.
```

The production build never reaches Vite because `tsc --noEmit` fails first.

`npm ci` itself completed, but reported:

```text
added 506 packages, and audited 507 packages in 19s
14 vulnerabilities (1 low, 6 moderate, 6 high, 1 critical)
```

This audit count was not attributed to the branch without a dependency-level provenance comparison, but it is relevant release risk.

## 3. Security review of `8d8deec`

### Finding: only narrowed, not closed

`8d8deec` catches direct attribute syntax such as:

```python
().__class__.__bases__[0].__subclasses__()
```

It does not catch dynamic lookup:

```python
getattr(value, "__class__")
```

The proof used nested `getattr` calls to recover the class hierarchy, selected `BuiltinImporter`, loaded the built-in `os` module, and invoked `getpid`. No forbidden `ast.Attribute` node or forbidden import statement appeared in the source.

Actual merged-tree result:

```text
getattr_bypass validation= []
getattr_bypass compile_warnings= [('code_node.handler.signature_style', 'Use the canonical HiAgent entry signature def handler(input=""):.'), ('code_node.handler.unpack_missing', 'The first executable statement must be params = input if isinstance(input, dict) else {}.')]
getattr_bypass handler_result= {'x': '75472'}
```

The compiler treats the non-canonical handler as warnings, not fatal errors, so the bypass can be emitted. Replacing `getpid` with dynamically resolved process or filesystem functions extends the same primitive to command execution or file access.

Blocking `getattr` alone is not a sufficient security boundary. Equivalent reflection can be assembled with dynamically constructed strings and mapping access such as `vars(type)[name]`. A denylist over Python AST attributes cannot safely sandbox arbitrary Python.

### Required security direction

Before this work can merge, choose and test one of these fail-closed designs:

1. Use a strict AST/call allowlist with no arbitrary reflection, dynamic attribute access, dynamic call targets, or unrestricted builtins; or
2. Treat untrusted Python as unsupported and reject it until execution is isolated by a real process/container sandbox with restricted builtins, filesystem, network, environment, syscalls, CPU, and memory.

At minimum, `loom/validator/policy.py:122-138` and `149-185` must be redesigned, and regression tests must demonstrate that:

- the canonical HiAgent handler passes;
- a call to the built-in `input()` is rejected without rejecting the handler parameter;
- direct dunder access is rejected;
- `getattr`/`vars`/string-built introspection chains are rejected;
- the policy is applied to the final emitted source, not only the pre-wrapper raw IR source.

## 4. Staleness risk

Main's four unique commits modify only HiAgent contract code/docs and `AGENTS.md`; the branch does not textually overwrite those files. The merged fallback wrapper remains the fixed:

```python
def handler(input=""):
    params = input if isinstance(input, dict) else {}
```

The staleness risk is semantic:

- Main newly declares `input` mandatory; the branch newly declares `input` forbidden.
- Main lint runs on emitted source; branch policy runs on raw source.
- Main added fatal `HiagentSpecError` paths; the merged service catch only handles the branch's `UnsupportedConstruct`.
- Main's linter is reached through direct compiler helpers, while the branch's capability gate exists only in the adapter.
- Main's vendored handbook and `node-specs.md` now document a contract that the merged validator cannot accept.

No other main-only code area was changed differently by the branch. The handbook additions and fallback-wrapper fix are preserved by the textual merge.

## 5. Changes required before reconsideration

All of the following are blocking:

1. **Unify the Code-node contract and security policy.**
   - Fix `loom/validator/policy.py:122-185` so `input` is legal as the single handler argument/unpack source while a call to `input()` remains illegal.
   - Replace the reflection denylist with a defensible strict allowlist or real sandbox.
   - Validate the final emitted source.
2. **Make fail-closed capability enforcement unavoidable.**
   - Route `loom/cli/commands/compile.py:77-80` and `loom/cli/commands/hiagent_push.py:75-89` through `HiagentAdapter.compile()` with `CompileContext`, or enforce capabilities inside every public core compiler helper.
   - Add tests proving CLI compile, API push, and service compile reject the same unsupported construct with the same structured error.
3. **Normalize error handling.**
   - Catch `HiagentSpecError` alongside `UnsupportedConstruct` in `loom/service/routes/sessions.py:1375-1378` and return a structured client error, not a server error.
4. **Fix the session read-only regression.**
   - Resolve explicit SQLite connection lifetime/WAL checkpoint behavior around `loom/state/store.py:854-980`.
   - Keep `tests/cli/test_session.py:109-121` passing without weakening its assertion.
5. **Restore Python gates.**
   - Fix the ten branch-added mypy errors listed above.
   - Make `ruff check .` pass under a pinned tool version; at minimum remove the two branch-added validator-test import findings.
6. **Restore the web production build.**
   - Supply valid `NodeProps` in `web/src/components/console/FlowNode.test.tsx:29-31`, or type the test helper against the component's actual accepted props.
   - Add/configure Node types and replace ESM-incompatible `__dirname` usage in `web/src/lib/flow-layout.test.ts:1-2,96`.
7. **Add merged-behavior regression tests.**
   - One canonical handler must pass validator + adapter capability gate + emitted-source lint + spec check.
   - One source containing both an unsupported runtime feature and a bad handler must have documented, consistent error precedence across service and CLI.

After those fixes, rerun the real merge against current `main` and require green results from Python tests, ruff, mypy, web tests, web lint, and web build before reconsidering the branch.
