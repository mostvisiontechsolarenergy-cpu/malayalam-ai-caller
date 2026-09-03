import asyncio
import base64
import contextlib
import json
import time
import uuid
from typing import Any

import structlog
from fastapi import WebSocket
from google import genai
from google.genai import types
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.db.models import (
    AIAgent,
    AIConversationMessage,
    CallbackRequest,
    ConversationRole,
    PhoneCall,
    PhoneCallStatus,
)
from app.db.session import SessionLocal
from app.services.ai_conversations import (
    build_agent_instructions,
    gemini_live_tools,
    selected_voice,
)
from app.services.ai_tools import AIToolRegistry
from app.services.telephony.audio import (
    gemini_pcm_24khz_to_mulaw_8khz,
    mulaw_8khz_to_gemini_pcm_16khz,
)

logger = structlog.get_logger()
OPENING_PLAYBACK_SAFETY_SECONDS = 0.25


def _load_call_context(call_id: uuid.UUID) -> tuple[PhoneCall, AIAgent, bool]:
    with SessionLocal() as db:
        phone_call = db.scalar(select(PhoneCall).where(PhoneCall.id == call_id))
        if phone_call is None:
            raise LookupError("Phone call not found")
        agent = db.scalar(
            select(AIAgent).where(
                AIAgent.id == phone_call.agent_id,
                AIAgent.company_id == phone_call.company_id,
                AIAgent.active.is_(True),
            )
        )
        if agent is None:
            raise LookupError("AI agent not found")
        is_callback = bool(
            db.scalar(select(CallbackRequest.id).where(CallbackRequest.phone_call_id == call_id))
        )
        db.expunge(phone_call)
        db.expunge(agent)
        return phone_call, agent, is_callback


def _mark_stream_started(call_id: uuid.UUID, stream_id: str) -> None:
    with SessionLocal() as db:
        phone_call = db.scalar(select(PhoneCall).where(PhoneCall.id == call_id))
        if phone_call is None:
            return
        phone_call.provider_stream_sid = stream_id
        phone_call.status = PhoneCallStatus.IN_PROGRESS
        db.commit()


def _persist_transcript(
    phone_call: PhoneCall,
    role: ConversationRole,
    text: str,
) -> None:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return
    with SessionLocal() as db:
        db.add(
            AIConversationMessage(
                company_id=phone_call.company_id,
                conversation_id=phone_call.conversation_id,
                role=role,
                text=cleaned,
                provider_item_id=f"vobiz-{role.value.lower()}-{uuid.uuid4().hex}",
                source_json=[],
            )
        )
        db.commit()


def _execute_tool(phone_call: PhoneCall, function_call: types.FunctionCall) -> dict[str, Any]:
    with SessionLocal() as db:
        event = AIToolRegistry(db, phone_call.company_id).execute(
            conversation_id=phone_call.conversation_id,
            name=function_call.name or "",
            call_id=function_call.id or uuid.uuid4().hex,
            arguments=function_call.args or {},
            phone_call_id=phone_call.id,
        )
        db.commit()
        return event.result_json


def _append_transcription(current: str, incoming: str | None) -> str:
    text = incoming or ""
    if not text:
        return current
    if text.startswith(current):
        return text
    return current + text


async def _release_opening_gate_after(
    delay_seconds: float,
    phone_call_id: uuid.UUID,
    state: dict[str, Any],
) -> None:
    await asyncio.sleep(max(0.0, delay_seconds))
    if state["opening_played"].is_set():
        return
    state["opening_played"].set()
    state["opening_gate_reason"] = "PLAYBACK_TIMER_FALLBACK"
    logger.warning(
        "vobiz_opening_playback_fallback",
        phone_call_id=str(phone_call_id),
        delay_seconds=round(delay_seconds, 3),
        suppressed_inbound_frames=state["suppressed_inbound_frames"],
    )


