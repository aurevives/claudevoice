"""Conversation tools for interactive voice interactions."""

import asyncio
import logging
import os
import time
import traceback
from typing import Optional, Literal
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from pydub import AudioSegment
from openai import AsyncOpenAI
import httpx

from voice_mcp.server_new import mcp
from voice_mcp.config import (
    audio_operation_lock,
    SAMPLE_RATE,
    CHANNELS,
    DEBUG,
    DEBUG_DIR,
    SAVE_AUDIO,
    AUDIO_DIR,
    OPENAI_API_KEY,
    STT_BASE_URL,
    TTS_BASE_URL,
    TTS_VOICE,
    TTS_MODEL,
    STT_MODEL,
    OPENAI_TTS_BASE_URL,
    KOKORO_TTS_BASE_URL,
    LIVEKIT_URL,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    PREFER_LOCAL,
    ALLOW_EMOTIONS,
    EMOTION_AUTO_UPGRADE,
    AUDIO_FEEDBACK_ENABLED,
    AUDIO_FEEDBACK_TYPE,
    AUDIO_FEEDBACK_VOICE,
    AUDIO_FEEDBACK_MODEL,
    AUDIO_FEEDBACK_STYLE,
    service_processes,
    HTTP_CLIENT_CONFIG
)
import voice_mcp.config
from voice_mcp.providers import (
    PROVIDERS,
    get_provider_by_voice,
    get_tts_provider,
    get_stt_provider,
    is_provider_available,
    get_provider_display_status
)
from voice_mcp.core import (
    get_openai_clients,
    text_to_speech,
    cleanup as cleanup_clients,
    save_debug_file,
    get_debug_filename,
    play_chime_start,
    play_chime_end
)

logger = logging.getLogger("voice-mcp")

# Initialize OpenAI clients with provider-specific TTS clients
openai_clients = get_openai_clients(OPENAI_API_KEY, STT_BASE_URL, TTS_BASE_URL)

# Add provider-specific TTS clients
# Always create OpenAI TTS client for emotional speech support
openai_clients['tts_openai'] = AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_TTS_BASE_URL,
    http_client=httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=5.0),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
    )
)

# Create Kokoro TTS client if different from default
if KOKORO_TTS_BASE_URL != TTS_BASE_URL:
    openai_clients['tts_kokoro'] = AsyncOpenAI(
        api_key=OPENAI_API_KEY,
        base_url=KOKORO_TTS_BASE_URL,
        http_client=httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
    )


