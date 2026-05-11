# ADR 0026: FDE Web Console Web Stack

Status: Accepted

Date: 2026-05-11

## Context

Phase 2 adds a browser console for FDE engineers to plan, validate, compile,
and download customer workflow artifacts. The user selected a lightweight stack:
Vite, React, FastAPI, and SQLite. The console must support Chinese and English,
keep the MVP easy to ship, and avoid heavyweight UI frameworks.

## Decision

Use a Vite + React + TypeScript frontend under `web/`.

The frontend stack is:

- React 18 and React DOM 18
- Vite 5+ (M2.1 currently uses the patched Vite 6 line)
- TypeScript 5
- Tailwind CSS 3
- TanStack Query 5 for server state
- Zustand 4 for local client state when needed
- i18next 23 and react-i18next 13 for Chinese/English localization
- react-router-dom 6 for client routing
- openapi-typescript 7 for generated backend API types

The generated OpenAPI file is checked in at
`web/src/lib/types.generated.ts`. Developers regenerate it with:

```bash
cd web
npm run gen:types
```

The backend must be running while generating types.

Do not add MUI, Ant Design, shadcn/ui, Chakra UI, or another component library
in Phase 2 M2.1. Product UI can be built directly from Tailwind primitives until
the M2.2 console surface proves what reusable components are needed.

## Consequences

- The frontend remains small and easy to iterate locally.
- Tailwind keeps styling close to the components without a heavy UI dependency.
- Generated OpenAPI types give the API client a stable contract with FastAPI.
- Future M2.2 and M2.3 UI work can add components incrementally without
  replacing the stack.