async def _receive_vobiz_audio(
    websocket: WebSocket,
    gemini_session: Any,
    phone_call: PhoneCall,
    started: asyncio.Event,
    state: dict[str, Any],
) -> None:
    try:
        while True:
            payload = json.loads(await websocket.receive_text())
            event = payload.get("event")
            if event == "start":
                start = payload.get("start") or {}
                stream_id = str(start.get("streamId") or "")
                provider_call_id = str(start.get("callId") or "")
                media_format = start.get("mediaFormat") or {}
                encoding = str(media_format.get("encoding") or "").lower()
                sample_rate = int(media_format.get("sampleRate") or 0)
                if not stream_id or not provider_call_id:
                    raise ValueError("The calling start event omitted the call or stream ID")
                if (
                    phone_call.provider_call_sid
                    and provider_call_id != phone_call.provider_call_sid
                ):
                    raise ValueError("The calling stream ID does not match the requested call")
                if encoding not in {"audio/x-mulaw", "mulaw"} or sample_rate != 8000:
                    raise ValueError("The calling stream must use the required audio format")
                state["stream_id"] = stream_id
                state["stream_started_at"] = time.monotonic()
                state["inbound_frames"] = 0
                state["inbound_bytes"] = 0
                _mark_stream_started(phone_call.id, stream_id)
                logger.info(
                    "vobiz_stream_started",
                    phone_call_id=str(phone_call.id),
                    stream_id=stream_id,
                    encoding=encoding,
                    sample_rate=sample_rate,
                )
                started.set()
            elif event == "media":
                encoded = (payload.get("media") or {}).get("payload")
                if not encoded:
                    continue
                mulaw = base64.b64decode(encoded, validate=True)
                state["inbound_frames"] += 1
                state["inbound_bytes"] += len(mulaw)
                if not state["opening_played"].is_set():
                    state["suppressed_inbound_frames"] += 1
                    continue
                pcm = mulaw_8khz_to_gemini_pcm_16khz(mulaw)
                await gemini_session.send_realtime_input(
                    audio=types.Blob(data=pcm, mime_type="audio/pcm;rate=16000")
                )
            elif event == "playedStream" and payload.get("name") == "opening-greeting":
                state["opening_played"].set()
                state["opening_gate_reason"] = "VOBIZ_PLAYED_STREAM"
                fallback_task = state.get("opening_gate_fallback_task")
                if fallback_task and not fallback_task.done():
                    fallback_task.cancel()
                logger.info(
                    "vobiz_opening_played",
                    phone_call_id=str(phone_call.id),
                    suppressed_inbound_frames=state["suppressed_inbound_frames"],
                )
    except WebSocketDisconnect:
        with contextlib.suppress(Exception):
            await gemini_session.send_realtime_input(audio_stream_end=True)


