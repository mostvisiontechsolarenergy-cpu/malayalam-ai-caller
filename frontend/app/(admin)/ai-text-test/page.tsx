"use client";

import { useEffect, useRef, useState } from "react";

import { StatusBadge } from "@/components/resource-page";
import { apiRequest } from "@/lib/api";
import type {
  Agent,
  Client,
  Conversation,
  ProviderStatus,
  SessionReport,
  ToolEvent,
  TranscriptMessage,
} from "@/lib/ai-types";
import { activeVoice } from "@/lib/ai-types";

type TurnResponse = {
  user_message: TranscriptMessage;
  assistant_message: TranscriptMessage;
  tool_events: ToolEvent[];
};

export default function AITextTestPage() {
  const [provider, setProvider] = useState<ProviderStatus | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [agentId, setAgentId] = useState("");
  const [clientId, setClientId] = useState("");
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [tools, setTools] = useState<ToolEvent[]>([]);
  const [report, setReport] = useState<SessionReport | null>(null);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const transcriptEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void Promise.all([
      apiRequest<ProviderStatus>("backend/ai/provider-status"),
      apiRequest<Agent[]>("backend/ai-agents?active=true"),
      apiRequest<Client[]>("backend/clients"),
    ])
      .then(([providerResult, agentResult, clientResult]) => {
        setProvider(providerResult);
        setAgents(agentResult.filter((item) => item.active));
        setClients(clientResult);
        setAgentId(agentResult.find((item) => item.active)?.id ?? "");
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Could not load the test."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function ensureConversation() {
    if (conversation) return conversation;
    if (!agentId) throw new Error("Create and select an active AI agent first.");
    const created = await apiRequest<Conversation>("backend/ai/conversations", {
      method: "POST",
      body: JSON.stringify({
        agent_id: agentId,
        client_id: clientId || null,
        channel: "TEXT_TEST",
      }),
    });
    setConversation(created);
    return created;
  }

  async function send(event: React.FormEvent) {
    event.preventDefault();
    const message = text.trim();
    if (!message || sending || !provider?.configured) return;
    setSending(true);
    setError("");
    try {
      const current = await ensureConversation();
      const result = await apiRequest<TurnResponse>(
        `backend/ai/conversations/${current.id}/text-turn`,
        { method: "POST", body: JSON.stringify({ text: message }) },
      );
      setMessages((items) => [...items, result.user_message, result.assistant_message]);
      setTools((items) => [...items, ...result.tool_events]);
      setText("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The AI reply failed.");
    } finally {
      setSending(false);
    }
  }

  async function endTest() {
    if (!conversation) return;
    setError("");
    try {
      const result = await apiRequest<SessionReport>(
        `backend/ai/conversations/${conversation.id}/end`,
        { method: "POST" },
      );
      setReport(result);
      setConversation((item) => (item ? { ...item, status: "COMPLETED" } : item));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not finish the test.");
    }
  }

  const disabled = loading || !provider?.configured || !agentId || conversation?.status === "COMPLETED";
  return (
    <>
      <header className="page-heading">
        <div>
          <span className="eyebrow">Phase 4 · Grounded conversation</span>
          <h1>Malayalam Text Test</h1>
          <p>Test the same agent instructions and approved knowledge used in customer conversations.</p>
        </div>
        {provider && (
          <StatusBadge tone={provider.configured ? "success" : "warning"}>
            {provider.configured ? "AI READY" : "AI SETUP REQUIRED"}
          </StatusBadge>
        )}
      </header>

      <div className={`info-banner ${provider?.configured ? "" : "warning-banner"}`}>
        <strong>{provider?.configured ? "Grounded mode:" : "Free mode remains active:"}</strong>{" "}
        {provider?.detail ?? "Checking AI configuration…"}
      </div>

      <div className="playground-grid">
        <section className="panel playground-controls">
          <div className="panel-title">
            <div><span className="eyebrow">Test setup</span><h2>Conversation context</h2></div>
          </div>
          <label className="field-label">AI agent
            <select value={agentId} onChange={(event) => setAgentId(event.target.value)} disabled={Boolean(conversation)}>
              <option value="">Select an agent</option>
              {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name} · {activeVoice(agent.voice, provider?.connection_mode)}</option>)}
            </select>
          </label>
          <label className="field-label">Client (optional)
            <select value={clientId} onChange={(event) => setClientId(event.target.value)} disabled={Boolean(conversation)}>
              <option value="">No client selected</option>
              {clients.map((client) => <option key={client.id} value={client.id}>{client.name} · {client.phone}</option>)}
            </select>
          </label>
          <div className="model-note"><span>Response engine</span><strong>{provider?.configured ? "Secure" : "Unavailable"}</strong></div>
          <div className="guardrail-list">
            <span>✓ Approved knowledge access</span>
            <span>✓ Price records are authoritative</span>
            <span>✓ Missing facts trigger a safe handoff</span>
            <span>✓ CRM-changing actions are disabled</span>
          </div>
          {conversation?.status === "ACTIVE" && <button className="secondary-button" onClick={() => void endTest()}>End test & generate report</button>}
        </section>

        <section className="panel transcript-panel">
          <div className="panel-title transcript-heading">
            <div><span className="eyebrow">Live transcript</span><h2>Malayalam conversation</h2></div>
            {conversation && <StatusBadge tone={conversation.status === "ACTIVE" ? "success" : "neutral"}>{conversation.status}</StatusBadge>}
          </div>
          <div className="transcript-stream" aria-live="polite">
            {messages.length === 0 ? (
              <div className="compact-empty"><h3>Ready for a Malayalam question</h3><p>Try asking about a product, service, price, offer, FAQ, or uploaded document.</p></div>
            ) : messages.map((message, index) => (
              <article className={`transcript-bubble ${message.role.toLowerCase()}`} key={message.id ?? index}>
                <span>{message.role === "USER" ? "You" : "AI assistant"}</span>
                <p lang="ml">{message.text}</p>
                {message.source_json && message.source_json.length > 0 && <small>{message.source_json.length} approved source{message.source_json.length === 1 ? "" : "s"}</small>}
              </article>
            ))}
            {sending && <div className="assistant-thinking"><span /><span /><span /></div>}
            <div ref={transcriptEnd} />
          </div>
          <form className="chat-composer" onSubmit={(event) => void send(event)}>
            <textarea lang="ml" value={text} onChange={(event) => setText(event.target.value)} placeholder="ഉദാഹരണം: വെബ്സൈറ്റ് പാക്കേജിന്റെ വില എത്രയാണ്?" maxLength={4000} disabled={disabled}/>
            <button className="primary-button" disabled={disabled || sending || !text.trim()}>{sending ? "Replying…" : "Send"}</button>
          </form>
          {error && <div className="form-error">{error}</div>}
        </section>
      </div>

      {(tools.length > 0 || report) && <div className="playground-diagnostics">
        {tools.length > 0 && <section className="panel"><div className="panel-title"><div><span className="eyebrow">Secure execution</span><h2>Knowledge checks</h2></div></div><div className="tool-event-list">{tools.map((tool, index) => <div key={tool.id}><span>Knowledge check {index + 1}</span><span>{tool.latency_ms} ms</span><StatusBadge tone={tool.success ? "success" : "danger"}>{tool.success ? "OK" : "FAILED"}</StatusBadge></div>)}</div></section>}
        {report && <section className="panel report-card"><div className="panel-title"><div><span className="eyebrow">Factual test report</span><h2>Session complete</h2></div></div><div className="report-metrics"><span><strong>{report.message_count}</strong>messages</span><span><strong>{report.tool_calls}</strong>knowledge checks</span><span><strong>{report.sources_used.length}</strong>sources</span><span><strong>{report.duration_seconds}s</strong>duration</span></div></section>}
      </div>}
    </>
  );
}
