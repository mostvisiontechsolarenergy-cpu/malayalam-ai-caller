"use client";

import {
  GoogleGenAI,
  Modality,
  ThinkingLevel,
  type LiveServerMessage,
  type Session,
} from "@google/genai";
import { useCallback, useEffect, useRef, useState } from "react";

import { StatusBadge } from "@/components/resource-page";
import { apiRequest } from "@/lib/api";
import type {
  Agent,
  Client,
  Conversation,
  LiveSessionConfig,
  ProviderStatus,
  SessionReport,
  ToolEvent,
  TranscriptMessage,
} from "@/lib/ai-types";
import { activeVoice } from "@/lib/ai-types";

type RealtimeOutputItem = {
  id?: string;
  type: string;
  name?: string;
  call_id?: string;
  arguments?: string;
};

type RealtimeEvent = {
  type: string;
  item_id?: string;
  transcript?: string;
  error?: { message?: string };
  response?: { output?: RealtimeOutputItem[] };
};

type ToolResponse = { event: ToolEvent; output: Record<string, unknown> };

function mergeTranscript(current: string, incoming: string) {
  if (!incoming) return current;
  if (!current || incoming.startsWith(current)) return incoming;
  if (current.endsWith(incoming)) return current;
  return `${current}${incoming}`;
}

function arrayBufferToBase64(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 1) binary += String.fromCharCode(bytes[index]);
  return window.btoa(binary);
}

function base64ToArrayBuffer(value: string) {
  const binary = window.atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes.buffer;
}

function downsample(input: Float32Array, inputRate: number, outputRate = 16000) {
  if (inputRate === outputRate) return input;
  const ratio = inputRate / outputRate;
  const result = new Float32Array(Math.round(input.length / ratio));
  let sourceOffset = 0;
  for (let index = 0; index < result.length; index += 1) {
    const nextOffset = Math.min(input.length, Math.round((index + 1) * ratio));
    let total = 0;
    let count = 0;
    for (; sourceOffset < nextOffset; sourceOffset += 1) {
      total += input[sourceOffset];
      count += 1;
    }
    result[index] = count ? total / count : 0;
  }
  return result;
}

function pcm16Base64(input: Float32Array, inputRate: number) {
  const samples = downsample(input, inputRate);
  const pcm = new Int16Array(samples.length);
  for (let index = 0; index < samples.length; index += 1) {
    const value = Math.max(-1, Math.min(1, samples[index]));
    pcm[index] = value < 0 ? value * 0x8000 : value * 0x7fff;
  }
  return arrayBufferToBase64(pcm.buffer);
}

async function realtimeAnswer(response: Response) {
  const text = await response.text();
  if (response.ok) return text;
  try {
    const payload = JSON.parse(text) as { detail?: string };
    throw new Error(payload.detail ?? "Live voice session failed.");
  } catch (error) {
    if (error instanceof SyntaxError) throw new Error("Live voice session failed.");
    throw error;
  }
}

