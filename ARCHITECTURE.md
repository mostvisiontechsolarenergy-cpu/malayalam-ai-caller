# System Architecture

## Current repository analysis

The starting workspace contained no source repository, package manifest, database schema, or application code. Phase 1 therefore establishes a new monorepo without legacy compatibility constraints.

## Target topology

```text
Next.js admin UI
        |
        | HTTPS / secure WebSocket
        v
FastAPI API --------------------------------------------------+
  | auth + RBAC         | knowledge tools                    |
  | tenant context      | call orchestration (future)        |
  v                     v                                    |
PostgreSQL + pgvector   Redis                                 |
  |                     | sessions/rate limits (future)      |
  |                     +-------------------------------------+
  |
  +--> private document processing + pgvector (Phase 3)
  +--> Gemini Live / OpenAI Realtime gateway (Phase 4)
  +--> TelephonyProvider --> Vobiz Programmable Voice (Phase 5)
```

The backend owns all permanent credentials and business facts. Gemini browser sessions use a one-use ephemeral token minted by the authenticated backend; OpenAI browser sessions use a backend-created WebRTC exchange. The browser never receives a permanent provider secret. The voice playground and telephone gateway will share one orchestration and knowledge-tool layer so that test behavior cannot diverge from live-call behavior.

## Folder structure

```text
backend/
  alembic/                 versioned database migrations
  app/
    api/v1/                HTTP routers
    core/                  configuration, auth, tenant dependencies
    db/                    engine/session and declarative models
    schemas/               request/response contracts
    services/              reusable business and retrieval logic
  tests/                   isolated API and business-rule tests
frontend/
  app/                     Next.js App Router shell
  components/              Phase 2 UI components
ARCHITECTURE.md
DATABASE.md
KNOWLEDGE_ARCHITECTURE.md
TELEPHONY_ARCHITECTURE.md
TELEPHONY_LIMITATIONS.md
IMPLEMENTATION_PLAN.md
docker-compose.yml
```

## API and service boundaries

- `core/security.py`: password hashing and short-lived signed access tokens.
- `core/dependencies.py`: authenticated user, role checks, and authoritative tenant resolution.
- `api/v1/*`: validation and HTTP semantics; no provider credentials or AI prompts.
- `services/knowledge.py`: deterministic structured-first hybrid retrieval and tenant-filtered vector/lexical document search.
- `services/documents.py`: private file extraction, chunking, and optional OpenAI embedding batches.
- `services/knowledge_health.py`: price conflict detection and computed knowledge quality findings.
- `services/telephony/base.py`: provider-neutral telephone contract.
- `services/telephony/vobiz_provider.py`: outbound calls and normalized provider status.
- `services/telephony/vobiz_bridge.py`: Vobiz bidirectional Streams to Gemini Live gateway.
- `services/ai_conversations.py`: provider selection, grounded text turns, secure Live session provisioning, instructions, and reporting.
- `services/ai_tools.py`: tenant-scoped, allow-listed knowledge functions shared by text and voice.

## Malayalam voice architecture

The browser playground supports Gemini Live audio over WebSocket using a one-use backend-minted token, and retains OpenAI Realtime over WebRTC when that provider is selected. The telephone path uses Vobiz's bidirectional `<Stream>` WebSocket through a server-side media gateway. The gateway converts Vobiz base64 μ-law/8 kHz media to Gemini PCM/16 kHz input and converts Gemini PCM/24 kHz output back to Vobiz `playAudio` events. Audio events, transcripts, tool calls, and source records join one conversation record. Gemini VAD plus Vobiz `clearAudio` provides barge-in. Malayalam-first instructions permit natural English code-switching and keep spoken turns concise.

Gemini Live supplies Malayalam audio input/output, built-in transcription, and function calling. Its permanent key remains server-side while the browser uses a constrained-lifetime credential. OpenAI's Realtime path remains available behind the same provider boundary. Models and provider selection remain environment variables.

## AI tool architecture

Tools are server-owned typed commands, never arbitrary SQL:

```text
Realtime function request
  -> validate call/user tenant context
  -> dispatch allow-listed tool
  -> query company_id + validity + active constraints
  -> return concise fact payload + source metadata
  -> append source-use audit record
```

Read tools will include company knowledge, products, services, prices, offers, FAQs, and document chunks. Write tools (follow-up, lead status, callback, requirements) will validate call ownership and use idempotency keys. Prices, offers, policies, and other critical facts will never fall back to model memory.

## Security architecture

- Argon2 password hashes and signed, expiring JWT access tokens.
- Default-deny role dependencies; bootstrap is one-time and transactionally guarded.
- Tenant ID comes from the authenticated server context, not request bodies.
- Entity lookups use `(company_id, id)` predicates to prevent insecure direct object references.
- Secrets are environment-only and redacted from structured logs.
- CORS is allow-listed; production requires TLS and secure proxy headers.
- Vobiz HTTP callbacks require V2/V3 HMAC-SHA256 validation; callbacks and WebSocket streams also require an opaque per-call token and strict CallUUID correlation.
- Audit logs capture security-sensitive mutations without storing credentials.
- Database row-level security is planned as defense in depth after connection-pool tenant context is implemented and tested.
