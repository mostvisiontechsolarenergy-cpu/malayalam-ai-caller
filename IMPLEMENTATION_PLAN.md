# Implementation Plan

## Phase 1 — foundation (complete)

- Architecture and security documentation
- Docker Compose with PostgreSQL/pgvector and Redis
- FastAPI, SQLAlchemy, Alembic, and typed settings
- JWT authentication and one-time bootstrap
- Tenant-safe company/client/catalog/knowledge APIs
- Initial migration and automated isolation/validity tests
- Initial Next.js shell

Exit gate: migration and tests passed; user approval received.

## Phase 2 — connected admin UI (complete)

- Premium responsive dashboard and access-aware navigation
- Secure HTTP-only browser session bridge to FastAPI
- Real company summary metrics and recent CRM activity
- Client, product, service, pricing, offer, FAQ, and knowledge CRUD screens
- Tenant-scoped AI Agent Builder model, migration, APIs, and UI
- Loading, error, empty, search, edit, and delete states
- No mock business data or simulated call analytics

Exit gate: migration, backend tests, lint, frontend typecheck, production build, and HTTP smoke checks pass. Stop for approval.

## Phase 3 — advanced knowledge (complete)

- Private persistent document storage and tenant-scoped upload/download APIs
- PDF, DOCX, TXT, CSV, and XLSX extraction with section-aware chunks
- OpenAI embeddings with pgvector HNSW cosine search and honest lexical fallback
- Hybrid structured/manual/FAQ/document retrieval with deterministic authority order
- Source tracking, retrieval latency, tool traces, and stored Knowledge Test runs
- Structured-price conflict detection and administrator resolution workflow
- Knowledge health score and actionable gap/failure/staleness findings
- Responsive Documents, Knowledge Health, and AI Knowledge Test pages

Exit gate: PostgreSQL migration, pgvector extension/index, backend tests, lint, frontend typecheck/build, and live upload/process/download/delete smoke checks pass. Stop for Phase 4 approval.

## Phase 4 — Gemini/OpenAI playground (complete)

- Provider-selectable Gemini or OpenAI AI orchestration
- Controlled knowledge tools and Malayalam/code-switching prompts
- Browser voice playground with short-lived Gemini Live tokens
- Text and voice transcripts, tool traces, and structured reports
- Shared orchestration for the playground and future phone path

Exit gate: real Gemini Malayalam text response, Gemini Live token creation, backend tests, lint, frontend typecheck/build, and authenticated browser smoke checks pass.

## Phase 5 — Vobiz telephony integration (implemented; live credentials pending)

- Vobiz outbound call creation and termination
- Signed Vobiz XML/status callbacks with per-call opaque tokens
- Consent, opt-out, tenant, and administrator authorization enforcement
- Real call history and provider readiness UI

## Phase 6 — realtime phone bridge (implemented; live trial call pending)

- Vobiz bidirectional Streams using `<Stream bidirectional="true">`
- μ-law/8 kHz to Gemini PCM/16 kHz input conversion
- Native Gemini L16 PCM/24 kHz playback through Vobiz `playAudio`
- Gemini VAD, Vobiz `clearAudio` interruption, knowledge tools, and transcripts

Exit gate: configure Vobiz credentials, an approved caller ID, sufficient balance/KYC, and a public HTTPS/WSS endpoint, then complete one explicitly confirmed controlled call. No successful phone call is claimed before that test.

## Phase 7 — operations and hardening

Add follow-ups, analytics, reports, conversation memory, callbacks, configurable cost accounting, compliance policies, audit UI, rate limiting, observability, backups, load testing, and production deployment controls.
