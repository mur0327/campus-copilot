# Campus Copilot Repository Guide

## Project Scope

Campus Copilot is a kiosk-oriented academic guidance system for Honam University.

- `backend`: FastAPI API and RAG services
- `worker`: crawling, parsing, embedding, and scheduled jobs
- `frontend`: kiosk UI and admin UI
- `pi-setup`: Raspberry Pi kiosk and local print-service support

The system is developed phase-by-phase because each subsystem is relatively independent.

## Source Of Truth

Use these documents as the primary source of truth before changing code or plans.

- [docs/superpowers/specs/2026-04-08-architecture-design.md](docs/superpowers/specs/2026-04-08-architecture-design.md)
- [docs/superpowers/plans/2026-04-08-phase-roadmap.md](docs/superpowers/plans/2026-04-08-phase-roadmap.md)
- [docs/superpowers/plans/2026-04-08-phase-1-project-scaffold.md](docs/superpowers/plans/2026-04-08-phase-1-project-scaffold.md)
- [docs/superpowers/specs/2026-04-19-phase-2-crawling-parsing-design.md](docs/superpowers/specs/2026-04-19-phase-2-crawling-parsing-design.md)
- [docs/superpowers/plans/2026-04-19-phase-2-crawling-parsing-implementation.md](docs/superpowers/plans/2026-04-19-phase-2-crawling-parsing-implementation.md)
- [docs/superpowers/specs/2026-05-06-phase-3-kiosk-admin-frontend-design.md](docs/superpowers/specs/2026-05-06-phase-3-kiosk-admin-frontend-design.md)
- [docs/superpowers/plans/2026-04-12-phase-3-kiosk-admin-frontend.md](docs/superpowers/plans/2026-04-12-phase-3-kiosk-admin-frontend.md)

If a document and the repository state disagree, update the relevant document or explicitly call out the mismatch before proceeding.

## Phase Workflow

Do not treat the whole project as one implementation batch.

1. Work one phase at a time.
2. Keep later phases at overview level until they are the active phase.
3. For an active phase, follow `spec -> implementation plan -> execution`.
4. If a request spans multiple independent subsystems, split it by phase or subsystem before implementing.

## Current Working Mode

The project scaffold, Phase 2 worker crawling/parsing implementation, and Phase 3 kiosk/admin frontend baseline are merged or ready to be treated as completed baseline work.

- `Phase 1` scaffold is complete.
- `Phase 2` worker crawling/parsing is complete in code and should be treated as the current baseline.
- `Phase 3` kiosk/admin frontend baseline is complete. Treat kiosk UI and admin UI as implemented draft surfaces that can be iterated on, not as missing scaffold.
- `Phase 3` STT and TTS are UI entry points only. Do not add real Web Speech API behavior unless a later phase explicitly promotes it.
- `Phase 3` FAQ/popular/category data is frontend-fallback friendly; backend completion for FAQ/popular and real data supply belongs to later backend/RAG work.
- `Phase 4` and later should remain lightweight until promoted to active work.
- When asked to review completed phase work, prioritize regressions, stale docs, verification gaps, and cross-phase boundary leaks.

## Implementation Rules

- Keep changes aligned with the current active phase only.
- Do not silently introduce later-phase behavior while working on an earlier active phase.
- Prefer small, explicit stubs when scaffolding a future subsystem rather than partial feature implementations.
- Preserve clear boundaries between `backend`, `worker`, `frontend`, and `pi-setup`.
- When adding infrastructure files, make sure referenced files are also created in the same plan or change set.

## Documentation Rules

- New design documents belong under `docs/superpowers/specs/`.
- New implementation plans belong under `docs/superpowers/plans/`.
- Phase overview documents should stay short and should not turn into full implementation plans early.
- When self-reviewing a document, check for:
  - missing referenced files
  - mismatched tech choices
  - scope that leaks into later phases
  - incomplete commit or verification steps

## Practical Defaults

- Keep repository-level instructions concrete and phase-aware.
- Prefer updating docs first when the repository is still in planning or scaffold mode.
- Before claiming a phase is ready, verify the relevant document, command, or checklist that proves it.
