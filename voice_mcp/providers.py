"""
Provider registry for voice-mcp.

This module manages the configuration and selection of voice service providers,
supporting both cloud and local STT/TTS services with transparent fallback.
"""

import logging
import os
import tempfile
import struct
from typing import Dict, Optional, List, Any
from pathlib import Path
import httpx
import asyncio

logger = logging.getLogger("voice-mcp")


class GeminiTTSProvider:
    """Gemini TTS provider using Google AI Studio API."""
    
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Import here to avoid dependency issues if not using Gemini
        try:
            from google import genai
            from google.genai import types
            self.genai = genai
            self.types = types
        except ImportError:
            raise ImportError("google-genai package is required for Gemini TTS. Install with: pip install google-genai")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
        self.voice = os.environ.get("TTS_VOICE", "Zephyr")
        self.system_prompt = os.environ.get("GEMINI_SYSTEM_PROMPT", "Speak naturally and clearly.")
    
    async def generate_speech(
        self, 
        text: str, 
        voice: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> Path:
        """
        Generate speech from text using Gemini TTS.
        
        Args:
            text: Text to convert to speech
            voice: Voice name to use (overrides default)
            model: Model to use (overrides default)
            system_prompt: Custom system prompt (overrides default)
            
        Returns:
            Path to generated audio file
        """
        try:
            # Use provided parameters or defaults
            voice_name = voice or self.voice
            model_name = model or self.model
            prompt = system_prompt or self.system_prompt
            
            # Construct the full prompt with system instructions
            full_text = f"{prompt} {text}" if prompt else text
            
            logger.debug(f"Generating Gemini TTS: model={model_name}, voice={voice_name}")
            
            # Create content for Gemini
            contents = [
                self.types.Content(
                    role="user",
                    parts=[self.types.Part.from_text(text=full_text)],
                ),
            ]
            
            # Configure generation
            config = self.types.GenerateContentConfig(
                temperature=1,
                response_modalities=["audio"],
                speech_config=self.types.SpeechConfig(
                    voice_config=self.types.VoiceConfig(
                        prebuilt_voice_config=self.types.PrebuiltVoiceConfig(
                            voice_name=voice_name
                        )
                    )
                ),
            )
            
            # Generate audio stream
            audio_chunks = []
            for chunk in self.client.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=config,
            ):
                if (
                    chunk.candidates is None
                    or chunk.candidates[0].content is None
                    or chunk.candidates[0].content.parts is None
                ):
                    continue
                
                part = chunk.candidates[0].content.parts[0]
                if part.inline_data and part.inline_data.data:
                    audio_chunks.append(part.inline_data.data)
            
            if not audio_chunks:
                raise RuntimeError("No audio data received from Gemini API")
            
            # Combine all audio chunks
            combined_audio = b''.join(audio_chunks)
            
            # Create temporary file for audio
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, 
                suffix='.wav',
                prefix='gemini_tts_'
            )
            
            # Convert to WAV format if needed
            wav_data = self._convert_to_wav(combined_audio, "audio/L16;rate=24000")
            temp_file.write(wav_data)
            temp_file.close()
            
            logger.info(f"Generated Gemini TTS audio: {temp_file.name}")
            return Path(temp_file.name)
            
        except Exception as e:
            logger.error(f"Gemini TTS generation failed: {e}")
            raise
    
    def _convert_to_wav(self, audio_data: bytes, mime_type: str) -> bytes:
        """
        Convert audio data to WAV format.
        
        Args:
            audio_data: Raw audio data
            mime_type: MIME type of the audio data
            
        Returns:
            WAV-formatted audio data
        """
        parameters = self._parse_audio_mime_type(mime_type)
        bits_per_sample = parameters["bits_per_sample"]
        sample_rate = parameters["rate"]
        num_channels = 1
        data_size = len(audio_data)
        bytes_per_sample = bits_per_sample // 8
        block_align = num_channels * bytes_per_sample
        byte_rate = sample_rate * block_align
        chunk_size = 36 + data_size  # 36 bytes for header fields before data chunk size

        # Create WAV header
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",          # ChunkID
            chunk_size,       # ChunkSize (total file size - 8 bytes)
            b"WAVE",          # Format
            b"fmt ",          # Subchunk1ID
            16,               # Subchunk1Size (16 for PCM)
            1,                # AudioFormat (1 for PCM)
            num_channels,     # NumChannels
            sample_rate,      # SampleRate
            byte_rate,        # ByteRate
            block_align,      # BlockAlign
            bits_per_sample,  # BitsPerSample
            b"data",          # Subchunk2ID
            data_size         # Subchunk2Size (size of audio data)
        )
        return header + audio_data

    def _parse_audio_mime_type(self, mime_type: str) -> Dict[str, int]:
        """
        Parse audio parameters from MIME type.
        
        Args:
            mime_type: Audio MIME type string
            
        Returns:
            Dictionary with bits_per_sample and rate
        """
        bits_per_sample = 16
        rate = 24000

        # Extract rate from parameters
        parts = mime_type.split(";")
        for param in parts:
            param = param.strip()
            if param.lower().startswith("rate="):
                try:
                    rate_str = param.split("=", 1)[1]
                    rate = int(rate_str)
                except (ValueError, IndexError):
                    pass  # Keep rate as default
            elif param.startswith("audio/L"):
                try:
                    bits_per_sample = int(param.split("L", 1)[1])
                except (ValueError, IndexError):
                    pass  # Keep bits_per_sample as default

        return {"bits_per_sample": bits_per_sample, "rate": rate}
    
    def get_available_voices(self) -> list[str]:
        """Get list of available Gemini voices."""
        return [
            "Aoede", "Callisto", "Charon", "Deimos", "Echo", "Europa",
            "Fenrir", "Ganymede", "Hera", "Io", "Kore", "Lunara",
            "Minerva", "Naia", "Nova", "Oberon", "Phobos", "Quorra",
            "Rhea", "Selene", "Titan", "Umbra", "Vega", "Whisper",
            "Xara", "Yuki", "Zephyr", "Astra", "Cypher", "Delta"
        ]
    
    def get_available_models(self) -> list[str]:
        """Get list of available Gemini models."""
        return [
            "gemini-2.5-flash-preview-tts",
            "gemini-2.5-pro-preview-tts"
        ]
    
    def is_available(self) -> bool:
        """Check if Gemini TTS is available."""
        return bool(self.api_key)


