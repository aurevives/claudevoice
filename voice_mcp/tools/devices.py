"""Audio device management tools."""

import logging
from typing import Optional
import sounddevice as sd

from voice_mcp.server_new import mcp
from voice_mcp.shared import startup_initialization

logger = logging.getLogger("voice-mcp")


@mcp.tool()
async def check_audio_devices() -> str:
    """List available audio input and output devices"""
    try:
        devices = sd.query_devices()
        input_devices = []
        output_devices = []
        
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append(f"  [{i}] {device['name']} ({device['max_input_channels']} channels)")
            if device['max_output_channels'] > 0:
                output_devices.append(f"  [{i}] {device['name']} ({device['max_output_channels']} channels)")
        
        default_input = sd.query_devices(kind='input')
        default_output = sd.query_devices(kind='output')
        
        result = []
        result.append("Audio Devices:")
        result.append(f"\nDefault Input: [{default_input['index']}] {default_input['name']}")
        result.append(f"Default Output: [{default_output['index']}] {default_output['name']}")
        
        result.append("\n\nInput Devices:")
        result.extend(input_devices)
        
        result.append("\n\nOutput Devices:")
        result.extend(output_devices)
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error listing audio devices: {e}")
        return f"Error listing audio devices: {str(e)}"


@mcp.tool()
async def voice_status() -> str:
    """Check the status of all voice services including TTS, STT, LiveKit, and audio devices.
    
    Provides a unified view of the voice infrastructure configuration and health.
    """
    from voice_mcp.providers import get_provider_display_status, is_provider_available
    
    try:
        status_lines = ["Voice Service Status:"]
        status_lines.append("=" * 50)
        
        # Provider status
        from voice_mcp.providers import PROVIDERS
        status_lines.append("\nProvider Status:")
        for provider_id in ["openai", "kokoro", "gemini"]:
            provider = PROVIDERS.get(provider_id)
            if provider:
                available = await is_provider_available(provider_id)
                status = get_provider_display_status(provider, available)
                for line in status:
                    status_lines.append(f"  {line}")
        
        # Configuration
        from voice_mcp.shared import (
            TTS_VOICE, TTS_MODEL, STT_MODEL, 
            PREFER_LOCAL, ALLOW_EMOTIONS, AUTO_START_KOKORO,
            AUDIO_FEEDBACK_ENABLED, LIVEKIT_URL
        )
        
        status_lines.append("\nConfiguration:")
        status_lines.append(f"  TTS Voice: {TTS_VOICE}")
        status_lines.append(f"  TTS Model: {TTS_MODEL}")
        status_lines.append(f"  STT Model: {STT_MODEL}")
        status_lines.append(f"  Prefer Local: {PREFER_LOCAL}")
        status_lines.append(f"  Allow Emotions: {ALLOW_EMOTIONS}")
        status_lines.append(f"  Auto-start Kokoro: {AUTO_START_KOKORO}")
        status_lines.append(f"  Audio Feedback: {AUDIO_FEEDBACK_ENABLED}")
        status_lines.append(f"  LiveKit URL: {LIVEKIT_URL}")
        
        # Audio devices
        try:
            default_input = sd.query_devices(kind='input')
            default_output = sd.query_devices(kind='output')
            status_lines.append("\nAudio Devices:")
            status_lines.append(f"  Input: {default_input['name']}")
            status_lines.append(f"  Output: {default_output['name']}")
        except:
            status_lines.append("\nAudio Devices: Unable to query")
        
        return "\n".join(status_lines)
        
    except Exception as e:
        logger.error(f"Error getting voice status: {e}")
        return f"Error getting voice status: {str(e)}"


@mcp.tool()
async def list_tts_voices(provider: Optional[str] = None) -> str:
    """List available TTS voices for different providers.
    
    Args:
        provider: Optional provider name ('openai' or 'kokoro'). If not specified, lists all available voices.
    
    Returns:
        A formatted list of available voices by provider.
    """
    await startup_initialization()
    
    results = []
    results.append("🔊 AVAILABLE TTS VOICES")
    results.append("=" * 40)
    
    # Determine which providers to check
    providers_to_check = []
    if provider:
        if provider.lower() not in ['openai', 'kokoro']:
            return f"Error: Unknown provider '{provider}'. Valid options: 'openai', 'kokoro'"
        providers_to_check = [provider.lower()]
    else:
        providers_to_check = ['openai', 'kokoro']
    
    # OpenAI voices
    if 'openai' in providers_to_check:
        results.append("\n📢 OpenAI Voices")
        results.append("-" * 40)
        
        # Standard voices (work with all models)
        results.append("\n**Standard Voices** (tts-1, tts-1-hd):")
        standard_voices = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
        for voice in standard_voices:
            results.append(f"  • {voice}")
        
        # Enhanced voices for gpt-4o-mini-tts
        results.append("\n**Enhanced Voices** (gpt-4o-mini-tts):")
        enhanced_voices = ['alloy', 'echo', 'shimmer']
        for voice in enhanced_voices:
            results.append(f"  • {voice} - supports emotional expression")
        
        results.append("\n**Voice Characteristics**:")
        voice_descriptions = {
            'alloy': 'Natural and conversational (default)',
            'echo': 'Smooth and conversational', 
            'fable': 'British accent, authoritative',
            'onyx': 'Deep and authoritative',
            'nova': 'Warm and friendly',
            'shimmer': 'Expressive and engaging'
        }
        for voice, desc in voice_descriptions.items():
            results.append(f"  • {voice}: {desc}")
    
    # Kokoro voices
    if 'kokoro' in providers_to_check:
        results.append("\n\n🎭 Kokoro Voices")
        results.append("-" * 40)
        
        # Default voice descriptions
        kokoro_voice_descriptions = {
            'af_sky': 'Female - Natural and expressive (recommended)',
            'af_sarah': 'Female - Warm and friendly',
            'am_adam': 'Male - Clear and professional',
            'af_nicole': 'Female - Energetic and upbeat',
            'am_michael': 'Male - Deep and authoritative',
            'bf_emma': 'British Female - Sophisticated accent',
            'bm_george': 'British Male - Distinguished accent'
        }
        
        results.append("\n**Available Voices**:")
        for voice, desc in kokoro_voice_descriptions.items():
            results.append(f"  • {voice}: {desc}")
        
        results.append("\n**Voice Naming**:")
        results.append("  • af_ = American Female")
        results.append("  • am_ = American Male")
        results.append("  • bf_ = British Female")
        results.append("  • bm_ = British Male")
    
    return "\n".join(results)