"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { StatusBadge } from "@/components/resource-page";
import { useSession } from "@/components/admin-shell";
import { apiRequest } from "@/lib/api";

type Finding = { code: string; title: string; detail: string; severity: string; count: number; action_href: string };
type Health = { score: number; grade: string; findings: Finding[]; open_conflicts: number; ready_documents: number; searchable_chunks: number; embedding_available: boolean; checked_at: string };
type Conflict = { id: string; summary: string; authoritative_value: string; conflicting_value: string; status: string };

export default function KnowledgeHealthPage() {
  const { user } = useSession();
  const [health, setHealth] = useState<Health | null>(null);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(async () => {
    try {
      const [healthResult, conflictResult] = await Promise.all([
        apiRequest<Health>("backend/knowledge/health"),
        apiRequest<Conflict[]>("backend/knowledge/conflicts"),
      ]);
      setHealth(healthResult); setConflicts(conflictResult); setError("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Health check failed."); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function refresh() {
    setRefreshing(true);
    try { await apiRequest("backend/knowledge/conflicts/refresh", { method: "POST" }); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Refresh failed."); }
    finally { setRefreshing(false); }
  }

  async function resolve(id: string) {
    await apiRequest(`backend/knowledge/conflicts/${id}`, { method: "PATCH", body: JSON.stringify({ status: "RESOLVED" }) });
    await load();
  }

  return <>
    <header className="page-heading"><div><span className="eyebrow">Phase 3 · Knowledge governance</span><h1>Knowledge Health</h1><p>Find gaps, stale records, document failures, and conflicting facts before the assistant uses them.</p></div>{user.role !== "STAFF" && <button className="secondary-button" disabled={refreshing} onClick={() => void refresh()}>{refreshing ? "Checking…" : "Refresh conflicts"}</button>}</header>
    {error && <div className="form-error page-alert">{error}</div>}
    {!health ? <div className="table-state">Running knowledge checks…</div> : <>
      <section className="health-overview panel"><div className="score-ring" style={{ "--score": `${health.score * 3.6}deg` } as React.CSSProperties}><div><strong>{health.score}</strong><span>/ 100</span></div></div><div><span className="eyebrow">Current grade</span><h2>{health.grade}</h2><p>{health.findings.length ? `${health.findings.length} issue groups need review.` : "No knowledge quality issues were detected."}</p></div><div className="health-stat"><strong>{health.ready_documents}</strong><span>Ready documents</span></div><div className="health-stat"><strong>{health.searchable_chunks}</strong><span>Searchable chunks</span></div><div className="health-stat"><strong>{health.open_conflicts}</strong><span>Open conflicts</span></div></section>
      <div className="knowledge-grid"><section className="panel health-panel"><div className="panel-title"><div><span className="eyebrow">Quality checks</span><h2>Findings</h2></div></div>{health.findings.length === 0 ? <div className="compact-empty"><h3>Knowledge looks healthy</h3><p>Run this check after every major catalog or document update.</p></div> : <div className="finding-list">{health.findings.map((item) => <Link href={item.action_href} className="finding-row" key={item.code}><StatusBadge tone={item.severity === "critical" || item.severity === "high" ? "danger" : item.severity === "medium" ? "warning" : "info"}>{item.severity}</StatusBadge><div><strong>{item.title}</strong><span>{item.detail}</span></div><b>Review →</b></Link>)}</div>}</section>
      <section className="panel health-panel"><div className="panel-title"><div><span className="eyebrow">Authority rules</span><h2>Conflicts</h2></div></div>{conflicts.filter((item) => item.status === "OPEN").length === 0 ? <div className="compact-empty"><h3>No open conflicts</h3><p>Structured prices and offers remain authoritative.</p></div> : <div className="conflict-list">{conflicts.filter((item) => item.status === "OPEN").map((item) => <article className="conflict-card" key={item.id}><StatusBadge tone="danger">OPEN</StatusBadge><p>{item.summary}</p><div><span>Authoritative: {item.authoritative_value}</span><span>Conflicting: {item.conflicting_value}</span></div>{user.role !== "STAFF" && <button className="secondary-button" onClick={() => void resolve(item.id)}>Mark resolved</button>}</article>)}</div>}</section></div>
    </>}
  </>;
}