async def _send_gemini_audio(
    websocket: WebSocket,
    gemini_session: Any,
    phone_call: PhoneCall,
    state: dict[str, Any],
) -> None:
    user_transcript = ""
    assistant_transcript = ""
    response_number = 0
    response_has_audio = False
    while True:
        received_message = False
        completed_turn = False
        # AsyncSession.receive() intentionally returns after one complete model turn.
        # Re-open the iterator so the phone bridge remains alive for the full call.
        async for message in gemini_session.receive():
            received_message = True
            stream_id = state.get("stream_id")
            if message.data and stream_id:
                if state["first_audio_latency_ms"] is None:
                    state["first_audio_latency_ms"] = round(
                        (time.monotonic() - state["stream_started_at"]) * 1000
                    )
                # Match the μ-law/8 kHz format negotiated by the Vobiz stream. Vobiz
                # playback checkpoints are tied to that stream-format queue.
                for offset in range(0, len(message.data), 1920):
                    chunk = message.data[offset : offset + 1920]
                    if not chunk:
                        continue
                    provider_audio = gemini_pcm_24khz_to_mulaw_8khz(chunk)
                    if not state["opening_checkpoint_sent"]:
                        if state.get("opening_audio_started_at") is None:
                            state["opening_audio_started_at"] = time.monotonic()
                        state["opening_audio_seconds"] = state.get(
                            "opening_audio_seconds", 0.0
                        ) + len(provider_audio) / 8000
                    await websocket.send_json(
                        {
                            "event": "playAudio",
                            "streamId": stream_id,
                            "media": {
                                "contentType": "audio/x-mulaw",
                                "sampleRate": 8000,
                                "payload": base64.b64encode(provider_audio).decode(),
                            },
                        }
                    )
                    state["outbound_chunks"] += 1
                    state["outbound_bytes"] += len(provider_audio)
                    response_has_audio = True

            content = message.server_content
            if content:
                if content.interrupted and stream_id and state["opening_played"].is_set():
                    await websocket.send_json(
                        {"event": "clearAudio", "streamId": stream_id}
                    )
                    response_has_audio = False
                if content.input_transcription:
                    user_transcript = _append_transcription(
                        user_transcript, content.input_transcription.text
                    )
                    if content.input_transcription.finished:
                        _persist_transcript(
                            phone_call, ConversationRole.USER, user_transcript
                        )
                        user_transcript = ""
                if content.output_transcription:
                    assistant_transcript = _append_transcription(
                        assistant_transcript, content.output_transcription.text
                    )
                    if content.output_transcription.finished:
                        _persist_transcript(
                            phone_call, ConversationRole.ASSISTANT, assistant_transcript
                        )
                        assistant_transcript = ""
                if content.turn_complete:
                    completed_turn = True
                    state["completed_turns"] = state.get("completed_turns", 0) + 1
                    if user_transcript:
                        _persist_transcript(
                            phone_call, ConversationRole.USER, user_transcript
                        )
                        user_transcript = ""
                    if assistant_transcript:
                        _persist_transcript(
                            phone_call, ConversationRole.ASSISTANT, assistant_transcript
                        )
                        assistant_transcript = ""
                    if response_has_audio and stream_id:
                        response_number += 1
                        checkpoint_name = (
                            "opening-greeting"
                            if not state["opening_checkpoint_sent"]
                            else f"gemini-response-{response_number}"
                        )
                        await websocket.send_json(
                            {
                                "event": "checkpoint",
                                "streamId": stream_id,
                                "name": checkpoint_name,
                            }
                        )
                        logger.info(
                            "vobiz_checkpoint_sent",
                            phone_call_id=str(phone_call.id),
                            checkpoint_name=checkpoint_name,
                            completed_turns=state["completed_turns"],
                        )
                        if checkpoint_name == "opening-greeting":
                            started_at = state.get("opening_audio_started_at")
                            elapsed = (
                                time.monotonic() - started_at if started_at is not None else 0.0
                            )
                            remaining_playback = max(
                                0.0, state.get("opening_audio_seconds", 0.0) - elapsed
                            )
                            fallback_delay = (
                                remaining_playback + OPENING_PLAYBACK_SAFETY_SECONDS
                            )
                            state["opening_gate_fallback_task"] = asyncio.create_task(
                                _release_opening_gate_after(
                                    fallback_delay, phone_call.id, state
                                )
                            )
                        state["opening_checkpoint_sent"] = True
                        response_has_audio = False

            if message.tool_call and message.tool_call.function_calls:
                responses = []
                for function_call in message.tool_call.function_calls:
                    result = await asyncio.to_thread(
                        _execute_tool, phone_call, function_call
                    )
                    responses.append(
                        types.FunctionResponse(
                            id=function_call.id,
                            name=function_call.name,
                            response={"output": result},
                        )
                    )
                await gemini_session.send_tool_response(function_responses=responses)

        if not received_message or not completed_turn:
            return


