# Database Design

## Conventions

- UUID primary keys prevent predictable public identifiers.
- All tenant-owned tables contain a non-null, indexed `company_id` foreign key.
- Timestamps are timezone-aware UTC values.
- Currency amounts use `NUMERIC(12,2)`, never floating point.
- Human-facing text is Unicode and supports Malayalam natively.
- Deletion is restricted for records referenced by history; business availability uses `active` and validity windows.

## Implemented tables

| Table | Purpose | Important constraints |
|---|---|---|
| `companies` | Tenant root | Unique normalized name |
| `users` | Login identity and role | Unique lowercase email; nullable company only for platform super-admins |
| `clients` | Tenant CRM records | Unique `(company_id, phone)`; E.164 phone validation at API boundary |
| `products` | Structured product catalog | Tenant-scoped name index, active flag |
| `services` | Structured service catalog | Decimal starting price; quotation flag |
| `prices` | Authoritative price facts | Exactly one product/service target; validity range check |
| `offers` | Time-bounded structured offers | Optional product/service target; price and validity checks |
| `faqs` | Multilingual answers | Tenant/category/language indexes |
| `knowledge_items` | Manual company facts | Category, priority, validity, active state |
| `ai_agents` | AI assistant configurations | Tenant-scoped name index, languages, voice label, tone, prompts, active state |
| `documents` | Private uploaded knowledge files and processing state | Unique tenant content hash; uploader, extraction, embedding, and failure metadata |
| `document_chunks` | Searchable extracted text | Tenant/document scope, ordered chunk index, optional `vector(1024)` embedding, HNSW cosine index |
| `knowledge_conflicts` | Structured-vs-secondary mismatches | Unique source pair; open/resolved/ignored workflow |
| `knowledge_test_runs` | Retrieval diagnostics and source evidence | Tenant/actor/query, latency, mode, tools, sources, and conflicts |
| `audit_logs` | Security and mutation evidence | Tenant/actor/action/resource metadata |

Database checks enforce non-negative money, coherent validity ranges, and valid price targets. Application queries additionally enforce tenant, active, and current-time predicates.

## Later-phase tables

Knowledge health findings are computed from current records rather than stored as potentially stale rows. Phases 4–7 add calls, messages, reports, follow-ups, requirements, callback requests, cost usage, and provider events.

## Tenant isolation

Every repository/service function takes an explicit `company_id`; route handlers obtain it only from the authenticated tenant dependency. Cross-tenant entity IDs return `404`, avoiding record-existence disclosure. PostgreSQL row-level security is a defense-in-depth milestone before production because it requires transaction-scoped tenant settings compatible with pooled connections, migrations, workers, and super-admin operations.