async def startup_initialization():
    """Initialize services on startup based on configuration"""
    if voice_mcp.config._startup_initialized:
        return
    
    voice_mcp.config._startup_initialized = True
    logger.info("Running startup initialization...")
    
    # Check if we should auto-start Kokoro
    auto_start_kokoro = os.getenv("VOICE_MCP_AUTO_START_KOKORO", "").lower() in ("true", "1", "yes", "on")
    if auto_start_kokoro:
        try:
            # Check if Kokoro is already running
            async with httpx.AsyncClient(timeout=3.0) as client:
                base_url = KOKORO_TTS_BASE_URL.rstrip('/').removesuffix('/v1')
                health_url = f"{base_url}/health"
                response = await client.get(health_url)
                
                if response.status_code == 200:
                    logger.info("Kokoro TTS is already running externally")
                else:
                    raise Exception("Not running")
        except:
            # Kokoro is not running, start it
            logger.info("Auto-starting Kokoro TTS service...")
            try:
                # Import here to avoid circular dependency
                import subprocess
                if "kokoro" not in service_processes:
                    process = subprocess.Popen(
                        ["uvx", "kokoro-fastapi"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        env={**os.environ}
                    )
                    service_processes["kokoro"] = process
                    
                    # Wait a moment for it to start
                    await asyncio.sleep(2.0)
                    
                    # Verify it started
                    if process.poll() is None:
                        logger.info(f"✓ Kokoro TTS started successfully (PID: {process.pid})")
                    else:
                        logger.error("Failed to start Kokoro TTS")
            except Exception as e:
                logger.error(f"Error auto-starting Kokoro: {e}")
    
    # Log initial status
    logger.info("Service initialization complete")


async def get_tts_config(provider: Optional[str] = None, voice: Optional[str] = None, model: Optional[str] = None, instructions: Optional[str] = None):
    """Get TTS configuration based on provider selection"""
    # Auto-detect provider based on voice if not specified
    if provider is None and voice:
        provider_info = get_provider_by_voice(voice)
        if provider_info:
            provider = provider_info["id"]
    
    # If no provider specified and PREFER_LOCAL is true, try local first
    if provider is None and PREFER_LOCAL:
        # Check if Kokoro is available
        if await is_provider_available("kokoro"):
            provider = "kokoro"
            logger.info("Auto-selected Kokoro (local) as TTS provider")
        else:
            provider = "openai"
    
    # Default to environment configuration
    if provider is None:
        # If TTS_BASE_URL is set to something other than OpenAI, assume Kokoro
        if TTS_BASE_URL and "openai.com" not in TTS_BASE_URL:
            provider = "kokoro"
        else:
            provider = "openai"
    
    # Validate instructions usage
    if instructions and model != "gpt-4o-mini-tts":
        logger.warning(f"Instructions parameter is only supported with gpt-4o-mini-tts model, ignoring for model: {model}")
        instructions = None
    
    # Get provider info from registry
    provider_info = PROVIDERS.get(provider)
    if not provider_info:
        logger.warning(f"Unknown provider: {provider}, falling back to OpenAI")
        provider = "openai"
        provider_info = PROVIDERS["openai"]
    
    if provider == "kokoro":
        # Use kokoro-specific client if available, otherwise use default
        client_key = 'tts_kokoro' if 'tts_kokoro' in openai_clients else 'tts'
        return {
            'client_key': client_key,
            'base_url': provider_info.get("base_url", KOKORO_TTS_BASE_URL),
            'model': model or provider_info["models"][0],
            'voice': voice or provider_info["default_voice"],
            'instructions': None  # Kokoro doesn't support instructions
        }
    else:  # openai
        # Use openai-specific client if available, otherwise use default
        client_key = 'tts_openai' if 'tts_openai' in openai_clients else 'tts'
        logger.debug(f"OpenAI TTS config: client_key={client_key}, available_clients={list(openai_clients.keys())}")
        return {
            'client_key': client_key,
            'base_url': provider_info.get("base_url", OPENAI_TTS_BASE_URL),
            'model': model or TTS_MODEL,  # Use provided model or default
            'voice': voice or provider_info.get("default_voice", TTS_VOICE),
            'instructions': instructions  # Pass through instructions for OpenAI
        }


async def get_stt_config(provider: Optional[str] = None):
    """Get STT configuration based on provider selection"""
    # If no provider specified and PREFER_LOCAL is true, try local first
    if provider is None and PREFER_LOCAL:
        # Check if Whisper is available
        if await is_provider_available("whisper-local"):
            provider = "whisper-local"
            logger.info("Auto-selected Whisper.cpp (local) as STT provider")
        else:
            provider = "openai-whisper"
    
    # Default to environment configuration
    if provider is None:
        # If STT_BASE_URL is set to something other than OpenAI, assume local
        if STT_BASE_URL and "openai.com" not in STT_BASE_URL:
            provider = "whisper-local"
        else:
            provider = "openai-whisper"
    
    # Get provider info from registry
    provider_info = PROVIDERS.get(provider)
    if not provider_info:
        logger.warning(f"Unknown STT provider: {provider}, falling back to OpenAI")
        provider = "openai-whisper"
        provider_info = PROVIDERS["openai-whisper"]
    
    return {
        'client_key': 'stt',
        'base_url': provider_info.get("base_url", STT_BASE_URL),
        'model': STT_MODEL,  # All providers use whisper-1 compatible model
        'provider': provider
    }


def validate_emotion_request(tts_model: Optional[str], tts_instructions: Optional[str], tts_provider: Optional[str]) -> Optional[str]:
    """
    Validate if emotional TTS is allowed and appropriate.
    Returns the instructions if valid, None if emotions should be stripped.
    """
    # No emotion instructions provided
    if not tts_instructions:
        return tts_instructions
    
    # Check if this is an emotion-capable model request
    if tts_model == "gpt-4o-mini-tts":
        if not ALLOW_EMOTIONS:
            logger.warning("Emotional TTS requested but VOICE_ALLOW_EMOTIONS not enabled")
            return None  # Strip emotion instructions
        
        # Log provider switch if needed
        if tts_provider != "openai":
            logger.info("Switching to OpenAI for emotional speech support")
    
    return tts_instructions


async def speech_to_text(audio_data: np.ndarray, save_audio: bool = False, audio_dir: Optional[Path] = None) -> Optional[str]:
    """Convert audio to text"""
    logger.info(f"STT: Converting speech to text, audio data shape: {audio_data.shape}")
    if DEBUG:
        logger.debug(f"STT config - Model: {STT_MODEL}, Base URL: {STT_BASE_URL}")
        logger.debug(f"Audio stats - Min: {audio_data.min()}, Max: {audio_data.max()}, Mean: {audio_data.mean():.2f}")
    
    wav_file = None
    mp3_file = None
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_file_obj:
            wav_file = wav_file_obj.name
            logger.debug(f"Writing audio to WAV file: {wav_file}")
            write(wav_file, SAMPLE_RATE, audio_data)
        
            # Save debug file for original recording
            if DEBUG:
                try:
                    with open(wav_file, 'rb') as f:
                        debug_path = save_debug_file(f.read(), "stt-input", "wav", DEBUG_DIR, DEBUG)
                        if debug_path:
                            logger.info(f"STT debug recording saved to: {debug_path}")
                except Exception as e:
                    logger.error(f"Failed to save debug WAV: {e}")
            
            # Save audio file if audio saving is enabled
            if save_audio and audio_dir:
                try:
                    with open(wav_file, 'rb') as f:
                        audio_path = save_debug_file(f.read(), "stt", "wav", audio_dir, True)
                        if audio_path:
                            logger.info(f"STT audio saved to: {audio_path}")
                except Exception as e:
                    logger.error(f"Failed to save audio WAV: {e}")
        
        try:
            # Convert WAV to MP3 for smaller upload
            logger.debug("Converting WAV to MP3 for upload...")
            audio = AudioSegment.from_wav(wav_file)
            logger.debug(f"Audio loaded - Duration: {len(audio)}ms, Channels: {audio.channels}, Frame rate: {audio.frame_rate}")
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as mp3_file_obj:
                mp3_file = mp3_file_obj.name
                audio.export(mp3_file, format="mp3", bitrate="64k")
                upload_file = mp3_file
                logger.debug(f"MP3 created for STT upload: {upload_file}")
            
            # Save debug file for upload version
            if DEBUG:
                try:
                    with open(upload_file, 'rb') as f:
                        debug_path = save_debug_file(f.read(), "stt-upload", "mp3", DEBUG_DIR, DEBUG)
                        if debug_path:
                            logger.info(f"Upload audio saved to: {debug_path}")
                except Exception as e:
                    logger.error(f"Failed to save debug MP3: {e}")
            
            # Get file size for logging
            file_size = os.path.getsize(upload_file)
            logger.debug(f"Uploading {file_size} bytes to STT API...")
            
            with open(upload_file, 'rb') as audio_file:
                # Use async context manager if available, otherwise use regular create
                transcription = await openai_clients['stt'].audio.transcriptions.create(
                    model=STT_MODEL,
                    file=audio_file,
                    response_format="text"
                )
                
                logger.debug(f"STT API response type: {type(transcription)}")
                text = transcription.strip() if isinstance(transcription, str) else transcription.text.strip()
                
                if text:
                    logger.info(f"✓ STT result: '{text}'")
                    return text
                else:
                    logger.warning("STT returned empty text")
                    return None
                        
        except Exception as e:
            logger.error(f"STT failed: {e}")
            logger.error(f"STT config when error occurred - Model: {STT_MODEL}, Base URL: {STT_BASE_URL}")
            if hasattr(e, 'response'):
                logger.error(f"HTTP status: {e.response.status_code if hasattr(e.response, 'status_code') else 'unknown'}")
                logger.error(f"Response text: {e.response.text if hasattr(e.response, 'text') else 'unknown'}")
            return None
    finally:
        # Clean up temporary files
        if wav_file and os.path.exists(wav_file):
            try:
                os.unlink(wav_file)
                logger.debug(f"Cleaned up WAV file: {wav_file}")
            except Exception as e:
                logger.error(f"Failed to clean up WAV file: {e}")
        
        if mp3_file and os.path.exists(mp3_file):
            try:
                os.unlink(mp3_file)
                logger.debug(f"Cleaned up MP3 file: {mp3_file}")
            except Exception as e:
                logger.error(f"Failed to clean up MP3 file: {e}")


async def play_audio_feedback(text: str, openai_clients: dict, enabled: Optional[bool] = None, style: str = "whisper", feedback_type: Optional[str] = None) -> None:
    """Play an audio feedback sound
    
    Args:
        text: Text to speak (either "listening" or "finished")
        openai_clients: OpenAI client instances
        enabled: Override global audio feedback setting
        style: Audio style - "whisper" (default) or "shout"
        feedback_type: Override global feedback type ("chime", "voice", "both", "none")
    """
    # Use parameter override if provided, otherwise use global setting
    if enabled is False or (enabled is None and not AUDIO_FEEDBACK_ENABLED):
        return
    
    # Determine feedback type to use
    feedback_type = feedback_type or AUDIO_FEEDBACK_TYPE
    
    if feedback_type == "none":
        return
    
    try:
        # Play chime if requested
        if feedback_type in ("chime", "both"):
            if text == "listening":
                await play_chime_start()
            elif text == "finished":
                await play_chime_end()
        
        # Play voice if requested
        if feedback_type in ("voice", "both"):
            # Determine text and instructions based on style
            if style == "shout":
                feedback_text = text.upper()  # Convert to uppercase for emphasis
                instructions = "SHOUT this word loudly and enthusiastically!" if text == "listening" else "SHOUT this word loudly and triumphantly!"
            else:  # whisper is default
                feedback_text = text.lower()
                instructions = "Whisper this word very softly and gently, almost inaudibly"
            
            # Use OpenAI's TTS with style-specific instructions
            await text_to_speech(
                text=feedback_text,
                openai_clients=openai_clients,
                tts_model=AUDIO_FEEDBACK_MODEL,
                tts_voice=AUDIO_FEEDBACK_VOICE,
                tts_base_url=TTS_BASE_URL,
                debug=DEBUG,
                debug_dir=DEBUG_DIR if DEBUG else None,
                save_audio=False,  # Don't save feedback sounds
                audio_dir=None,
                client_key='tts',
                instructions=instructions
            )
    except Exception as e:
        logger.debug(f"Audio feedback failed: {e}")
        # Don't interrupt the main flow if feedback fails


def record_audio(duration: float) -> np.ndarray:
    """Record audio from microphone with intelligent silence detection"""
    logger.info(f"🎤 Recording audio with silence detection (max {duration}s)...")
    if DEBUG:
        try:
            devices = sd.query_devices()
            default_input = sd.default.device[0]
            logger.debug(f"Default input device: {default_input} - {devices[default_input]['name'] if default_input is not None else 'None'}")
            logger.debug(f"Recording config - Sample rate: {SAMPLE_RATE}Hz, Channels: {CHANNELS}, dtype: int16")
        except Exception as dev_e:
            logger.error(f"Error querying audio devices: {dev_e}")
    
    # Save current stdio state
    import sys
    original_stdin = sys.stdin
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    try:
        # Configuration for silence detection
        silence_threshold = 100  # RMS level below which we consider silence
        silence_duration = 4.0   # Seconds of silence before stopping
        chunk_size = int(SAMPLE_RATE * 0.1)  # 100ms chunks for real-time processing
        
        recording_data = []
        silence_start = None
        total_recorded = 0
        start_time = time.time()
        
        logger.debug(f"Starting real-time recording with {chunk_size} samples per chunk...")
        
        # Start recording in streaming mode
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=np.int16,
            blocksize=chunk_size
        ) as stream:
            
            while total_recorded < duration * SAMPLE_RATE:
                # Read next chunk
                chunk, overflowed = stream.read(chunk_size)
                if overflowed:
                    logger.warning("Audio buffer overflowed")
                
                chunk_flat = chunk.flatten()
                recording_data.append(chunk_flat)
                total_recorded += len(chunk_flat)
                
                # Calculate RMS for this chunk
                rms = np.sqrt(np.mean(chunk_flat.astype(float) ** 2))
                current_time = time.time()
                
                if DEBUG and len(recording_data) % 10 == 0:  # Log every second
                    logger.debug(f"Chunk RMS: {rms:.2f} ({'silence' if rms < silence_threshold else 'audio'})")
                
                # Check for silence
                if rms < silence_threshold:
                    if silence_start is None:
                        silence_start = current_time
                        logger.debug("Silence detected, starting timer...")
                    elif current_time - silence_start >= silence_duration:
                        logger.info(f"✓ Stopping after {silence_duration}s of silence")
                        break
                else:
                    # Audio detected, reset silence timer
                    if silence_start is not None:
                        logger.debug("Audio resumed, resetting silence timer")
                    silence_start = None
        
        # Combine all chunks
        flattened = np.concatenate(recording_data) if recording_data else np.array([])
        actual_duration = len(flattened) / SAMPLE_RATE
        logger.info(f"✓ Recorded {len(flattened)} samples ({actual_duration:.1f}s)")
        
        if DEBUG:
            logger.debug(f"Recording stats - Min: {flattened.min()}, Max: {flattened.max()}, Mean: {flattened.mean():.2f}")
            # Final RMS check
            final_rms = np.sqrt(np.mean(flattened.astype(float) ** 2))
            logger.debug(f"Final RMS level: {final_rms:.2f}")
        
        return flattened
        
    except Exception as e:
        logger.error(f"Recording failed: {e}")
        logger.error(f"Audio config when error occurred - Sample rate: {SAMPLE_RATE}, Channels: {CHANNELS}")
        
        # Try to get more info about audio devices
        try:
            devices = sd.query_devices()
            logger.error(f"Available input devices:")
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    logger.error(f"  {i}: {device['name']} (inputs: {device['max_input_channels']})")
        except Exception as dev_e:
            logger.error(f"Cannot query audio devices: {dev_e}")
        
        return np.array([])
    finally:
        # Restore stdio if it was changed
        if sys.stdin != original_stdin:
            sys.stdin = original_stdin
        if sys.stdout != original_stdout:
            sys.stdout = original_stdout
        if sys.stderr != original_stderr:
            sys.stderr = original_stderr


