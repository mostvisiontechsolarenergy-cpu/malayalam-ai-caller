# Knowledge Base and RAG Architecture

## Authority order

1. Current structured pricing
2. Active structured offers
3. Active product/service records
4. Active FAQs
5. Active manual company knowledge
6. Tenant-filtered document chunks
7. General conversational reasoning (never allowed to create business facts)

The Phase 3 `KnowledgeService` implements this authority order in one tenant-scoped hybrid retrieval path. Semantic similarity can improve document recall but cannot move a document above structured prices or current offers.

## Document ingestion (Phase 3)

```text
upload -> extension/size/hash validation -> private persistent storage
       -> extraction -> Unicode cleanup -> section-aware chunking
       -> embeddings -> pgvector chunks -> READY
```

Supported formats are PDF, DOCX, TXT, CSV, and XLSX, with a configurable 15 MB default limit and duplicate-content protection per tenant. Processing runs after the upload response and records `UPLOADING`, `PROCESSING`, `READY`, or `FAILED`; embedding state is tracked separately. Each object and chunk carries `company_id`. Raw files use a dedicated Docker volume, while extracted content and embeddings are stored in PostgreSQL.

When `OPENAI_API_KEY` is absent, ingestion finishes as `READY` with embedding state `SKIPPED_NO_KEY`; lexical hybrid retrieval remains active. When configured, the service requests 1,024-dimensional `text-embedding-3-small` vectors in batches and stores them in a pgvector column with an HNSW cosine index. Production code never fabricates embeddings.

## Retrieval

Retrieval tokenizes the customer question, searches current structured prices/offers/catalog/FAQs/manual knowledge, and then searches tenant-owned ready document chunks. If embeddings are configured on PostgreSQL, the document stage uses cosine distance; otherwise it uses lexical matching. Results include source type, source ID, title, content, confidence, priority, score, authority flag, and page/section metadata.

## Conflict handling

Structured records win deterministically. The health engine extracts INR/rupee price-like statements from documents and manual knowledge for comparison only. A mismatch creates a persistent conflict and admin health finding; it never changes the selected price. Resolved conflicts reopen if the same mismatch returns. Expired records are filtered before ranking and never reach the model context.

## Anti-hallucination contract

Tools return either a typed fact with source metadata or `found: false`. For a missing critical fact, the agent says the exact detail is unavailable and may request a human callback. The model is never asked to estimate a price, offer, warranty, delivery time, availability, policy, feature, service, or location.

## Knowledge test diagnostics

The implemented test page shows a deterministic grounded answer preview, ordered retrieval candidates, selected source IDs, called retrieval tools, confidence, latency, search mode, and conflicts. Runs are stored for diagnostics. It deliberately does not generate an LLM conversation; Phase 4 will invoke this same retrieval layer from text and voice orchestration.
