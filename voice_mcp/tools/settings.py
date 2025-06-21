"""
Settings management tools for Voice MCP.
"""

import logging
from typing import Optional, List
from voice_mcp.server import mcp
from voice_mcp.settings import settings_manager

logger = logging.getLogger("voice-mcp")

@mcp.tool()
async def get_voice_settings() -> str:
    """
    Get current voice settings configuration.
    
    Returns:
        Formatted display of all current voice settings.
    """
    settings = settings_manager.load_settings()
    
    result = []
    result.append("🎙️ CURRENT VOICE SETTINGS")
    result.append("=" * 50)
    
    result.append("\n🔊 TEXT-TO-SPEECH:")
    result.append(f"  Provider: {settings.tts_provider}")
    result.append(f"  Voice: {settings.tts_voice}")
    result.append(f"  Model: {settings.tts_model}")
    
    result.append("\n🗣️ SPEECH-TO-TEXT:")
    result.append(f"  Provider: {settings.stt_provider}")
    result.append(f"  Model: {settings.stt_model}")
    
    result.append("\n⏱️ CONVERSATION:")
    result.append(f"  Silence timeout: {settings.silence_timeout}s")
    result.append(f"  Max listen duration: {settings.listen_duration}s")
    
    result.append("\n🔧 AUDIO & OPTIONS:")
    result.append(f"  Audio feedback: {settings.audio_feedback}")
    result.append(f"  Allow emotions: {settings.allow_emotions}")
    result.append(f"  Auto-start Kokoro: {settings.auto_start_kokoro}")
    result.append(f"  Prefer local: {settings.prefer_local}")
    
    if settings.last_updated:
        result.append(f"\n📅 Last updated: {settings.last_updated[:19]}")
    
    return "\n".join(result)

@mcp.tool()
async def set_tts_provider(provider: str) -> str:
    """
    Set the TTS (Text-to-Speech) provider.
    
    Args:
        provider: TTS provider to use ("openai" or "kokoro")
    
    Returns:
        Confirmation message.
    """
    if provider not in ["openai", "kokoro"]:
        return "❌ Invalid TTS provider. Use 'openai' or 'kokoro'."
    
    success = settings_manager.update_setting('tts_provider', provider)
    if success:
        return f"✅ TTS provider set to: {provider}"
    else:
        return "❌ Failed to update TTS provider."

@mcp.tool()
async def set_tts_voice(voice: str) -> str:
    """
    Set the TTS voice.
    
    Args:
        voice: Voice name to use (e.g., "nova", "alloy" for OpenAI; "af_sky", "af_sarah" for Kokoro)
    
    Returns:
        Confirmation message.
    """
    success = settings_manager.update_setting('tts_voice', voice)
    if success:
        return f"✅ TTS voice set to: {voice}"
    else:
        return "❌ Failed to update TTS voice."

@mcp.tool()
async def set_stt_provider(provider: str) -> str:
    """
    Set the STT (Speech-to-Text) provider.
    
    Args:
        provider: STT provider to use ("openai" for API or "local" for Whisper.cpp)
    
    Returns:
        Confirmation message.
    """
    if provider not in ["openai", "local"]:
        return "❌ Invalid STT provider. Use 'openai' or 'local'."
    
    success = settings_manager.update_setting('stt_provider', provider)
    if success:
        return f"✅ STT provider set to: {provider}"
    else:
        return "❌ Failed to update STT provider."

@mcp.tool()
async def set_silence_timeout(timeout: float) -> str:
    """
    Set the silence timeout (how long to wait before stopping recording).
    
    Args:
        timeout: Timeout in seconds (e.g., 2.0, 5.0, 10.0)
    
    Returns:
        Confirmation message.
    """
    if timeout <= 0 or timeout > 60:
        return "❌ Silence timeout must be between 0.1 and 60 seconds."
    
    success = settings_manager.update_setting('silence_timeout', timeout)
    if success:
        return f"✅ Silence timeout set to: {timeout}s"
    else:
        return "❌ Failed to update silence timeout."

@mcp.tool()
async def set_listen_duration(duration: float) -> str:
    """
    Set the maximum listen duration (fallback timeout).
    
    Args:
        duration: Duration in seconds (e.g., 60, 120, 180)
    
    Returns:
        Confirmation message.
    """
    if duration < 5 or duration > 600:
        return "❌ Listen duration must be between 5 and 600 seconds."
    
    success = settings_manager.update_setting('listen_duration', duration)
    if success:
        return f"✅ Listen duration set to: {duration}s"
    else:
        return "❌ Failed to update listen duration."

