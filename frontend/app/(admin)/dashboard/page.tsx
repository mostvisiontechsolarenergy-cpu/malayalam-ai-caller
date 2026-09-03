"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { StatusBadge, formatDate } from "@/components/resource-page";
import { useSession } from "@/components/admin-shell";
import { apiRequest, type ApiRecord } from "@/lib/api";

type DashboardSummary = {
  clients_total: number;
  lead_counts: Record<string, number>;
  products_total: number;
  products_active: number;
  services_total: number;
  services_active: number;
  current_prices: number;
  active_offers: number;
  active_faqs: number;
  active_knowledge_items: number;
  active_ai_agents: number;
  call_metrics_available: boolean;
};

const leadTones: Record<string, "success" | "warning" | "danger" | "neutral" | "info"> = {
  HOT: "danger",
  WARM: "warning",
  COLD: "info",
  CONVERTED: "success",
  NOT_INTERESTED: "neutral",
  NEW: "info",
  FOLLOW_UP: "warning",
};

const platformModules = [
  { href: "/digital-analysis", label: "Digital Analysis", detail: "Company-wide intelligence", mark: "A" },
  { href: "/clients", label: "Clients", detail: "CRM and customer records", mark: "C" },
  { href: "/projects", label: "Projects", detail: "Delivery and assignments", mark: "P" },
  { href: "/sales-pipeline", label: "Sales Pipeline", detail: "Enquiry to conversion", mark: "S" },
  { href: "/maya-ai", label: "Maya AI", detail: "Calling and AI agents", mark: "M" },
  { href: "/proposal-connect", label: "Proposal Connect", detail: "Requirements to proposal", mark: "P" },
  { href: "/accounting", label: "Accounting", detail: "Company finance control", mark: "A" },
  { href: "/office-management", label: "Office Management", detail: "People and office operations", mark: "O" },
  { href: "/company-assets", label: "Company Assets", detail: "Asset lifecycle and custody", mark: "C" },
  { href: "/investments", label: "Investments", detail: "Capital and returns", mark: "I" },
  { href: "/media-library", label: "Media Library", detail: "Creative files and approvals", mark: "L" },
  { href: "/knowledge", label: "Company Knowledge", detail: "Approved AI information", mark: "K" },
];

