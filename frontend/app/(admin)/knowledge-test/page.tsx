"use client";

import { useState } from "react";

import { StatusBadge } from "@/components/resource-page";
import { apiRequest } from "@/lib/api";

type Source = { source_type: string; source_id: string; title: string; content: string; confidence: string; authoritative: boolean; metadata: Record<string, unknown> };
type Result = { answer_preview: string; retrieved_knowledge: Source[]; tools_called: string[]; retrieval_latency_ms: number; records_used: number; retrieval_mode: string; conflicts: { summary: string }[]; embedding_available: boolean };

export default function KnowledgeTestPage() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function run(event: React.FormEvent) {
    event.preventDefault(); if (!query.trim()) return;
    setLoading(true); setError("");
    try { setResult(await apiRequest<Result>("backend/knowledge/test", { method: "POST", body: JSON.stringify({ query, limit: 10 }) })); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Knowledge test failed."); }
    finally { setLoading(false); }
  }
  return <>
    <header className="page-heading"><div><span className="eyebrow">Phase 3 · Retrieval diagnostics</span><h1>AI Knowledge Test</h1><p>Ask a realistic customer question and inspect exactly which approved sources the future voice assistant would receive.</p></div></header>
    <div className="info-banner"><strong>Grounded preview only:</strong> this page tests retrieval, authority, source tracking, and latency. LLM-generated conversation begins in Phase 4.</div>
    <form className="knowledge-test-form panel" onSubmit={(event) => void run(event)}><label htmlFor="knowledge-query">Customer question</label><div><textarea id="knowledge-query" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Example: What is the price of our website development package?" maxLength={500}/><button className="primary-button" disabled={loading || !query.trim()}>{loading ? "Testing…" : "Run knowledge test"}</button></div></form>
    {error && <div className="form-error page-alert">{error}</div>}
    {result && <div className="test-result-grid"><section className="panel answer-panel"><span className="eyebrow">Grounded answer preview</span><h2>{result.answer_preview}</h2><div className="diagnostic-strip"><span><strong>{result.retrieval_latency_ms} ms</strong> retrieval</span><span><strong>{result.records_used}</strong> sources</span><span><strong>Secure</strong> search</span></div>{result.conflicts.length > 0 && <div className="form-error">{result.conflicts.map((item) => item.summary).join(" ")}</div>}<div className="tool-list"><span>Knowledge checks</span>{result.tools_called.length ? <strong>{result.tools_called.length} completed</strong> : <em>No approved source matched</em>}</div></section>
    <section className="panel source-panel"><div className="panel-title"><div><span className="eyebrow">Source trace</span><h2>Retrieved knowledge</h2></div></div>{result.retrieved_knowledge.length === 0 ? <div className="compact-empty"><h3>No grounded source found</h3><p>Add manual knowledge, catalog data, FAQs, or documents.</p></div> : <div className="source-list">{result.retrieved_knowledge.map((source, index) => <article className="source-card" key={source.source_id}><div><span>#{index + 1} · {source.source_type.replaceAll("_", " ")}</span><StatusBadge tone={source.authoritative ? "success" : "info"}>{source.confidence}</StatusBadge></div><h3>{source.title}</h3><p>{source.content}</p></article>)}</div>}</section></div>}
  </>;
}
