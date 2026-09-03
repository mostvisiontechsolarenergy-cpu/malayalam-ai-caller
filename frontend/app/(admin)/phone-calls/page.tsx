"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useSession } from "@/components/admin-shell";
import { StatusBadge, formatDate } from "@/components/resource-page";
import { apiRequest, type ApiRecord } from "@/lib/api";

type ProviderStatus = {
  provider: string;
  configured: boolean;
  public_webhook_ready: boolean;
  ai_ready: boolean;
  ready: boolean;
  trial_mode: boolean;
  missing_fields: string[];
  detail: string;
};

type PhoneCall = {
  id: string;
  client_id: string;
  agent_id: string;
  conversation_id: string;
  provider: string;
  provider_call_sid: string | null;
  destination: string;
  status: string;
  duration_seconds: number | null;
  error_message: string | null;
  created_at: string;
};

type CallbackRequest = {
  id: string;
  client_id: string;
  agent_id: string;
  source_phone_call_id: string | null;
  phone_call_id: string | null;
  scheduled_for: string;
  timezone: string;
  customer_request_text: string;
  status: "SCHEDULED" | "PROCESSING" | "DISPATCHED" | "CANCELLED" | "FAILED";
  dispatch_attempts: number;
  dispatched_at: string | null;
  last_error: string | null;
};

type CallBatchItem = {
  id: string;
  sequence_number: number;
  phone: string;
  status: string;
  client_id: string | null;
  phone_call_id: string | null;
  error_message: string | null;
};

type CallBatch = {
  id: string;
  agent_id: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "CANCELLED";
  total_count: number;
  processed_count: number;
  successful_count: number;
  failed_count: number;
  skipped_count: number;
  cancelled_count: number;
  cancelled_at: string | null;
  last_error: string | null;
  created_at: string;
  items: CallBatchItem[];
};

type TranscriptMessage = {
  id: string;
  role: "USER" | "ASSISTANT" | "TOOL";
  text: string;
  created_at: string;
};

type MalayalamAnalysis = {
  summary_ml: string;
  customer_requirement_ml: string;
  services_interested_ml: string[];
  customer_questions_ml: string[];
  expected_budget_ml: string;
  objections_ml: string[];
  decisions_ml: string[];
  follow_up_action_ml: string;
  outcome_ml: string;
  lead_temperature: "HOT" | "WARM" | "COLD" | "UNKNOWN";
};

type MalayalamReport = {
  status: "NOT_GENERATED" | "PENDING" | "READY" | "FAILED" | "INSUFFICIENT_TRANSCRIPT";
  generated_at?: string;
  analysis: MalayalamAnalysis | null;
  error?: string;
};

type CallReportResponse = {
  call: PhoneCall;
  client: {
    name: string;
    phone: string;
    alternative_phone: string | null;
    business_name: string | null;
    email: string | null;
    location: string | null;
    preferred_language: string;
    lead_status: string;
  };
  report: {
    malayalam_report: MalayalamReport;
  };
  transcript: TranscriptMessage[];
};