@mcp.tool()
async def set_audio_feedback(feedback: str) -> str:
    """
    Set the audio feedback type.
    
    Args:
        feedback: Feedback type ("chime", "voice", "both", "none")
    
    Returns:
        Confirmation message.
    """
    if feedback not in ["chime", "voice", "both", "none"]:
        return "❌ Invalid audio feedback. Use 'chime', 'voice', 'both', or 'none'."
    
    success = settings_manager.update_setting('audio_feedback', feedback)
    if success:
        return f"✅ Audio feedback set to: {feedback}"
    else:
        return "❌ Failed to update audio feedback."

@mcp.tool()
async def set_allow_emotions(allow: bool) -> str:
    """
    Enable or disable emotional TTS (requires OpenAI gpt-4o-mini-tts model).
    
    Args:
        allow: True to enable emotions, False to disable
    
    Returns:
        Confirmation message.
    """
    success = settings_manager.update_setting('allow_emotions', allow)
    if success:
        status = "enabled" if allow else "disabled"
        return f"✅ Emotional TTS {status}"
    else:
        return "❌ Failed to update emotion setting."

@mcp.tool()
async def get_available_voices() -> str:
    """
    Get list of available voices for each TTS provider.
    
    Returns:
        List of available voices grouped by provider.
    """
    result = []
    result.append("🎵 AVAILABLE VOICES")
    result.append("=" * 40)
    
    result.append("\n🤖 OPENAI TTS:")
    openai_voices = ["alloy", "echo", "fable", "nova", "onyx", "shimmer"]
    for voice in openai_voices:
        result.append(f"  • {voice}")
    
    result.append("\n🏠 KOKORO TTS (Local):")
    kokoro_voices = ["af_sky", "af_sarah", "am_adam", "af_nicole", "am_michael"]
    for voice in kokoro_voices:
        result.append(f"  • {voice}")
    
    result.append("\n💡 USAGE:")
    result.append("Use set_tts_voice('voice_name') to change voice")
    result.append("Use set_tts_provider('openai' or 'kokoro') to change provider")
    
    return "\n".join(result)

@mcp.tool()
async def reset_voice_settings() -> str:
    """
    Reset all voice settings to default values.
    
    Returns:
        Confirmation message.
    """
    try:
        # Delete settings file to force defaults
        if settings_manager.settings_file.exists():
            settings_manager.settings_file.unlink()
        
        # Clear cached settings
        settings_manager._settings = None
        
        # Reload and apply defaults
        settings_manager.load_settings()
        settings_manager.apply_to_environment()
        
        return "✅ Voice settings reset to defaults."
        
    except Exception as e:
        logger.error(f"Failed to reset settings: {e}")
        return f"❌ Failed to reset settings: {str(e)}"

@mcp.tool()
async def quick_setup_local() -> str:
    """
    Quick setup for local voice processing (Kokoro TTS + Whisper STT).
    
    Returns:
        Setup confirmation message.
    """
    try:
        settings_manager.update_setting('tts_provider', 'kokoro')
        settings_manager.update_setting('tts_voice', 'af_sky')
        settings_manager.update_setting('stt_provider', 'local')
        settings_manager.update_setting('auto_start_kokoro', True)
        settings_manager.update_setting('prefer_local', True)
        
        return "✅ QUICK SETUP: Local processing configured (Kokoro TTS + Whisper STT)"
        
    except Exception as e:
        return f"❌ Failed to setup local configuration: {str(e)}"

@mcp.tool()
async def quick_setup_cloud() -> str:
    """
    Quick setup for cloud voice processing (OpenAI TTS + STT).
    
    Returns:
        Setup confirmation message.
    """
    try:
        settings_manager.update_setting('tts_provider', 'openai')
        settings_manager.update_setting('tts_voice', 'nova')
        settings_manager.update_setting('stt_provider', 'openai')
        settings_manager.update_setting('allow_emotions', True)
        settings_manager.update_setting('prefer_local', False)
        
        return "✅ QUICK SETUP: Cloud processing configured (OpenAI TTS + STT)"
        
    except Exception as e:
        return f"❌ Failed to setup cloud configuration: {str(e)}"

@mcp.tool()
async def quick_setup_hybrid() -> str:
    """
    Quick setup for hybrid processing (OpenAI TTS + Local Whisper STT).
    
    Returns:
        Setup confirmation message.
    """
    try:
        settings_manager.update_setting('tts_provider', 'openai')
        settings_manager.update_setting('tts_voice', 'nova')
        settings_manager.update_setting('stt_provider', 'local')
        settings_manager.update_setting('allow_emotions', True)
        settings_manager.update_setting('prefer_local', True)
        
        return "✅ QUICK SETUP: Hybrid processing configured (OpenAI TTS + Local Whisper STT)"
        
    except Exception as e:
        return f"❌ Failed to setup hybrid configuration: {str(e)}"