async def bridge_vobiz_to_gemini(websocket: WebSocket, call_id: uuid.UUID) -> None:
    settings = get_settings()
    if settings.ai_provider != "gemini" or not settings.gemini_key_configured:
        raise RuntimeError("The live voice service is not configured for phone calls")
    phone_call, agent, is_callback = _load_call_context(call_id)
    client = genai.Client(
        api_key=settings.gemini_api_key.get_secret_value(),  # type: ignore[union-attr]
        http_options={"api_version": "v1alpha"},
    )
    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": build_agent_instructions(
            agent, phone_call=True, callback_call=is_callback
        ),
        "speech_config": {
            "language_code": "ml-IN",
            "voice_config": {"prebuilt_voice_config": {"voice_name": selected_voice(agent.voice)}},
        },
        "input_audio_transcription": {},
        "output_audio_transcription": {},
        "realtime_input_config": {
            "automatic_activity_detection": {
                "disabled": False,
                "silence_duration_ms": 700,
            }
        },
        "tools": [{"function_declarations": gemini_live_tools(include_phone_tools=True)}],
    }
    started = asyncio.Event()
    state: dict[str, Any] = {
        "stream_id": None,
        "stream_started_at": time.monotonic(),
        "first_audio_latency_ms": None,
        "inbound_frames": 0,
        "inbound_bytes": 0,
        "suppressed_inbound_frames": 0,
        "outbound_chunks": 0,
        "outbound_bytes": 0,
        "completed_turns": 0,
        "opening_checkpoint_sent": False,
        "opening_audio_started_at": None,
        "opening_audio_seconds": 0.0,
        "opening_gate_fallback_task": None,
        "opening_gate_reason": None,
        "opening_played": asyncio.Event(),
    }
    async with client.aio.live.connect(
        model=settings.gemini_live_model, config=config
    ) as gemini_session:
        incoming = asyncio.create_task(
            _receive_vobiz_audio(websocket, gemini_session, phone_call, started, state)
        )
        outgoing: asyncio.Task[None] | None = None
        try:
            await asyncio.wait_for(started.wait(), timeout=15)
            outgoing = asyncio.create_task(
                _send_gemini_audio(websocket, gemini_session, phone_call, state)
            )
            await asyncio.sleep(0)
            opening_message = (
                "നമസ്കാരം സർ, ഞാൻ D-Creation-ൽ നിന്നുള്ള Maya ആണ് സംസാരിക്കുന്നത്. "
                "നിങ്ങൾ ആവശ്യപ്പെട്ട സമയത്തെ callback ആണ്. ഇപ്പോൾ സംസാരിക്കാൻ സൗകര്യമുണ്ടോ?"
                if is_callback
                else agent.opening_message
            )
            await gemini_session.send_client_content(
                turns={
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "Speak this exact approved Malayalam greeting now, without "
                                f"adding or removing words: {opening_message} "
                                "Then stop speaking and wait for the caller."
                            )
                        }
                    ],
                },
                turn_complete=True,
            )
            done, pending = await asyncio.wait(
                {incoming, outgoing}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                task.result()
        finally:
            if not incoming.done():
                incoming.cancel()
                await asyncio.gather(incoming, return_exceptions=True)
            if outgoing and not outgoing.done():
                outgoing.cancel()
                await asyncio.gather(outgoing, return_exceptions=True)
            fallback_task = state.get("opening_gate_fallback_task")
            if fallback_task and not fallback_task.done():
                fallback_task.cancel()
                await asyncio.gather(fallback_task, return_exceptions=True)
    logger.info(
        "vobiz_gemini_stream_closed",
        phone_call_id=str(call_id),
        inbound_frames=state["inbound_frames"],
        inbound_bytes=state["inbound_bytes"],
        outbound_chunks=state["outbound_chunks"],
        outbound_bytes=state["outbound_bytes"],
        first_audio_latency_ms=state["first_audio_latency_ms"],
        suppressed_inbound_frames=state["suppressed_inbound_frames"],
        completed_turns=state["completed_turns"],
        opening_checkpoint_sent=state["opening_checkpoint_sent"],
        opening_played=state["opening_played"].is_set(),
        opening_gate_reason=state["opening_gate_reason"],
    )