async def check_livekit_available() -> bool:
    """Check if LiveKit is available and has active rooms"""
    try:
        from livekit import api
        
        api_url = LIVEKIT_URL.replace("ws://", "http://").replace("wss://", "https://")
        lk_api = api.LiveKitAPI(api_url, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        
        rooms = await lk_api.room.list_rooms(api.ListRoomsRequest())
        active_rooms = [r for r in rooms.rooms if r.num_participants > 0]
        
        return len(active_rooms) > 0
        
    except Exception as e:
        logger.debug(f"LiveKit not available: {e}")
        return False


async def livekit_ask_voice_question(question: str, room_name: str = "", timeout: float = 60.0) -> str:
    """Ask voice question using LiveKit transport"""
    try:
        from livekit import rtc, api
        from livekit.agents import Agent, AgentSession
        from livekit.plugins import openai as lk_openai, silero
        
        # Auto-discover room if needed
        if not room_name:
            api_url = LIVEKIT_URL.replace("ws://", "http://").replace("wss://", "https://")
            lk_api = api.LiveKitAPI(api_url, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            
            rooms = await lk_api.room.list_rooms(api.ListRoomsRequest())
            for room in rooms.rooms:
                if room.num_participants > 0:
                    room_name = room.name
                    break
            
            if not room_name:
                return "No active LiveKit rooms found"
        
        # Setup TTS and STT for LiveKit
        tts_client = lk_openai.TTS(voice=TTS_VOICE, base_url=TTS_BASE_URL, model=TTS_MODEL)
        stt_client = lk_openai.STT(base_url=STT_BASE_URL, model=STT_MODEL)
        
        # Create simple agent that speaks and listens
        class VoiceAgent(Agent):
            def __init__(self):
                super().__init__(
                    instructions="Speak the message and listen for response",
                    stt=stt_client,
                    tts=tts_client,
                    llm=None
                )
                self.response = None
                self.has_spoken = False
            
            async def on_enter(self):
                await asyncio.sleep(0.5)
                if self.session:
                    await self.session.say(question, allow_interruptions=True)
                    self.has_spoken = True
            
            async def on_user_turn_completed(self, chat_ctx, new_message):
                if self.has_spoken and not self.response and new_message.content:
                    self.response = new_message.content[0]
        
        # Connect and run
        token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        token.with_identity("voice-mcp-bot").with_name("Voice MCP Bot")
        token.with_grants(api.VideoGrants(
            room_join=True, room=room_name,
            can_publish=True, can_subscribe=True,
        ))
        
        room = rtc.Room()
        await room.connect(LIVEKIT_URL, token.to_jwt())
        
        if not room.remote_participants:
            await room.disconnect()
            return "No participants in LiveKit room"
        
        agent = VoiceAgent()
        vad = silero.VAD.load()
        session = AgentSession(vad=vad)
        await session.start(room=room, agent=agent)
        
        # Wait for response
        start_time = time.time()
        while time.time() - start_time < timeout:
            if agent.response:
                await room.disconnect()
                return agent.response
            await asyncio.sleep(0.1)
        
        await room.disconnect()
        return f"No response within {timeout}s"
        
    except Exception as e:
        logger.error(f"LiveKit error: {e}")
        return f"LiveKit error: {str(e)}"


@mcp.tool()
async def converse(
    message: str,
    wait_for_response: bool = True,
    listen_duration: float = 15.0,
    transport: Literal["auto", "local", "livekit"] = "auto",
    room_name: str = "",
    timeout: float = 60.0,
    voice: Optional[str] = None,
    tts_provider: Optional[Literal["openai", "kokoro"]] = None,
    tts_model: Optional[str] = None,
    tts_instructions: Optional[str] = None,
    audio_feedback: Optional[bool] = None,
    audio_feedback_style: Optional[str] = None
) -> str:
    """Have a voice conversation - speak a message and optionally listen for response.
    
    PRIVACY NOTICE: When wait_for_response is True, this tool will access your microphone
    to record audio for speech-to-text conversion. Audio is processed using the configured
    STT service and is not permanently stored.
    
    Args:
        message: The message to speak
        wait_for_response: Whether to listen for a response after speaking (default: True)
        listen_duration: How long to listen for response in seconds (default: 15.0)
        transport: Transport method - "auto" (try LiveKit then local), "local" (direct mic), "livekit" (room-based)
        room_name: LiveKit room name (only for livekit transport, auto-discovered if empty)
        timeout: Maximum wait time for response in seconds (LiveKit only)
        voice: Override TTS voice (e.g., OpenAI: nova, shimmer; Kokoro: af_sky, af_sarah, am_adam, af_nicole, am_michael)
               IMPORTANT: Never use 'coral' voice. For Kokoro, always default to 'af_sky'
        tts_provider: TTS provider to use - "openai" or "kokoro" (auto-detects based on voice if not specified)
        tts_model: TTS model to use (e.g., OpenAI: tts-1, tts-1-hd, gpt-4o-mini-tts; Kokoro uses tts-1)
                   IMPORTANT: gpt-4o-mini-tts is BEST for emotional speech and should be used when expressing emotions
        tts_instructions: Tone/style instructions for gpt-4o-mini-tts model only (e.g., "Speak in a cheerful tone", "Sound angry", "Be extremely sad")
        audio_feedback: Override global audio feedback setting (default: None uses VOICE_MCP_AUDIO_FEEDBACK env var)
        audio_feedback_style: Audio feedback style - "whisper" (default) or "shout" (default: None uses VOICE_MCP_FEEDBACK_STYLE env var)
        If wait_for_response is False: Confirmation that message was spoken
        If wait_for_response is True: The voice response received (or error/timeout message)
    
    Examples:
        - Ask a question: converse("What's your name?")
        - Make a statement and wait: converse("Tell me more about that")
        - Just speak without waiting: converse("Goodbye!", wait_for_response=False)
        - Use HD model: converse("High quality speech", tts_model="tts-1-hd")
        
    Emotional Speech (requires VOICE_ALLOW_EMOTIONS=true and OpenAI API):
        - Excitement: converse("We did it!", tts_model="gpt-4o-mini-tts", tts_instructions="Sound extremely excited and celebratory")
        - Sadness: converse("I'm sorry for your loss", tts_model="gpt-4o-mini-tts", tts_instructions="Sound gentle and sympathetic")
        - Urgency: converse("Watch out!", tts_model="gpt-4o-mini-tts", tts_instructions="Sound urgent and concerned")
        - Humor: converse("That's hilarious!", tts_model="gpt-4o-mini-tts", tts_instructions="Sound amused and playful")
        
    Note: Emotional speech uses OpenAI's gpt-4o-mini-tts model and incurs API costs (~$0.02/minute)
    """
    logger.info(f"Converse: '{message[:50]}{'...' if len(message) > 50 else ''}' (wait_for_response: {wait_for_response})")
    
    # Run startup initialization if needed
    await startup_initialization()
    
    # Track execution time and resources
    start_time = time.time()
    if DEBUG:
        import resource
        start_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        logger.debug(f"Starting converse - Memory: {start_memory} KB")
    
    try:
        # If not waiting for response, just speak and return
        if not wait_for_response:
            try:
                async with audio_operation_lock:
                    # Validate emotion request
                    validated_instructions = validate_emotion_request(tts_model, tts_instructions, tts_provider)
                    tts_config = await get_tts_config(tts_provider, voice, tts_model, validated_instructions)
                    success, tts_metrics = await text_to_speech(
                        text=message,
                        openai_clients=openai_clients,
                        tts_model=tts_config['model'],
                        tts_base_url=tts_config['base_url'],
                        tts_voice=tts_config['voice'],
                        debug=DEBUG,
                        debug_dir=DEBUG_DIR if DEBUG else None,
                        save_audio=SAVE_AUDIO,
                        audio_dir=AUDIO_DIR if SAVE_AUDIO else None,
                        client_key=tts_config['client_key'],
                        instructions=tts_config.get('instructions')
                    )
                    
                # Include timing info if available
                timing_info = ""
                if success and tts_metrics:
                    timing_info = f" (gen: {tts_metrics.get('generation', 0):.1f}s, play: {tts_metrics.get('playback', 0):.1f}s)"
                
                result = f"✓ Message spoken successfully{timing_info}" if success else "✗ Failed to speak message"
                logger.info(f"Speak-only result: {result}")
                return result
            except Exception as e:
                logger.error(f"Speak error: {e}")
                error_msg = f"Error: {str(e)}"
                logger.error(f"Returning error: {error_msg}")
                return error_msg
        
        # Otherwise, speak and then listen for response
        # Determine transport method
        if transport == "auto":
            if await check_livekit_available():
                transport = "livekit"
                logger.info("Auto-selected LiveKit transport")
            else:
                transport = "local"
                logger.info("Auto-selected local transport")
        
        if transport == "livekit":
            # For LiveKit, use the existing function but with the message parameter
            return await livekit_ask_voice_question(message, room_name, timeout)
        
        elif transport == "local":
            # Local microphone approach with timing
            timings = {}
            try:
                async with audio_operation_lock:
                    # Speak the message
                    tts_start = time.perf_counter()
                    # Validate emotion request
                    validated_instructions = validate_emotion_request(tts_model, tts_instructions, tts_provider)
                    tts_config = await get_tts_config(tts_provider, voice, tts_model, validated_instructions)
                    tts_success, tts_metrics = await text_to_speech(
                        text=message,
                        openai_clients=openai_clients,
                        tts_model=tts_config['model'],
                        tts_base_url=tts_config['base_url'],
                        tts_voice=tts_config['voice'],
                        debug=DEBUG,
                        debug_dir=DEBUG_DIR if DEBUG else None,
                        save_audio=SAVE_AUDIO,
                        audio_dir=AUDIO_DIR if SAVE_AUDIO else None,
                        client_key=tts_config['client_key'],
                        instructions=tts_config.get('instructions')
                    )
                    
                    # Add TTS sub-metrics
                    if tts_metrics:
                        timings['tts_gen'] = tts_metrics.get('generation', 0)
                        timings['tts_play'] = tts_metrics.get('playback', 0)
                    timings['tts_total'] = time.perf_counter() - tts_start
                    
                    if not tts_success:
                        return "Error: Could not speak message"
                    
                    # Brief pause before listening
                    await asyncio.sleep(0.5)
                    
                    # Play "listening" feedback sound
                    await play_audio_feedback("listening", openai_clients, audio_feedback, audio_feedback_style or AUDIO_FEEDBACK_STYLE)
                    
                    # Record response
                    logger.info(f"🎤 Listening for {listen_duration} seconds...")
                    record_start = time.perf_counter()
                    audio_data = await asyncio.get_event_loop().run_in_executor(
                        None, record_audio, listen_duration
                    )
                    timings['record'] = time.perf_counter() - record_start
                    
                    # Play "finished" feedback sound
                    await play_audio_feedback("finished", openai_clients, audio_feedback, audio_feedback_style or AUDIO_FEEDBACK_STYLE)
                    
                    if len(audio_data) == 0:
                        return "Error: Could not record audio"
                    
                    # Convert to text
                    stt_start = time.perf_counter()
                    response_text = await speech_to_text(audio_data, SAVE_AUDIO, AUDIO_DIR if SAVE_AUDIO else None)
                    timings['stt'] = time.perf_counter() - stt_start
                
                # Calculate total time (use tts_total instead of sub-metrics)
                main_timings = {k: v for k, v in timings.items() if k in ['tts_total', 'record', 'stt']}
                total_time = sum(main_timings.values())
                
                # Format timing string with sub-metrics
                timing_parts = []
                if 'tts_gen' in timings:
                    timing_parts.append(f"tts_gen {timings['tts_gen']:.1f}s")
                if 'tts_play' in timings:
                    timing_parts.append(f"tts_play {timings['tts_play']:.1f}s")
                if 'tts_total' in timings:
                    timing_parts.append(f"tts_total {timings['tts_total']:.1f}s")
                if 'record' in timings:
                    timing_parts.append(f"record {timings['record']:.1f}s")
                if 'stt' in timings:
                    timing_parts.append(f"stt {timings['stt']:.1f}s")
                
                timing_str = ", ".join(timing_parts)
                timing_str += f", total {total_time:.1f}s"
                
                if response_text:
                    return f"Voice response: {response_text} | Timing: {timing_str}"
                else:
                    return f"No speech detected | Timing: {timing_str}"
                    
            except Exception as e:
                logger.error(f"Local voice error: {e}")
                if DEBUG:
                    logger.error(f"Traceback: {traceback.format_exc()}")
                return f"Error: {str(e)}"
            
        else:
            return f"Unknown transport: {transport}"
            
    except Exception as e:
        logger.error(f"Unexpected error in converse: {e}")
        if DEBUG:
            logger.error(f"Full traceback: {traceback.format_exc()}")
        return f"Unexpected error: {str(e)}"
        
    finally:
        # Log execution metrics
        elapsed = time.time() - start_time
        logger.info(f"Converse completed in {elapsed:.2f}s")
        
        if DEBUG:
            import resource
            import gc
            end_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            memory_delta = end_memory - start_memory
            logger.debug(f"Memory delta: {memory_delta} KB (start: {start_memory}, end: {end_memory})")
            
            # Force garbage collection
            collected = gc.collect()
            logger.debug(f"Garbage collected {collected} objects")


@mcp.tool()
async def ask_voice_question(
    question: str,
    duration: float = 15.0,
    voice: Optional[str] = None,
    tts_provider: Optional[Literal["openai", "kokoro"]] = None,
    tts_model: Optional[str] = None,
    tts_instructions: Optional[str] = None
) -> str:
    """Ask a voice question and listen for the answer.
    
    PRIVACY NOTICE: This tool will access your microphone to record audio
    for speech-to-text conversion. Audio is processed using the configured
    STT service and is not permanently stored.
    
    Args:
        question: The question to ask
        duration: How long to listen for response in seconds (default: 15.0)
        voice: Override TTS voice (e.g., OpenAI: nova, shimmer; Kokoro: af_sky)
        tts_provider: TTS provider to use - "openai" or "kokoro"
        tts_model: TTS model to use (e.g., tts-1, tts-1-hd, gpt-4o-mini-tts)
        tts_instructions: Tone/style instructions for gpt-4o-mini-tts model only
    
    Returns:
        The voice response received
    
    This is a convenience wrapper around converse() for backward compatibility.
    """
    return await converse(
        message=question,
        wait_for_response=True,
        listen_duration=duration,
        voice=voice,
        tts_provider=tts_provider,
        tts_model=tts_model,
        tts_instructions=tts_instructions
    )


@mcp.tool()
async def voice_chat(
    initial_message: Optional[str] = None,
    max_turns: int = 10,
    listen_duration: float = 15.0,
    voice: Optional[str] = None,
    tts_provider: Optional[Literal["openai", "kokoro"]] = None
) -> str:
    """Start an interactive voice chat session.
    
    PRIVACY NOTICE: This tool will access your microphone for the duration
    of the chat session. Say "goodbye", "exit", or "end chat" to stop.
    
    Args:
        initial_message: Optional greeting to start the conversation
        max_turns: Maximum number of conversation turns (default: 10)
        listen_duration: How long to listen each turn in seconds (default: 15.0)
        voice: Override TTS voice
        tts_provider: TTS provider to use - "openai" or "kokoro"
    
    Returns:
        Summary of the conversation
    
    Note: This is a simplified version. The full voice-chat command provides
    a more interactive experience with the LLM handling the conversation flow.
    """
    transcript = []
    
    # Start with initial message if provided
    if initial_message:
        result = await converse(
            message=initial_message,
            wait_for_response=True,
            listen_duration=listen_duration,
            voice=voice,
            tts_provider=tts_provider
        )
        transcript.append(f"Assistant: {initial_message}")
        if "Voice response:" in result:
            user_response = result.split("Voice response:")[1].split("|")[0].strip()
            transcript.append(f"User: {user_response}")
            
            # Check for exit phrases
            exit_phrases = ["goodbye", "exit", "end chat", "stop", "quit"]
            if any(phrase in user_response.lower() for phrase in exit_phrases):
                return "\n".join(transcript) + "\n\nChat ended by user."
    
    # Continue conversation for remaining turns
    turns_remaining = max_turns - (1 if initial_message else 0)
    
    return f"Voice chat started. Use the converse tool in a loop to continue the conversation.\n\nTranscript so far:\n" + "\n".join(transcript)