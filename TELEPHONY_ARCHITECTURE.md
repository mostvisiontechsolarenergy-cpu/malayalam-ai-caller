# Vobiz Telephony Architecture

## Call flow

```text
Admin starts approved call
  -> tenant, role, consent, and opt-out checks
  -> Vobiz Call API dials the consented destination
  -> signed answer callback returns <Stream bidirectional="true">
  -> Vobiz opens the per-call WSS media stream
  -> FastAPI converts μ-law/8 kHz to PCM/16 kHz
  -> Gemini Live handles Malayalam audio and approved knowledge tools
  -> FastAPI sends Gemini L16 PCM/24 kHz directly to Vobiz
  -> playAudio delivers the response through Vobiz to the phone
```

`PhoneCall` owns provider identifiers, normalized status, duration, tenant/client/agent ownership, and a linked `AIConversation`. Provider callbacks never receive an authenticated browser token. They are authorized using Vobiz HMAC-SHA256 V2/V3 signatures, an opaque per-call URL token stored only as a SHA-256 hash, and CallUUID correlation.

`CallbackRequest` stores the customer-confirmed exact callback instant in UTC with `Asia/Kolkata` as the business timezone. Gemini must ask for an exact clock time when a customer gives a vague period, repeat the exact date/time, and receive explicit confirmation before invoking `schedule_callback`. A persistent backend scheduler claims due rows every two seconds and starts the Vobiz call without manual approval. Calling consent and opt-out state are revalidated immediately before dispatch. Requests survive restarts, stale claims recover automatically, and provider-readiness failures retry only within a bounded 15-minute dispatch window.

## Media protocol

The answer webhook returns Vobiz XML with a bidirectional `<Stream>` using inbound `audio/x-mulaw;rate=8000`. Vobiz sends `start`, `media`, `playedStream`, and `clearedAudio` events. The application sends `playAudio`, `checkpoint`, `clearAudio`, and optionally `stop` commands.

Inbound base64 μ-law/8 kHz becomes signed 16-bit little-endian PCM/16 kHz for Gemini. Gemini's native L16 PCM/24 kHz output is sent directly to Vobiz in 20–40 ms playback chunks, avoiding a second lossy conversion. Raw audio is not written to disk. Gemini transcriptions are stored in the tenant-scoped conversation timeline, and tool calls execute only through the allow-listed `AIToolRegistry`. On barge-in, the bridge sends `clearAudio` to discard queued assistant audio.

## Provider operations

The Vobiz adapter implements:

- outbound call creation through `POST /api/v1/Account/{auth_id}/Call/`;
- ringing, answered, completed, busy, failed, cancelled, timeout, and no-answer normalization;
- active-call termination through `DELETE /Call/{call_uuid}/`;
- live call detail retrieval;
- signed answer, hangup, and stream lifecycle callbacks.

Transfer, recording, campaigns, bulk dialing, and automatic retry dialing remain disabled.

## Security and compliance

- Vobiz Auth ID and Auth Token stay in backend environment variables.
- HTTP callbacks validate Vobiz V3 or V2 HMAC-SHA256 signatures using the Auth Token.
- WebSocket access requires a high-entropy per-call token and then validates the Vobiz `start.callId` against the stored CallUUID.
- Permanent secrets never appear in browser JavaScript, callback payload storage, or logs.
- Calls require an active agent and a tenant-owned client with `GRANTED` consent, Calling allowed enabled, and Opted out disabled.
- The callback origin must use HTTPS/WSS; recording is off by default.
- Vobiz balance, approved caller ID, geographic routing, India KYC/UCC requirements, and customer consent remain operational requirements.

Official references: [Make an outbound call](https://vobiz.ai/docs/call/make-call), [Stream XML](https://vobiz.ai/docs/xml/stream), [Stream events](https://vobiz.ai/docs/xml/stream/stream-events), [validating callbacks](https://vobiz.ai/docs/concepts/validating-callbacks), and [hang up a call](https://vobiz.ai/docs/call/hangup-call).
