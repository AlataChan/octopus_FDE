# Vendored Hiagent Handbook

Upstream platform documentation, vendored so that `docs/runtimes/hiagent/node-specs.md`
citations resolve inside this repository. These files are **read-only reference
material** — do not edit them here. Fixes go upstream, then re-vendor.

## Source

| Field | Value |
|---|---|
| Upstream repo | `https://github.com/AlataChan/hiagent-architect-kit` |
| Pinned commit | `330312df867c4c6d5c451bc08c3e38a8ee83be3d` |
| Commit date | 2026-07-26 |
| Upstream path | `references/hiagent-handbook/raw/workflow/` |
| Vendored on | 2026-07-27 |

## Scope

Only `raw/workflow/` is vendored — it holds the workflow/node documentation that
`node-specs.md` actually cites. The upstream handbook also carries `agent/`,
`knowledge-base/`, `plugin/`, `model/`, `integration/`, `operation/`, and
`overview/` trees (~1.3M total). Vendor additional subtrees only when a spec
document in this repo needs to cite them, and record the addition in the table
above.

These files are Chinese-language platform source material and are kept verbatim
so that quotes remain checkable against the vendor's documentation.

## Re-vendoring

```bash
KIT=/path/to/hiagent-architect-kit
git -C "$KIT" rev-parse HEAD          # record this in the table above
rm -rf docs/runtimes/hiagent/handbook/workflow
cp -R "$KIT/references/hiagent-handbook/raw/workflow" docs/runtimes/hiagent/handbook/
```

After re-vendoring, re-check any `[LIVE]` markers in `node-specs.md` that
contradict the handbook: `[LIVE]` means live-API behavior overrides the
documented behavior, and an upstream doc update may resolve or invalidate one.