function ReportList({ items }: { items: string[] }) {
  if (!items.length) return <p className="call-report-empty">വിവരം ലഭ്യമല്ല</p>;
  return <ul>{items.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>;
}

const terminalStatuses = new Set(["COMPLETED", "BUSY", "NO_ANSWER", "FAILED", "CANCELLED"]);
const tones: Record<string, "success" | "warning" | "danger" | "neutral" | "info"> = {
  QUEUED: "neutral",
  INITIATED: "info",
  RINGING: "warning",
  IN_PROGRESS: "success",
  COMPLETED: "success",
  BUSY: "warning",
  NO_ANSWER: "warning",
  FAILED: "danger",
  CANCELLED: "neutral",
  SCHEDULED: "info",
  PROCESSING: "warning",
  DISPATCHED: "success",
  RUNNING: "info",
  SKIPPED: "neutral",
};

function formatIndiaTime(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function PhoneCallsPage() {
  const session = useSession();
  const canCall = session.user.role !== "STAFF";
  const [provider, setProvider] = useState<ProviderStatus | null>(null);
  const [calls, setCalls] = useState<PhoneCall[]>([]);
  const [callbacks, setCallbacks] = useState<CallbackRequest[]>([]);
  const [callBatches, setCallBatches] = useState<CallBatch[]>([]);
  const [clients, setClients] = useState<ApiRecord[]>([]);
  const [agents, setAgents] = useState<ApiRecord[]>([]);
  const [clientId, setClientId] = useState("");
  const [agentId, setAgentId] = useState("");
  const [quickAgentId, setQuickAgentId] = useState("");
  const [quickPhone, setQuickPhone] = useState("");
  const [batchAgentId, setBatchAgentId] = useState("");
  const [batchPhones, setBatchPhones] = useState("");
  const [batchConsentConfirmed, setBatchConsentConfirmed] = useState(false);
  const [batchCostConfirmed, setBatchCostConfirmed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [quickCalling, setQuickCalling] = useState(false);
  const [batchStarting, setBatchStarting] = useState(false);
  const [callReport, setCallReport] = useState<CallReportResponse | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const [providerData, callData, callbackData, batchData, clientData, agentData] = await Promise.all([
        apiRequest<ProviderStatus>("backend/telephony/provider-status"),
        apiRequest<PhoneCall[]>("backend/telephony/calls"),
        apiRequest<CallbackRequest[]>("backend/telephony/callbacks"),
        apiRequest<CallBatch[]>("backend/telephony/call-batches"),
        apiRequest<ApiRecord[]>("backend/clients?limit=100"),
        apiRequest<ApiRecord[]>("backend/ai-agents?limit=100"),
      ]);
      setProvider(providerData);
      setCalls(callData);
      setCallbacks(callbackData);
      setCallBatches(batchData);
      setClients(clientData);
      setAgents(agentData.filter((agent) => agent.active));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load phone calling");
    } finally {
      if (!quiet) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(true), 4000);
    return () => window.clearInterval(interval);
  }, [load]);

  const eligibleClients = useMemo(
    () =>
      clients.filter(
        (client) =>
          client.calling_allowed &&
          client.consent_status === "GRANTED" &&
          !client.opted_out,
      ),
    [clients],
  );
  const clientNames = useMemo(
    () => Object.fromEntries(clients.map((client) => [client.id, String(client.name)])),
    [clients],
  );
  const agentNames = useMemo(
    () => Object.fromEntries(agents.map((agent) => [agent.id, String(agent.name)])),
    [agents],
  );

  useEffect(() => {
    if (!clientId && eligibleClients[0]) setClientId(eligibleClients[0].id);
    if (!agentId && agents[0]) setAgentId(agents[0].id);
    if (!quickAgentId && agents.length) {
      const soorya = agents.find((agent) => String(agent.name).toLowerCase() === "soorya");
      setQuickAgentId(soorya?.id ?? agents[0].id);
    }
    if (!batchAgentId && agents.length) {
      const soorya = agents.find((agent) => String(agent.name).toLowerCase() === "soorya");
      setBatchAgentId(soorya?.id ?? agents[0].id);
    }
  }, [agentId, agents, batchAgentId, clientId, eligibleClients, quickAgentId]);

  const parsedBatchPhones = useMemo(
    () => Array.from(new Set(batchPhones.split(/[,;\n\r]+/).map((phone) => phone.trim()).filter(Boolean))),
    [batchPhones],
  );
  const activeBatch = useMemo(
    () => callBatches.find((batch) => batch.status === "QUEUED" || batch.status === "RUNNING"),
    [callBatches],
  );

  async function startCall() {
    if (!clientId || !agentId) return;
    setStarting(true);
    setError("");
    setSuccess("");
    try {
      const call = await apiRequest<PhoneCall>("backend/telephony/calls", {
        method: "POST",
        body: JSON.stringify({ client_id: clientId, agent_id: agentId }),
      });
      setSuccess(`Call queued to ${clientNames[call.client_id] ?? call.destination}.`);
      await load(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to start the call");
    } finally {
      setStarting(false);
    }
  }

  async function startQuickCall() {
    if (!quickPhone.trim() || !quickAgentId) return;
    setQuickCalling(true);
    setError("");
    setSuccess("");
    try {
      const call = await apiRequest<PhoneCall>("backend/telephony/calls/quick", {
        method: "POST",
        body: JSON.stringify({ phone: quickPhone, agent_id: quickAgentId }),
      });
      setQuickPhone("");
      setSuccess(
        `${agentNames[call.agent_id] ?? "Selected agent"} call queued to ${call.destination}.`,
      );
      await load(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to start the quick call");
    } finally {
      setQuickCalling(false);
    }
  }

  async function startCallBatch() {
    if (!batchAgentId || !parsedBatchPhones.length) return;
    setBatchStarting(true);
    setError("");
    setSuccess("");
    try {
      const batch = await apiRequest<CallBatch>("backend/telephony/call-batches", {
        method: "POST",
        body: JSON.stringify({
          agent_id: batchAgentId,
          phones: parsedBatchPhones,
          consent_confirmed: batchConsentConfirmed,
          cost_confirmed: batchCostConfirmed,
        }),
      });
      setBatchPhones("");
      setBatchConsentConfirmed(false);
      setBatchCostConfirmed(false);
      setSuccess(
        `Sequential queue started for ${batch.total_count} number${batch.total_count === 1 ? "" : "s"}.`,
      );
      await load(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to start sequential calls");
    } finally {
      setBatchStarting(false);
    }
  }

  async function cancelCallBatch(batchId: string) {
    setError("");
    setSuccess("");
    try {
      await apiRequest(`backend/telephony/call-batches/${batchId}/cancel`, { method: "POST" });
      setSuccess("Queue stopped. The current connected call may finish; no next number will be called.");
      await load(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to stop the call queue");
    }
  }

  async function endCall(callId: string) {
    setError("");
    try {
      await apiRequest(`backend/telephony/calls/${callId}/end`, { method: "POST" });
      await load(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to end the call");
    }
  }

  async function cancelCallback(callbackId: string) {
    setError("");
    setSuccess("");
    try {
      await apiRequest(`backend/telephony/callbacks/${callbackId}/cancel`, { method: "POST" });
      setSuccess("Automatic callback cancelled.");
      await load(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to cancel the callback");
    }
  }

  async function viewReport(callId: string) {
    setReportLoading(true);
    setError("");
    try {
      const report = await apiRequest<CallReportResponse>(
        `backend/telephony/calls/${callId}/report`,
      );
      setCallReport(report);
      window.setTimeout(
        () => document.getElementById("malayalam-call-report")?.scrollIntoView({ behavior: "smooth" }),
        0,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load the call report");
    } finally {
      setReportLoading(false);
    }
  }

  async function generateReport() {
    if (!callReport) return;
    setReportLoading(true);
    setError("");
    try {
      const report = await apiRequest<CallReportResponse>(
        `backend/telephony/calls/${callReport.call.id}/report`,
        { method: "POST" },
      );
      setCallReport(report);
      setSuccess("Malayalam call report updated.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to generate the call report");
    } finally {
      setReportLoading(false);
    }
  }

  const malayalamReport = callReport?.report.malayalam_report;
  const analysis = malayalamReport?.analysis;

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Secure calling workspace</span>
          <h1>AI Phone Calls</h1>
          <p>Call a consented client with the selected grounded Dcreation AI agent.</p>
        </div>
        <StatusBadge tone={provider?.ready ? "success" : "warning"}>
          {provider?.ready ? "READY" : "SETUP REQUIRED"}
        </StatusBadge>
      </div>

      {error ? <div className="form-error page-alert">{error}</div> : null}
      {success ? <div className="success-toast">{success}</div> : null}

      <section className="panel quick-call-panel">
        <div>
          <span className="eyebrow">Immediate outbound call</span>
          <h2>Quick Call</h2>
          <p>Choose Maya or Soorya, enter the customer number, and call immediately.</p>
        </div>
        <div className="quick-call-control">
          <select
            aria-label="Quick Call AI agent"
            onChange={(event) => setQuickAgentId(event.target.value)}
            value={quickAgentId}
          >
            <option value="">Select AI agent</option>
            {agents.map((agent) => (
              <option key={agent.id} value={agent.id}>{String(agent.name)}</option>
            ))}
          </select>
          <input
            aria-label="Quick Call customer phone number"
            autoComplete="tel"
            inputMode="tel"
            onChange={(event) => setQuickPhone(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void startQuickCall();
            }}
            placeholder="9876543210 or +919876543210"
            type="tel"
            value={quickPhone}
          />
          <button
            className="primary-button"
            disabled={
              !canCall ||
              !provider?.ready ||
              !quickAgentId ||
              !quickPhone.trim() ||
              quickCalling
            }
            onClick={startQuickCall}
          >
            {quickCalling ? "Calling…" : "Call now"}
          </button>
        </div>
        <small>
          Use this only when the customer has permitted the call and is not opted out. Selecting
          Call now records the operator-confirmed contact source; the chosen agent controls the
          Malayalam workflow.
        </small>
      </section>

      <section className="panel batch-call-panel">
        <div className="batch-call-heading">
          <div>
            <span className="eyebrow">Sequential multiple-number calling</span>
            <h2>Quick Call List</h2>
            <p>
              Paste up to 100 permitted customer numbers, separated by commas or new lines.
              The next number is called only after the current call finishes.
            </p>
          </div>
          {activeBatch ? (
            <StatusBadge tone={tones[activeBatch.status] ?? "neutral"}>{activeBatch.status}</StatusBadge>
          ) : null}
        </div>

        <div className="batch-call-form">
          <label className="field-label">
            AI agent for every number
            <select value={batchAgentId} onChange={(event) => setBatchAgentId(event.target.value)}>
              <option value="">Select AI agent</option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>{String(agent.name)}</option>
              ))}
            </select>
          </label>
          <label className="field-label batch-phone-field">
            Customer phone numbers
            <textarea
              aria-label="Multiple customer phone numbers"
              disabled={Boolean(activeBatch)}
              onChange={(event) => setBatchPhones(event.target.value)}
              placeholder={"9876543210, 9876543211, 9876543212\nOr paste one number per line"}
              rows={5}
              value={batchPhones}
            />
            <small className={parsedBatchPhones.length > 100 ? "batch-count-danger" : undefined}>
              {parsedBatchPhones.length} unique number{parsedBatchPhones.length === 1 ? "" : "s"} entered
              {parsedBatchPhones.length > 100 ? " - maximum is 100" : " - maximum 100"}.
            </small>
          </label>
          <div className="batch-confirmations">
            <label>
              <input
                checked={batchConsentConfirmed}
                disabled={Boolean(activeBatch)}
                onChange={(event) => setBatchConsentConfirmed(event.target.checked)}
                type="checkbox"
              />
              Every number has permitted this call and is not from an unapproved purchased list.
            </label>
            <label>
              <input
                checked={batchCostConfirmed}
                disabled={Boolean(activeBatch)}
                onChange={(event) => setBatchCostConfirmed(event.target.checked)}
                type="checkbox"
              />
              I understand each attempted carrier call can use the calling balance.
            </label>
          </div>
          <button
            className="primary-button batch-start-button"
            disabled={
              !canCall ||
              !provider?.ready ||
              !batchAgentId ||
              !parsedBatchPhones.length ||
              parsedBatchPhones.length > 100 ||
              !batchConsentConfirmed ||
              !batchCostConfirmed ||
              Boolean(activeBatch) ||
              batchStarting
            }
            onClick={startCallBatch}
          >
            {batchStarting ? "Starting queue..." : `Start ${parsedBatchPhones.length || ""} sequential calls`}
          </button>
        </div>

        {activeBatch ? (
          <div className="batch-progress-card">
            <div className="batch-progress-heading">
              <div>
                <strong>{agentNames[activeBatch.agent_id] ?? "Selected agent"} call queue</strong>
                <span>{activeBatch.processed_count} of {activeBatch.total_count} processed</span>
              </div>
              <button onClick={() => cancelCallBatch(activeBatch.id)}>Stop after current call</button>
            </div>
            <progress max={activeBatch.total_count} value={activeBatch.processed_count} />
            <div className="batch-stat-grid">
              <span><strong>{activeBatch.successful_count}</strong> Completed</span>
              <span><strong>{activeBatch.failed_count}</strong> Unanswered/failed</span>
              <span><strong>{activeBatch.skipped_count}</strong> Opt-out skipped</span>
              <span><strong>{activeBatch.cancelled_count}</strong> Cancelled</span>
            </div>
            {activeBatch.items.find((item) => ["DISPATCHING", "IN_PROGRESS"].includes(item.status)) ? (
              <p>
                Current: <strong>{activeBatch.items.find((item) => ["DISPATCHING", "IN_PROGRESS"].includes(item.status))?.phone}</strong>
              </p>
            ) : null}
            {activeBatch.last_error ? <small className="call-error">{activeBatch.last_error}</small> : null}
          </div>
        ) : callBatches[0] ? (
          <div className="batch-progress-card batch-complete-card">
            <strong>Latest queue: {callBatches[0].status}</strong>
            <span>
              {callBatches[0].processed_count}/{callBatches[0].total_count} processed - {callBatches[0].successful_count} completed,
              {" "}{callBatches[0].failed_count} unanswered/failed, {callBatches[0].skipped_count} skipped.
            </span>
          </div>
        ) : null}
      </section>

      <section className="phone-call-grid">
        <article className="panel phone-call-panel">
          <div className="panel-heading">
            <div><span className="eyebrow">Outbound phone call</span><h2>Start a Malayalam call</h2></div>
          </div>
          <div className="phone-call-form">
            <label className="field-label">
              Client with call consent
              <select value={clientId} onChange={(event) => setClientId(event.target.value)}>
                <option value="">Select a client</option>
                {eligibleClients.map((client) => (
                  <option key={client.id} value={client.id}>
                    {String(client.name)} · {String(client.phone)}
                  </option>
                ))}
              </select>
              <small>Only GRANTED, calling-allowed, non-opted-out clients are shown.</small>
            </label>
            <label className="field-label">
              AI agent
              <select value={agentId} onChange={(event) => setAgentId(event.target.value)}>
                <option value="">Select an active agent</option>
                {agents.map((agent) => (
                  <option key={agent.id} value={agent.id}>{String(agent.name)}</option>
                ))}
              </select>
              <small>The selected agent controls the Malayalam voice, prompt, and knowledge tools.</small>
            </label>
            <button
              className="primary-button phone-call-button"
              disabled={!canCall || !provider?.ready || !clientId || !agentId || starting}
              onClick={startCall}
            >
              {starting ? "Starting call…" : "Call consented phone"}
            </button>
          </div>
          {!eligibleClients.length && !loading ? (
            <div className="info-banner phone-inline-note">
              No eligible client. Open <Link href="/clients">Clients</Link>, add the client number, set consent to GRANTED, and enable Calling allowed.
            </div>
          ) : null}
        </article>

        <article className="panel phone-readiness-panel">
          <div className="panel-heading">
            <div><span className="eyebrow">System readiness</span><h2>Calling connection</h2></div>
          </div>
          <div className="readiness-list">
            {[
              ["Calling account and number", provider?.configured],
              ["Secure public callback", provider?.public_webhook_ready],
              ["Malayalam voice engine", provider?.ai_ready],
            ].map(([label, ready]) => (
              <div className="readiness-row" key={String(label)}>
                <span className={ready ? "check complete" : "check"}>{ready ? "✓" : "·"}</span>
                <span><strong>{label}</strong><small>{ready ? "Ready" : "Needs setup"}</small></span>
              </div>
            ))}
          </div>
          <p className="phone-provider-detail">{provider?.detail ?? "Checking configuration…"}</p>
          {provider?.missing_fields.length ? (
            <div className="phone-missing-fields">
              {provider.missing_fields.map((field) => <code key={field}>{field}</code>)}
            </div>
          ) : null}
          <small className="muted">Carrier calling is pay-as-you-go. Keep sufficient balance and complete any required India KYC before calling.</small>
        </article>
      </section>

      <section className="data-card phone-history callback-history">
        <div className="table-toolbar">
          <div>
            <strong>Automatic callbacks</strong>
            <span>
              Maya asks for an exact time, confirms it, and calls automatically in India time.
              No manual approval is required.
            </span>
          </div>
        </div>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr><th>Client</th><th>Exact callback time</th><th>Status</th><th>Customer confirmation</th><th className="actions-column">Action</th></tr>
            </thead>
            <tbody>
              {callbacks.map((callback) => (
                <tr key={callback.id}>
                  <td className="primary-cell">
                    <strong>{clientNames[callback.client_id] ?? "Client"}</strong>
                    <span>{agentNames[callback.agent_id] ?? "Dcreation Maya"}</span>
                  </td>
                  <td className="primary-cell">
                    <strong>{formatIndiaTime(callback.scheduled_for)}</strong>
                    <span>Asia/Kolkata</span>
                  </td>
                  <td>
                    <StatusBadge tone={tones[callback.status] ?? "neutral"}>
                      {callback.status.replaceAll("_", " ")}
                    </StatusBadge>
                    {callback.last_error ? <small className="call-error">{callback.last_error}</small> : null}
                  </td>
                  <td>{callback.customer_request_text}</td>
                  <td className="row-actions">
                    {callback.status === "SCHEDULED" && canCall ? (
                      <button onClick={() => cancelCallback(callback.id)}>Cancel</button>
                    ) : null}
                    {callback.phone_call_id ? (
                      <button onClick={() => viewReport(callback.phone_call_id!)}>Open call</button>
                    ) : null}
                  </td>
                </tr>
              ))}
              {!loading && !callbacks.length ? (
                <tr><td colSpan={5}><div className="compact-empty"><h3>No automatic callbacks yet</h3><p>Confirmed callback requests from live calls will appear here.</p></div></td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="data-card phone-history">
        <div className="table-toolbar">
          <div><strong>Call history</strong><span>{calls.length} real call records · no simulated calls</span></div>
        </div>
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th>Client</th><th>Agent</th><th>Status</th><th>Duration</th><th>Started</th><th className="actions-column">Action</th></tr></thead>
            <tbody>
              {calls.map((call) => (
                <tr key={call.id}>
                  <td className="primary-cell"><strong>{clientNames[call.client_id] ?? call.destination}</strong><span>{call.destination}</span></td>
                  <td>{agentNames[call.agent_id] ?? "AI agent"}</td>
                  <td><StatusBadge tone={tones[call.status] ?? "neutral"}>{call.status.replaceAll("_", " ")}</StatusBadge>{call.error_message ? <small className="call-error">{call.error_message}</small> : null}</td>
                  <td>{call.duration_seconds == null ? "—" : `${call.duration_seconds}s`}</td>
                  <td>{formatDate(call.created_at)}</td>
                  <td className="row-actions">
                    {!terminalStatuses.has(call.status) && canCall ? <button onClick={() => endCall(call.id)}>End call</button> : null}
                    {terminalStatuses.has(call.status) ? <button onClick={() => viewReport(call.id)}>Malayalam report</button> : null}
                  </td>
                </tr>
              ))}
              {!loading && !calls.length ? <tr><td colSpan={6}><div className="compact-empty"><h3>No phone calls yet</h3><p>Your first customer call will appear here.</p></div></td></tr> : null}
            </tbody>
          </table>
        </div>
      </section>

      {callReport || reportLoading ? (
        <section className="panel call-report" id="malayalam-call-report" lang="ml">
          <div className="panel-heading call-report-heading">
            <div>
              <span className="eyebrow">Post-call intelligence</span>
              <h2>മലയാളം കോൾ റിപ്പോർട്ട്</h2>
              {callReport ? <p>{callReport.client.name} · {callReport.client.phone}</p> : null}
            </div>
            <div className="call-report-actions">
              {malayalamReport ? (
                <StatusBadge
                  tone={
                    malayalamReport.status === "READY" ? "success"
                      : malayalamReport.status === "FAILED" ? "danger"
                        : malayalamReport.status === "PENDING" ? "warning" : "neutral"
                  }
                >
                  {malayalamReport.status.replaceAll("_", " ")}
                </StatusBadge>
              ) : null}
              {callReport && canCall ? (
                <button disabled={reportLoading} onClick={generateReport}>
                  {reportLoading ? "തയ്യാറാക്കുന്നു…" : "റിപ്പോർട്ട് വീണ്ടും തയ്യാറാക്കുക"}
                </button>
              ) : null}
              <button onClick={() => setCallReport(null)}>അടയ്ക്കുക</button>
            </div>
          </div>

          {reportLoading && !callReport ? <div className="compact-empty"><p>റിപ്പോർട്ട് ലോഡ് ചെയ്യുന്നു…</p></div> : null}

          {callReport ? (
            <>
              <div className="call-client-grid">
                <div><span>ക്ലയന്റ് പേര്</span><strong>{callReport.client.name}</strong></div>
                <div><span>ഫോൺ</span><strong>{callReport.client.phone}</strong></div>
                <div><span>ബിസിനസ്</span><strong>{callReport.client.business_name || "വിവരം ലഭ്യമല്ല"}</strong></div>
                <div><span>സ്ഥലം</span><strong>{callReport.client.location || "വിവരം ലഭ്യമല്ല"}</strong></div>
                <div><span>ഇമെയിൽ</span><strong>{callReport.client.email || "വിവരം ലഭ്യമല്ല"}</strong></div>
                <div><span>CRM ലീഡ് സ്റ്റാറ്റസ്</span><strong>{callReport.client.lead_status.replaceAll("_", " ")}</strong></div>
              </div>

              {malayalamReport?.status === "READY" && analysis ? (
                <div className="call-report-grid">
                  <article className="call-report-card call-report-wide">
                    <span>കോൾ സംഗ്രഹം</span><p>{analysis.summary_ml}</p>
                  </article>
                  <article className="call-report-card">
                    <span>ഉപഭോക്താവിന്റെ ആവശ്യം</span><p>{analysis.customer_requirement_ml}</p>
                  </article>
                  <article className="call-report-card">
                    <span>പ്രതീക്ഷിക്കുന്ന ബജറ്റ്</span><p>{analysis.expected_budget_ml}</p>
                  </article>
                  <article className="call-report-card">
                    <span>താൽപര്യമുള്ള സേവനങ്ങൾ</span><ReportList items={analysis.services_interested_ml} />
                  </article>
                  <article className="call-report-card">
                    <span>ഉപഭോക്താവിന്റെ ചോദ്യങ്ങൾ</span><ReportList items={analysis.customer_questions_ml} />
                  </article>
                  <article className="call-report-card">
                    <span>എതിർപ്പുകൾ / സംശയങ്ങൾ</span><ReportList items={analysis.objections_ml} />
                  </article>
                  <article className="call-report-card">
                    <span>കോളിലെ തീരുമാനങ്ങൾ</span><ReportList items={analysis.decisions_ml} />
                  </article>
                  <article className="call-report-card">
                    <span>അടുത്ത ഫോളോ-അപ്പ്</span><p>{analysis.follow_up_action_ml}</p>
                  </article>
                  <article className="call-report-card">
                    <span>കോളിന്റെ ഫലം</span><p>{analysis.outcome_ml}</p><strong className="lead-temperature">{analysis.lead_temperature} LEAD</strong>
                  </article>
                </div>
              ) : (
                <div className="info-banner call-report-state">
                  {malayalamReport?.status === "INSUFFICIENT_TRANSCRIPT"
                    ? "ഉപഭോക്താവിന്റെ സംഭാഷണം ലഭ്യമല്ല. റിപ്പോർട്ട് തയ്യാറാക്കാൻ മതിയായ ട്രാൻസ്ക്രിപ്റ്റ് ഇല്ല."
                    : malayalamReport?.status === "FAILED"
                      ? "റിപ്പോർട്ട് തയ്യാറാക്കാൻ കഴിഞ്ഞില്ല. വീണ്ടും തയ്യാറാക്കുക ബട്ടൺ അമർത്തുക."
                      : malayalamReport?.status === "PENDING"
                        ? "മലയാളം റിപ്പോർട്ട് തയ്യാറാക്കിക്കൊണ്ടിരിക്കുന്നു."
                        : "ഈ പഴയ കോളിന്റെ റിപ്പോർട്ട് തയ്യാറാക്കാൻ മുകളിലെ ബട്ടൺ അമർത്തുക."}
                </div>
              )}

              <div className="call-transcript">
                <div className="call-transcript-heading">
                  <div><span className="eyebrow">Full transcript</span><h3>പൂർണ്ണ സംഭാഷണം</h3></div>
                  <span>{callReport.transcript.length} സന്ദേശങ്ങൾ</span>
                </div>
                <div className="call-transcript-list">
                  {callReport.transcript.map((message) => (
                    <article className={`call-transcript-message ${message.role.toLowerCase()}`} key={message.id}>
                      <strong>{message.role === "USER" ? "ഉപഭോക്താവ്" : message.role === "ASSISTANT" ? "AI സഹായി" : "ടൂൾ"}</strong>
                      <p>{message.text}</p>
                      <time>{formatDate(message.created_at)}</time>
                    </article>
                  ))}
                  {!callReport.transcript.length ? <p className="call-report-empty">ട്രാൻസ്ക്രിപ്റ്റ് ലഭ്യമല്ല</p> : null}
                </div>
              </div>
            </>
          ) : null}
        </section>
      ) : null}
    </>
  );
}
