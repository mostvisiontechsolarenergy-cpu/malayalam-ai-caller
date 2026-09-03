export type ProviderStatus = {
  provider: "AI_ENGINE";
  connection_mode: "secure_token" | "secure_session";
  configured: boolean;
  voice_ready: boolean;
  detail: string;
};

export type LiveSessionConfig = {
  provider: "AI_ENGINE";
  token: string;
  model: string;
  voice: string;
  instructions: string;
  tools: Array<{
    name: string;
    description?: string;
    parameters?: Record<string, unknown>;
  }>;
};

export type Agent = {
  id: string;
  name: string;
  voice: string;
  tone: string;
  primary_language: string;
  active: boolean;
};

export type Client = { id: string; name: string; phone: string };

export type Conversation = {
  id: string;
  channel: "TEXT_TEST" | "VOICE_PLAYGROUND";
  status: "ACTIVE" | "COMPLETED" | "FAILED";
  model: string;
  voice: string | null;
};

export type TranscriptMessage = {
  id?: string;
  provider_item_id?: string | null;
  role: "USER" | "ASSISTANT" | "TOOL";
  text: string;
  source_json?: Record<string, unknown>[];
  created_at?: string;
};

export type ToolEvent = {
  id: string;
  tool_name: string;
  call_id: string;
  arguments_json: Record<string, unknown>;
  result_json: Record<string, unknown>;
  success: boolean;
  latency_ms: number;
  created_at: string;
};

export type SessionReport = {
  conversation_id: string;
  status: string;
  channel: string;
  duration_seconds: number;
  message_count: number;
  user_turns: number;
  assistant_turns: number;
  tool_calls: number;
  successful_tool_calls: number;
  sources_used: Record<string, unknown>[];
  generated_at: string;
};

const REALTIME_VOICES = new Set([
  "alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse", "marin", "cedar",
  "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede", "Callirrhoe",
  "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba", "Despina", "Erinome", "Algenib",
  "Rasalgethi", "Laomedeia", "Achernar", "Alnilam", "Schedar", "Gacrux", "Pulcherrima",
  "Achird", "Zubenelgenubi", "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]);

const VOICE_COMPATIBILITY_MAP: Record<string, string> = {
  marin: "Kore", cedar: "Charon", coral: "Aoede", sage: "Sulafat", alloy: "Puck",
  ash: "Orus", ballad: "Leda", echo: "Iapetus", shimmer: "Zephyr", verse: "Achird",
};

export function normalizedVoice(voice: string) {
  return REALTIME_VOICES.has(voice) ? voice : "marin";
}

export function activeVoice(voice: string, connectionMode?: string) {
  if (connectionMode === "secure_token") return VOICE_COMPATIBILITY_MAP[voice] ?? (REALTIME_VOICES.has(voice) ? voice : "Kore");
  return normalizedVoice(voice);
}
