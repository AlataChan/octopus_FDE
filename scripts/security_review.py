#!/usr/bin/env python3
"""Security review helper — runs static checks against an IR file.

Not a substitute for human review. Flags the obvious so human review covers
the subtle.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DANGEROUS_PY = [
    r"\b__import__\b",
    r"\beval\b",
    r"\bexec\b",
    r"\bopen\(\s*['\"]/",  # absolute path open
    r"\bos\.system\b",
    r"\bsubprocess\b",
    r"\bsocket\.\w+\(",
    r"\brequests\.\w+\(",
    r"\burllib\b",
    r"\bpickle\b",
    r"\bmarshal\b",
]
DANGEROUS_JS = [
    r"\beval\(",
    r"\bnew Function\(",
    r"\brequire\(['\"]child_process['\"]\)",
    r"\bfetch\(",
    r"\bXMLHttpRequest\b",
]

PROMPT_INJECTION_HINTS = [
    r"untrusted",
    r"user_input",
    r"<\|",
    r"```",
]


def review_ir(doc: dict) -> list[str]:
    findings: list[str] = []
    for n in _walk_nodes(doc["nodes"]):
        if n["type"] == "code":
            patterns = DANGEROUS_PY if n["language"] == "python" else DANGEROUS_JS
            for pat in patterns:
                if re.search(pat, n["source"]):
                    findings.append(
                        f"node {n['id']}: code uses '{pat}' — sandbox escape vector"
                    )
            if n.get("idempotency_key") is None:
                findings.append(
                    f"node {n['id']}: code without idempotency_key — re-run safety unclear"
                )
        if n["type"] == "http" and n.get("credential") and "${input." in (n.get("url") or ""):
            findings.append(
                f"node {n['id']}: credentialed http with user-controlled URL — SSRF"
            )
        if n["type"] == "agent":
            sys_prompt = n.get("system_prompt") or ""
            for hint in PROMPT_INJECTION_HINTS:
                if re.search(hint, sys_prompt, re.I):
                    findings.append(
                        f"node {n['id']}: agent system prompt mentions {hint!r} — confirm typed-registry isolation"
                    )
            tools = n.get("tools", [])
            if not tools:
                findings.append(f"node {n['id']}: agent has empty tools list")
    return findings


def _walk_nodes(nodes):
    for n in nodes:
        yield n
        if n["type"] == "loop":
            yield from _walk_nodes(n["body"])
        elif n["type"] == "parallel":
            for branch in n["branches"].values():
                yield from _walk_nodes(branch)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("ir_files", nargs="+")
    args = p.parse_args()
    any_findings = False
    for f in args.ir_files:
        doc = json.loads(Path(f).read_text())
        findings = review_ir(doc)
        if findings:
            any_findings = True
            print(f"\n{f}:")
            for x in findings:
                print(f"  - {x}")
    return 1 if any_findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
