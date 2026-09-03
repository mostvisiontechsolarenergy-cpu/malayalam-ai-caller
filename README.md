# Malayalam AI Caller

Production-oriented, multi-tenant administration and knowledge workspace for a Malayalam and Malayalam-English AI calling platform. This repository contains the approved **Phases 1 through 5**: architecture, Docker services, authentication, tenant-safe data APIs, the admin dashboard, AI agent configuration, advanced document knowledge, grounded AI tests, browser voice, and a Vobiz phone-call bridge.

Gemini Free Tier and OpenAI are selectable AI providers. Vobiz is the telephony provider. Vobiz carrier minutes are billed separately from Gemini and may require account balance and regulatory verification. No fake telephony, fake call analytics, fake embeddings, or mock business records are presented as production functionality.

## Implemented capabilities

- FastAPI + SQLAlchemy + Alembic backend
- PostgreSQL with pgvector/HNSW indexing and Redis Docker services
- JWT authentication with `SUPER_ADMIN`, `ADMIN`, and `STAFF` roles
- Explicit tenant context and company-scoped database queries
- Company, client, product, service, price, offer, FAQ, and manual knowledge models
- Current/active filtering for authoritative pricing, offers, and knowledge
- Next.js/TypeScript/Tailwind admin workspace with responsive navigation
- Secure browser session bridge using HTTP-only JWT cookies
- Real dashboard counts and recent CRM activity
- Connected create/edit/delete screens for clients, products, services, prices, offers, FAQs, and manual knowledge
- Tenant-scoped AI Agent Builder records
- Private PDF, DOCX, TXT, CSV, and XLSX upload, extraction, and section-aware chunking
- Hybrid structured/manual/FAQ/document retrieval with source and latency diagnostics
- Deterministic authority ordering: structured pricing and active offers outrank documents
- Price conflict detection, knowledge health scoring, and conflict resolution workflow
- AI Knowledge Test page with grounded answer preview, called tools, source trace, and conflicts
- Provider-selectable grounded text conversations (Gemini or OpenAI)
- Malayalam Gemini Live browser audio with one-use ephemeral credentials, transcripts, barge-in, and controlled tools
- Existing OpenAI Realtime WebRTC browser path retained when OpenAI is selected
- Vobiz outbound calls with signed webhooks, consent enforcement, status history, and call termination
- Bidirectional Vobiz Streams bridged to Gemini Live with μ-law/8 kHz input and native L16/24 kHz playback
- Customer-confirmed automatic callbacks with exact Asia/Kolkata scheduling, persistent PostgreSQL state, consent revalidation, restart recovery, and no manual approval step
- Phone-call transcripts and controlled company-knowledge tools stored in the existing conversation timeline
- Unit/API tests covering tenant isolation, document security, source tracking, retrieval priority, conflicts, health, and time-sensitive facts

## Gemini free-tier text and voice

Set these values in `.env` to use the Google AI Studio project tier:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your-full-private-key
GEMINI_TEXT_MODEL=gemini-3.1-flash-lite
GEMINI_LIVE_MODEL=gemini-3.1-flash-live-preview
GEMINI_VOICE=Kore
```

The permanent key stays in the backend. The authenticated Voice Playground receives a one-use ephemeral token and connects directly to Gemini Live. Free-tier quotas and Google's free-tier data terms apply. Phone calls are started separately from the AI Phone Calls page.

## Vobiz phone calls

Add the following values to `.env` after creating a Vobiz account and obtaining an outbound-capable caller number:

```env
TELEPHONY_PROVIDER=vobiz
VOBIZ_AUTH_ID=MA_xxxxxx
VOBIZ_AUTH_TOKEN=your-private-auth-token
VOBIZ_PHONE_NUMBER=+91xxxxxxxxxx
VOBIZ_API_BASE_URL=https://api.vobiz.ai/api
VOBIZ_VALIDATE_SIGNATURES=true
PUBLIC_WEBHOOK_BASE_URL=https://your-public-backend.example
```

`PUBLIC_WEBHOOK_BASE_URL` must expose the FastAPI backend over public HTTPS; its corresponding WSS address carries the bidirectional media stream. Never put the Auth Token in browser code, chat, or a screenshot. Calls are blocked unless the client record has `GRANTED` consent, Calling allowed is enabled, and Opted out is false. Vobiz is pay-as-you-go; sufficient balance, an allowed caller ID, routing permission, and applicable India KYC are still required.

## OpenAI embeddings

Set `OPENAI_API_KEY` in `.env` to activate `text-embedding-3-small` semantic retrieval. The application requests 1,024-dimensional embeddings and stores them in pgvector. Without a key, documents are still extracted and searched using lexical hybrid retrieval; their UI status is `SKIPPED NO KEY`. No placeholder vectors are created.

## Local setup with Docker

The Docker stack also includes a local n8n automation service at
`http://localhost:5678`. See [N8N_LOCAL_SETUP.md](N8N_LOCAL_SETUP.md) for the authenticated
connection check and the safe proposal/payment integration order.

1. Copy `.env.example` to `.env` and replace `JWT_SECRET`.
2. Start the stack:

   ```powershell
   docker compose up --build -d
   ```

3. Run the migration:

   ```powershell
   docker compose exec backend alembic upgrade head
   ```

4. Create the first company and administrator (works only while the user table is empty):

   ```powershell
   Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/bootstrap `
     -ContentType 'application/json' `
     -Body '{"company_name":"Example Company","admin_name":"Owner","email":"owner@example.com","password":"replace-with-a-strong-password"}'
   ```

5. Open <http://localhost:3000/login> and sign in with the administrator account. API documentation remains available at <http://localhost:8000/docs> in development.

## Local backend tests without Docker

Use Python 3.12+:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
pytest
```

## Tenant selection

Normal admin/staff tokens are permanently scoped to the user's company. A `SUPER_ADMIN` may address another company only by sending an explicit `X-Company-ID` header. Entity identifiers are always queried together with the resolved company ID, so knowing another tenant's UUID does not grant access.

## Documentation

- [System architecture](ARCHITECTURE.md)
- [Database design](DATABASE.md)
- [Implementation phases](IMPLEMENTATION_PLAN.md)
- [Knowledge and RAG design](KNOWLEDGE_ARCHITECTURE.md)
- [Telephony abstraction](TELEPHONY_ARCHITECTURE.md)
- [Verified telephony limitations](TELEPHONY_LIMITATIONS.md)