export default function VoicePlaygroundPage() {
  const [provider, setProvider] = useState<ProviderStatus | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [agentId, setAgentId] = useState("");
  const [clientId, setClientId] = useState("");
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [tools, setTools] = useState<ToolEvent[]>([]);
  const [report, setReport] = useState<SessionReport | null>(null);
  const [connection, setConnection] = useState<"IDLE" | "CONNECTING" | "LIVE" | "ENDING" | "ENDED">("IDLE");
  const [activity, setActivity] = useState("Ready to start");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const peerRef = useRef<RTCPeerConnection | null>(null);
  const channelRef = useRef<RTCDataChannel | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const geminiSessionRef = useRef<Session | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const captureContextRef = useRef<AudioContext | null>(null);
  const captureSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const playbackContextRef = useRef<AudioContext | null>(null);
  const playbackSourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const nextPlaybackRef = useRef(0);
  const inputTranscriptRef = useRef("");
  const outputTranscriptRef = useRef("");
  const transcriptSequenceRef = useRef(0);
  const transcriptEnd = useRef<HTMLDivElement>(null);
  const pendingSources = useRef<Record<string, unknown>[]>([]);
  const persistedItems = useRef(new Set<string>());

  useEffect(() => {
    void Promise.all([
      apiRequest<ProviderStatus>("backend/ai/provider-status"),
      apiRequest<Agent[]>("backend/ai-agents"),
      apiRequest<Client[]>("backend/clients"),
    ])
      .then(([providerResult, agentResult, clientResult]) => {
        const activeAgents = agentResult.filter((item) => item.active);
        setProvider(providerResult);
        setAgents(activeAgents);
        setClients(clientResult);
        setAgentId(activeAgents[0]?.id ?? "");
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Could not load the playground."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const stopPlayback = useCallback(() => {
    for (const source of playbackSourcesRef.current) {
      try { source.stop(); } catch { /* The source may already have ended. */ }
    }
    playbackSourcesRef.current = [];
    nextPlaybackRef.current = playbackContextRef.current?.currentTime ?? 0;
  }, []);

  const stopMedia = useCallback(() => {
    processorRef.current?.disconnect();
    captureSourceRef.current?.disconnect();
    processorRef.current = null;
    captureSourceRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    void captureContextRef.current?.close();
    captureContextRef.current = null;
    channelRef.current?.close();
    peerRef.current?.close();
    channelRef.current = null;
    peerRef.current = null;
    geminiSessionRef.current?.close();
    geminiSessionRef.current = null;
    stopPlayback();
    void playbackContextRef.current?.close();
    playbackContextRef.current = null;
    nextPlaybackRef.current = 0;
  }, [stopPlayback]);

  useEffect(() => () => {
    stopMedia();
  }, [stopMedia]);

  const playGeminiAudio = useCallback(async (base64: string) => {
    let context = playbackContextRef.current;
    if (!context) {
      context = new AudioContext();
      playbackContextRef.current = context;
    }
    if (context.state === "suspended") await context.resume();
    const pcm = new Int16Array(base64ToArrayBuffer(base64));
    const buffer = context.createBuffer(1, pcm.length, 24000);
    const channel = buffer.getChannelData(0);
    for (let index = 0; index < pcm.length; index += 1) channel[index] = pcm[index] / 32768;
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    const startAt = Math.max(context.currentTime, nextPlaybackRef.current);
    source.start(startAt);
    nextPlaybackRef.current = startAt + buffer.duration;
    playbackSourcesRef.current.push(source);
    source.onended = () => {
      playbackSourcesRef.current = playbackSourcesRef.current.filter((item) => item !== source);
    };
  }, []);

  const persistMessage = useCallback(async (
    conversationId: string,
    role: "USER" | "ASSISTANT",
    text: string,
    providerItemId?: string,
  ) => {
    const normalized = text.trim();
    if (!normalized || (providerItemId && persistedItems.current.has(providerItemId))) return;
    if (providerItemId) persistedItems.current.add(providerItemId);
    const sourceJson = role === "ASSISTANT" ? pendingSources.current.splice(0) : [];
    const local: TranscriptMessage = { role, text: normalized, provider_item_id: providerItemId, source_json: sourceJson };
    setMessages((items) => [...items, local]);
    try {
      await apiRequest(`backend/ai/conversations/${conversationId}/messages`, {
        method: "POST",
        body: JSON.stringify({ role, text: normalized, provider_item_id: providerItemId ?? null, source_json: sourceJson }),
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save a transcript turn.");
    }
  }, []);

  const flushGeminiTranscript = useCallback(async (conversationId: string, role: "USER" | "ASSISTANT") => {
    const reference = role === "USER" ? inputTranscriptRef : outputTranscriptRef;
    const text = reference.current.trim();
    if (!text) return;
    reference.current = "";
    transcriptSequenceRef.current += 1;
    await persistMessage(conversationId, role, text, `gemini-${role.toLowerCase()}-${transcriptSequenceRef.current}`);
  }, [persistMessage]);

  const executeGeminiTools = useCallback(async (conversationId: string, message: LiveServerMessage) => {
    const responses = [];
    for (const call of message.toolCall?.functionCalls ?? []) {
      if (!call.name || !call.id) continue;
      try {
        const result = await apiRequest<ToolResponse>(`backend/ai/conversations/${conversationId}/tools`, {
          method: "POST",
          body: JSON.stringify({ name: call.name, call_id: call.id, arguments: call.args ?? {} }),
        });
        setTools((items) => items.some((item) => item.id === result.event.id) ? items : [...items, result.event]);
        const sources = Array.isArray(result.output.sources) ? result.output.sources as Record<string, unknown>[] : [];
        pendingSources.current.push(...sources);
        responses.push({ id: call.id, name: call.name, response: { result: result.output } });
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "A controlled tool failed.");
        responses.push({ id: call.id, name: call.name, response: { result: { ok: false, error: "Controlled tool execution failed" } } });
      }
    }
    if (responses.length) geminiSessionRef.current?.sendToolResponse({ functionResponses: responses });
  }, []);

  const handleGeminiMessage = useCallback(async (conversationId: string, message: LiveServerMessage) => {
    if (message.setupComplete) {
      setConnection("LIVE");
      setActivity("Listening for Malayalam");
    }
    if (message.data) await playGeminiAudio(message.data);
    const content = message.serverContent;
    if (content?.interrupted) {
      stopPlayback();
      outputTranscriptRef.current = "";
    }
    if (content?.inputTranscription?.text) {
      inputTranscriptRef.current = mergeTranscript(inputTranscriptRef.current, content.inputTranscription.text);
      setActivity("Customer is speaking…");
    }
    if (content?.inputTranscription?.finished) await flushGeminiTranscript(conversationId, "USER");
    if (content?.outputTranscription?.text) {
      outputTranscriptRef.current = mergeTranscript(outputTranscriptRef.current, content.outputTranscription.text);
      setActivity("AI is responding…");
    }
    if (content?.outputTranscription?.finished) await flushGeminiTranscript(conversationId, "ASSISTANT");
    if (message.toolCall) {
      await flushGeminiTranscript(conversationId, "USER");
      setActivity("Checking approved knowledge…");
      await executeGeminiTools(conversationId, message);
    }
    if (content?.turnComplete) {
      await flushGeminiTranscript(conversationId, "USER");
      await flushGeminiTranscript(conversationId, "ASSISTANT");
      setActivity("Listening for Malayalam");
    }
  }, [executeGeminiTools, flushGeminiTranscript, playGeminiAudio, stopPlayback]);

  const executeOpenAITool = useCallback(async (conversationId: string, channel: RTCDataChannel, item: RealtimeOutputItem) => {
    if (!item.name || !item.call_id) return;
    let args: Record<string, unknown> = {};
    try { args = JSON.parse(item.arguments ?? "{}"); } catch { args = {}; }
    try {
      const result = await apiRequest<ToolResponse>(`backend/ai/conversations/${conversationId}/tools`, {
        method: "POST",
        body: JSON.stringify({ name: item.name, call_id: item.call_id, arguments: args }),
      });
      setTools((items) => items.some((event) => event.id === result.event.id) ? items : [...items, result.event]);
      const sources = Array.isArray(result.output.sources) ? result.output.sources as Record<string, unknown>[] : [];
      pendingSources.current.push(...sources);
      channel.send(JSON.stringify({ type: "conversation.item.create", item: { type: "function_call_output", call_id: item.call_id, output: JSON.stringify(result.output) } }));
      channel.send(JSON.stringify({ type: "response.create" }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "A controlled tool failed.");
      channel.send(JSON.stringify({ type: "conversation.item.create", item: { type: "function_call_output", call_id: item.call_id, output: JSON.stringify({ ok: false, error: "Controlled tool execution failed" }) } }));
      channel.send(JSON.stringify({ type: "response.create" }));
    }
  }, []);

  const handleOpenAIEvent = useCallback(async (conversationId: string, channel: RTCDataChannel, event: RealtimeEvent) => {
    if (event.type === "session.created") {
      setConnection("LIVE");
      setActivity("Listening for Malayalam");
      channel.send(JSON.stringify({ type: "response.create", response: { instructions: "Start the test now with the configured opening message and clear AI disclosure." } }));
      return;
    }
    if (event.type === "input_audio_buffer.speech_started") setActivity("Customer is speaking…");
    if (event.type === "input_audio_buffer.speech_stopped") setActivity("Thinking…");
    if (event.type === "conversation.item.input_audio_transcription.completed" && event.transcript) {
      await persistMessage(conversationId, "USER", event.transcript, event.item_id);
    }
    if (event.type === "response.output_audio_transcript.done" && event.transcript) {
      await persistMessage(conversationId, "ASSISTANT", event.transcript, event.item_id);
      setActivity("Listening for Malayalam");
    }
    if (event.type === "response.done") {
      for (const item of event.response?.output ?? []) if (item.type === "function_call") await executeOpenAITool(conversationId, channel, item);
    }
    if (event.type === "error") setError("The live voice engine returned an error.");
  }, [executeOpenAITool, persistMessage]);

  async function startGemini(created: Conversation) {
    const live = await apiRequest<LiveSessionConfig>(`backend/ai/conversations/${created.id}/live-token`, { method: "POST" });
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    });
    streamRef.current = stream;
    const ai = new GoogleGenAI({ apiKey: live.token, httpOptions: { apiVersion: "v1alpha" } });
    setActivity("Connecting to the live voice engine…");
    const session = await ai.live.connect({
      model: live.model,
      callbacks: {
        onopen: () => setActivity("Live voice connected"),
        onmessage: (message) => { void handleGeminiMessage(created.id, message); },
        onerror: () => setError("The live voice engine returned an error."),
        onclose: () => {
          if (connection !== "ENDING" && connection !== "ENDED") setActivity("Live voice connection closed");
        },
      },
      config: {
        responseModalities: [Modality.AUDIO],
        systemInstruction: live.instructions,
        speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: live.voice } } },
        inputAudioTranscription: {},
        outputAudioTranscription: {},
        thinkingConfig: { thinkingLevel: ThinkingLevel.MINIMAL },
        realtimeInputConfig: { automaticActivityDetection: { disabled: false, silenceDurationMs: 700, prefixPaddingMs: 120 } },
        tools: [{ functionDeclarations: live.tools }],
      },
    });
    geminiSessionRef.current = session;
    const context = new AudioContext();
    captureContextRef.current = context;
    await context.resume();
    const source = context.createMediaStreamSource(stream);
    const processor = context.createScriptProcessor(4096, 1, 1);
    captureSourceRef.current = source;
    processorRef.current = processor;
    processor.onaudioprocess = (event) => {
      const current = geminiSessionRef.current;
      if (!current) return;
      current.sendRealtimeInput({
        audio: {
          data: pcm16Base64(event.inputBuffer.getChannelData(0), context.sampleRate),
          mimeType: "audio/pcm;rate=16000",
        },
      });
    };
    source.connect(processor);
    processor.connect(context.destination);
    session.sendRealtimeInput({ text: "Start the conversation now using the configured opening message. Clearly disclose that you are an AI assistant and speak in natural Malayalam." });
  }

  async function startOpenAI(created: Conversation) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    const peer = new RTCPeerConnection();
    peerRef.current = peer;
    peer.ontrack = (event) => { if (audioRef.current) audioRef.current.srcObject = event.streams[0]; };
    stream.getTracks().forEach((track) => peer.addTrack(track, stream));
    const channel = peer.createDataChannel("oai-events");
    channelRef.current = channel;
    channel.addEventListener("message", (message) => {
      try { void handleOpenAIEvent(created.id, channel, JSON.parse(message.data) as RealtimeEvent); }
      catch { setError("Received an unreadable Realtime event."); }
    });
    channel.addEventListener("close", () => setActivity("Realtime connection closed"));
    const offer = await peer.createOffer();
    await peer.setLocalDescription(offer);
    setActivity("Connecting to the live voice engine…");
    const response = await fetch(`/api/backend/ai/conversations/${created.id}/realtime`, {
      method: "POST", headers: { "Content-Type": "application/sdp" }, body: offer.sdp,
    });
    const answerSdp = await realtimeAnswer(response);
    await peer.setRemoteDescription({ type: "answer", sdp: answerSdp });
  }

  async function start() {
    if (!provider?.configured || !agentId || connection !== "IDLE") return;
    setConnection("CONNECTING");
    setActivity("Requesting microphone…");
    setError("");
    try {
      const created = await apiRequest<Conversation>("backend/ai/conversations", {
        method: "POST",
        body: JSON.stringify({ agent_id: agentId, client_id: clientId || null, channel: "VOICE_PLAYGROUND" }),
      });
      setConversation(created);
      if (provider.connection_mode === "secure_token") await startGemini(created);
      else await startOpenAI(created);
    } catch (caught) {
      stopMedia();
      setConnection("IDLE");
      setActivity("Ready to start");
      setError(caught instanceof Error ? caught.message : "Could not start the microphone test.");
    }
  }

  async function end() {
    if (!conversation || connection === "ENDED" || connection === "ENDING") return;
    setConnection("ENDING");
    setActivity("Saving the test report…");
    geminiSessionRef.current?.sendRealtimeInput({ audioStreamEnd: true });
    await flushGeminiTranscript(conversation.id, "USER");
    await flushGeminiTranscript(conversation.id, "ASSISTANT");
    stopMedia();
    try {
      const result = await apiRequest<SessionReport>(`backend/ai/conversations/${conversation.id}/end`, { method: "POST" });
      setReport(result);
      setConnection("ENDED");
      setActivity("Test complete");
    } catch (caught) {
      setConnection("ENDED");
      setError(caught instanceof Error ? caught.message : "Could not save the test report.");
    }
  }

  const selectedAgent = agents.find((agent) => agent.id === agentId);
  return (
    <>
      <audio ref={audioRef} autoPlay aria-label="AI assistant audio" />
      <header className="page-heading">
        <div>
          <span className="eyebrow">Secure microphone test</span>
          <h1>Malayalam Voice Playground</h1>
          <p>Speak Malayalam, hear the grounded assistant, and inspect the live transcript and approved knowledge checks.</p>
        </div>
        <StatusBadge tone={connection === "LIVE" ? "success" : provider?.configured ? "info" : "warning"}>
          {connection === "LIVE" ? "LIVE" : provider?.configured ? connection : "AI SETUP REQUIRED"}
        </StatusBadge>
      </header>

      <div className={`info-banner ${provider?.configured ? "" : "warning-banner"}`}>
        <strong>{provider?.configured ? "Secure voice test:" : "Voice engine unavailable:"}</strong>{" "}
        {provider?.detail ?? "Checking voice configuration…"} No telephone call is started from this page.
      </div>

      <div className="voice-layout">
        <section className="panel voice-console">
          <div className={`voice-orb ${connection === "LIVE" ? "live" : ""}`}><span>AI</span></div>
          <span className="eyebrow">Realtime status</span>
          <h2>{activity}</h2>
          <div className="voice-wave" aria-hidden="true">{Array.from({ length: 18 }).map((_, index) => <span key={index} />)}</div>
          <div className="voice-context">
            <label className="field-label">AI agent
              <select value={agentId} onChange={(event) => setAgentId(event.target.value)} disabled={connection !== "IDLE"}>
                <option value="">Select an agent</option>
                {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name} · {activeVoice(agent.voice, provider?.connection_mode)}</option>)}
              </select>
            </label>
            <label className="field-label">Client (optional)
              <select value={clientId} onChange={(event) => setClientId(event.target.value)} disabled={connection !== "IDLE"}>
                <option value="">No client selected</option>
                {clients.map((client) => <option key={client.id} value={client.id}>{client.name} · {client.phone}</option>)}
              </select>
            </label>
          </div>
          <div className="voice-model-line"><span>Secure live audio</span><span>{activeVoice(selectedAgent?.voice ?? "marin", provider?.connection_mode)} voice</span><span>Malayalam + English</span></div>
          {connection === "IDLE" ? (
            <button className="primary-button voice-action" onClick={() => void start()} disabled={loading || !provider?.voice_ready || !agentId}>Start microphone test</button>
          ) : connection !== "ENDED" ? (
            <button className="danger-button voice-action" onClick={() => void end()} disabled={connection === "CONNECTING" || connection === "ENDING"}>End conversation</button>
          ) : null}
          <p className="microphone-note">Your browser asks for microphone permission only after Start. The session uses a short-lived credential; permanent credentials remain backend-only.</p>
          {error && <div className="form-error">{error}</div>}
        </section>

        <section className="panel transcript-panel voice-transcript">
          <div className="panel-title transcript-heading"><div><span className="eyebrow">Live transcript</span><h2>Conversation turns</h2></div><span>{messages.length} messages</span></div>
          <div className="transcript-stream" aria-live="polite">
            {messages.length === 0 ? <div className="compact-empty"><h3>Your transcript will appear here</h3><p>The assistant opens the conversation after the secure Live session connects.</p></div> : messages.map((message, index) => <article className={`transcript-bubble ${message.role.toLowerCase()}`} key={message.provider_item_id ?? index}><span>{message.role === "USER" ? "Customer" : "AI assistant"}</span><p lang="ml">{message.text}</p>{message.source_json && message.source_json.length > 0 && <small>{message.source_json.length} approved sources</small>}</article>)}
            <div ref={transcriptEnd} />
          </div>
          <div className="voice-tool-strip"><span>Knowledge checks</span>{tools.length === 0 ? <em>No knowledge check yet</em> : <strong>{tools.length} completed securely</strong>}</div>
        </section>
      </div>

      {report && <section className="panel report-card voice-report"><div className="panel-title"><div><span className="eyebrow">Factual test report</span><h2>Voice session saved</h2></div><StatusBadge tone="success">COMPLETE</StatusBadge></div><div className="report-metrics"><span><strong>{report.duration_seconds}s</strong>duration</span><span><strong>{report.user_turns}</strong>customer turns</span><span><strong>{report.assistant_turns}</strong>AI turns</span><span><strong>{report.tool_calls}</strong>knowledge checks</span><span><strong>{report.sources_used.length}</strong>sources</span></div></section>}
    </>
  );
}