export default function DashboardPage() {
  const session = useSession();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [clients, setClients] = useState<ApiRecord[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      apiRequest<DashboardSummary>("backend/dashboard/summary"),
      apiRequest<ApiRecord[]>("backend/clients?limit=5"),
    ])
      .then(([summaryData, clientData]) => {
        setSummary(summaryData);
        setClients(clientData);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load dashboard"));
  }, []);

  const leadTotal = summary
    ? Object.values(summary.lead_counts).reduce((total, count) => total + count, 0)
    : 0;
  const metricCards = summary
    ? [
        { label: "Clients", value: summary.clients_total, detail: `${summary.lead_counts.HOT ?? 0} hot leads`, mark: "C" },
        { label: "Active catalog", value: summary.products_active + summary.services_active, detail: `${summary.products_active} products · ${summary.services_active} services`, mark: "P" },
        { label: "Current prices", value: summary.current_prices, detail: "Authoritative price records", mark: "₹" },
        { label: "Active offers", value: summary.active_offers, detail: "Valid today", mark: "%" },
        { label: "Knowledge", value: summary.active_knowledge_items + summary.active_faqs, detail: `${summary.active_faqs} active FAQs`, mark: "K" },
        { label: "AI agents", value: summary.active_ai_agents, detail: "Configured assistants", mark: "A" },
      ]
    : [];

  return (
    <>
      <div className="page-heading dashboard-heading">
        <div>
          <span className="eyebrow">Dcreation Digitalization Platform</span>
          <h1>Good day, Admin</h1>
          <p>Manage clients, delivery, sales, Maya AI, proposals, finance, office operations, assets, investments, and media from one company workspace.</p>
        </div>
        {session.user.role !== "STAFF" ? (
          <div className="dashboard-actions">
            <Link href="/proposal-connect" className="primary-button">+ Create Proposal</Link>
            <Link href="/clients" className="secondary-button">+ Add client</Link>
          </div>
        ) : null}
      </div>

      {error ? <div className="form-error page-alert">{error}</div> : null}
      <section className="platform-launch-grid" aria-label="Platform modules">
        {platformModules.map((module) => (
          <Link className="platform-launch-card" href={module.href} key={module.href}>
            <span className="platform-launch-mark">{module.mark}</span>
            <span>
              <strong>{module.label}</strong>
              <small>{module.detail}</small>
            </span>
            <b>→</b>
          </Link>
        ))}
      </section>
      <section className="metric-grid">
        {summary ? metricCards.map((metric) => (
          <article className="metric-card" key={metric.label}>
            <div className="metric-mark">{metric.mark}</div>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.detail}</small>
          </article>
        )) : Array.from({ length: 6 }).map((_, index) => <div className="metric-card metric-skeleton" key={index} />)}
      </section>

      <section className="dashboard-grid">
        <article className="panel lead-panel">
          <div className="panel-heading">
            <div><span className="eyebrow">CRM health</span><h2>Lead funnel</h2></div>
            <span className="panel-count">{leadTotal} total</span>
          </div>
          {summary && leadTotal > 0 ? (
            <div className="funnel-list">
              {Object.entries(summary.lead_counts).map(([status, count]) => (
                <div className="funnel-row" key={status}>
                  <div><span>{status.replaceAll("_", " ")}</span><strong>{count}</strong></div>
                  <div className="funnel-track"><span style={{ width: `${Math.max((count / leadTotal) * 100, count ? 4 : 0)}%` }} /></div>
                </div>
              ))}
            </div>
          ) : (
            <div className="compact-empty"><div className="empty-mark">C</div><h3>Your funnel starts with a client</h3><p>Add clients and assign lead status to see real distribution here.</p><Link href="/clients">Open client CRM →</Link></div>
          )}
        </article>

        <article className="panel readiness-panel">
          <div className="panel-heading"><div><span className="eyebrow">Readiness</span><h2>Knowledge coverage</h2></div></div>
          {summary ? (
            <div className="readiness-list">
              {[
                ["Products & services", summary.products_active + summary.services_active, "/products"],
                ["Current prices", summary.current_prices, "/pricing"],
                ["Offers", summary.active_offers, "/offers"],
                ["FAQs & knowledge", summary.active_faqs + summary.active_knowledge_items, "/knowledge"],
                ["AI agents", summary.active_ai_agents, "/agents"],
              ].map(([label, count, href]) => (
                <Link href={String(href)} className="readiness-row" key={String(label)}>
                  <span className={Number(count) > 0 ? "check complete" : "check"}>{Number(count) > 0 ? "✓" : "·"}</span>
                  <span><strong>{label}</strong><small>{Number(count) > 0 ? `${count} configured` : "Needs setup"}</small></span>
                  <b>→</b>
                </Link>
              ))}
            </div>
          ) : null}
        </article>
      </section>

      <section className="dashboard-grid lower-grid">
        <article className="panel recent-panel">
          <div className="panel-heading"><div><span className="eyebrow">Latest CRM activity</span><h2>Recent clients</h2></div><Link href="/clients">View all</Link></div>
          {clients.length ? (
            <div className="recent-list">
              {clients.map((client) => (
                <div className="recent-row" key={client.id}>
                  <div className="client-avatar">{String(client.name ?? "C").slice(0, 1).toUpperCase()}</div>
                  <div><strong>{String(client.name)}</strong><span>{String(client.business_name ?? client.phone ?? "")}</span></div>
                  <StatusBadge tone={leadTones[String(client.lead_status)] ?? "neutral"}>{String(client.lead_status).replaceAll("_", " ")}</StatusBadge>
                  <time>{formatDate(client.created_at)}</time>
                </div>
              ))}
            </div>
          ) : <div className="compact-empty horizontal"><div className="empty-mark">C</div><div><h3>No client activity yet</h3><p>Newly added clients will appear here.</p></div></div>}
        </article>

        <article className="panel call-panel">
          <span className="phase-chip">Maya AI · Calling Assistant</span>
          <h2>Maya calling is connected to the wider platform</h2>
          <p>Run consented Malayalam customer conversations and move the resulting requirements into CRM, sales, proposals, and projects.</p>
          <div className="call-placeholder"><span /><span /><span /><span /><span /></div>
          <Link href="/phone-calls">Open Calling Assistant →</Link>
        </article>
      </section>
    </>
  );
}