# Provider Registry with basic metadata
PROVIDERS = {
    "kokoro": {
        "id": "kokoro",
        "name": "Kokoro TTS", 
        "type": "tts",
        "base_url": "http://localhost:8880/v1",
        "local": True,
        "auto_start": True,
        "features": ["local", "free", "fast"],
        "default_voice": "af_sky",
        "voices": ["af_sky", "af_sarah", "am_adam", "af_nicole", "am_michael"],
        "models": ["tts-1"],  # OpenAI-compatible model name
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI TTS",
        "type": "tts", 
        "base_url": "https://api.openai.com/v1",
        "local": False,
        "features": ["cloud", "emotions", "multi-model"],
        "default_voice": "alloy",
        "voices": ["alloy", "nova", "echo", "fable", "onyx", "shimmer"],
        "models": ["tts-1", "tts-1-hd", "gpt-4o-mini-tts"],
    },
    "whisper-local": {
        "id": "whisper-local",
        "name": "Whisper.cpp",
        "type": "stt",
        "base_url": "http://localhost:2022/v1", 
        "local": True,
        "features": ["local", "free", "accurate"],
        "models": ["whisper-1"],  # OpenAI-compatible model name
    },
    "openai-whisper": {
        "id": "openai-whisper",
        "name": "OpenAI Whisper",
        "type": "stt",
        "base_url": "https://api.openai.com/v1",
        "local": False,
        "features": ["cloud", "fast", "reliable"],
        "models": ["whisper-1"],
    },
    "gemini": {
        "id": "gemini",
        "name": "Gemini AI Studio TTS",
        "type": "tts",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "local": False,
        "features": ["cloud", "multi-speaker", "emotions", "multi-language", "custom-prompts"],
        "default_voice": "Zephyr",
        "voices": [
            "Aoede", "Callisto", "Charon", "Deimos", "Echo", "Europa",
            "Fenrir", "Ganymede", "Hera", "Io", "Kore", "Lunara",
            "Minerva", "Naia", "Nova", "Oberon", "Phobos", "Quorra",
            "Rhea", "Selene", "Titan", "Umbra", "Vega", "Whisper",
            "Xara", "Yuki", "Zephyr", "Astra", "Cypher", "Delta"
        ],
        "models": ["gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"],
        "default_model": "gemini-2.5-flash-preview-tts",
    }
}


async def is_provider_available(provider_id: str, timeout: float = 2.0) -> bool:
    """Check if a provider is reachable via health check or basic connectivity."""
    provider = PROVIDERS.get(provider_id)
    if not provider:
        return False
    
    base_url = provider["base_url"]
    
    # Skip health check for cloud providers
    if not provider.get("local", False):
        # For cloud providers, we assume they're available
        # Real availability will be checked during actual API calls
        return True
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Try OpenAI-compatible models endpoint first
            try:
                response = await client.get(f"{base_url}/models")
                if response.status_code == 200:
                    logger.debug(f"Provider {provider_id} is available (models endpoint)")
                    return True
            except:
                pass
            
            # Try health endpoint as fallback
            try:
                response = await client.get(f"{base_url}/health")
                if response.status_code == 200:
                    logger.debug(f"Provider {provider_id} is available (health endpoint)")
                    return True
            except:
                pass
            
            # Try base URL
            try:
                response = await client.get(base_url)
                if response.status_code < 500:  # Any non-server-error response
                    logger.debug(f"Provider {provider_id} is available (base URL)")
                    return True
            except:
                pass
                
    except Exception as e:
        logger.debug(f"Provider {provider_id} not available: {e}")
    
    return False


async def get_available_providers(provider_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all available providers of a specific type."""
    providers = []
    
    for provider_id, provider in PROVIDERS.items():
        # Filter by type if specified
        if provider_type and provider["type"] != provider_type:
            continue
            
        # Check availability
        if await is_provider_available(provider_id):
            providers.append(provider)
    
    return providers


async def get_tts_provider(prefer_local: bool = True, require_emotions: bool = False) -> Optional[Dict[str, Any]]:
    """
    Get the best available TTS provider based on requirements.
    
    Args:
        prefer_local: Prefer local providers over cloud
        require_emotions: Require emotion support (forces OpenAI)
        
    Returns:
        Provider configuration dict or None if no suitable provider found
    """
    # If emotions are required, only OpenAI will work
    if require_emotions:
        if await is_provider_available("openai"):
            return PROVIDERS["openai"]
        return None
    
    # Get available TTS providers
    available = await get_available_providers("tts")
    
    if not available:
        return None
    
    # Sort by preference
    if prefer_local:
        # Prefer local providers
        available.sort(key=lambda p: (not p.get("local", False), p["id"]))
    else:
        # Prefer cloud providers
        available.sort(key=lambda p: (p.get("local", False), p["id"]))
    
    return available[0]


async def get_stt_provider(prefer_local: bool = True) -> Optional[Dict[str, Any]]:
    """
    Get the best available STT provider.
    
    Args:
        prefer_local: Prefer local providers over cloud
        
    Returns:
        Provider configuration dict or None if no suitable provider found
    """
    # Get available STT providers
    available = await get_available_providers("stt")
    
    if not available:
        return None
    
    # Sort by preference
    if prefer_local:
        # Prefer local providers
        available.sort(key=lambda p: (not p.get("local", False), p["id"]))
    else:
        # Prefer cloud providers
        available.sort(key=lambda p: (p.get("local", False), p["id"]))
    
    return available[0]


def get_provider_by_voice(voice: str) -> Optional[Dict[str, Any]]:
    """Get provider based on voice selection."""
    # Kokoro voices start with af_ or am_
    if voice.startswith(('af_', 'am_', 'bf_', 'bm_')):
        return PROVIDERS.get("kokoro")
    
    # Gemini voices (named after celestial bodies and mythological names)
    gemini_voices = [
        "Aoede", "Callisto", "Charon", "Deimos", "Echo", "Europa",
        "Fenrir", "Ganymede", "Hera", "Io", "Kore", "Lunara",
        "Minerva", "Naia", "Nova", "Oberon", "Phobos", "Quorra",
        "Rhea", "Selene", "Titan", "Umbra", "Vega", "Whisper",
        "Xara", "Yuki", "Zephyr", "Astra", "Cypher", "Delta"
    ]
    if voice in gemini_voices:
        return PROVIDERS.get("gemini")
    
    # Default to OpenAI for standard voices
    return PROVIDERS.get("openai")


def get_provider_display_status(provider: Dict[str, Any], is_available: bool) -> List[str]:
    """Get formatted status display for a provider."""
    status_lines = []
    
    emoji = "✅" if is_available else "❌"
    status = "Available" if is_available else "Unavailable"
    
    status_lines.append(f"{emoji} {provider['name']} ({status})")
    status_lines.append(f"   Type: {provider['type'].upper()}")
    status_lines.append(f"   Local: {'Yes' if provider.get('local') else 'No'}")
    
    if provider['type'] == 'tts' and 'voices' in provider:
        status_lines.append(f"   Voices: {len(provider['voices'])}")
    
    if 'features' in provider:
        status_lines.append(f"   Features: {', '.join(provider['features'])}")
    
    return status_lines