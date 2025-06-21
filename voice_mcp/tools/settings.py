"""
Settings management tools for Voice MCP.
"""

import logging
from typing import Optional, List
from voice_mcp.server_new import mcp
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
    
    # Show Gemini-specific settings if using Gemini
    if settings.tts_provider == "gemini":
        result.append("\n🤖 GEMINI SETTINGS:")
        result.append(f"  Model: {settings.gemini_model}")
        result.append(f"  System prompt: {settings.gemini_system_prompt}")
    
    if settings.last_updated:
        result.append(f"\n📅 Last updated: {settings.last_updated[:19]}")
    
    return "\n".join(result)

@mcp.tool()
async def set_tts_provider(provider: str) -> str:
    """
    Set the TTS (Text-to-Speech) provider.
    
    Args:
        provider: TTS provider to use ("openai", "kokoro", or "gemini")
    
    Returns:
        Confirmation message.
    """
    if provider not in ["openai", "kokoro", "gemini"]:
        return "❌ Invalid TTS provider. Use 'openai', 'kokoro', or 'gemini'."
    
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
    
    result.append("\n🤖 GEMINI TTS (AI Studio):")
    gemini_voices = [
        "Aoede", "Callisto", "Charon", "Deimos", "Echo", "Europa",
        "Fenrir", "Ganymede", "Hera", "Io", "Kore", "Lunara",
        "Minerva", "Naia", "Nova", "Oberon", "Phobos", "Quorra",
        "Rhea", "Selene", "Titan", "Umbra", "Vega", "Whisper",
        "Xara", "Yuki", "Zephyr", "Astra", "Cypher", "Delta"
    ]
    for voice in gemini_voices:
        result.append(f"  • {voice}")
    
    result.append("\n💡 USAGE:")
    result.append("Use set_tts_voice('voice_name') to change voice")
    result.append("Use set_tts_provider('openai', 'kokoro', or 'gemini') to change provider")
    result.append("Use set_gemini_model() and set_gemini_prompt() for Gemini customization")
    
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

@mcp.tool()
async def set_gemini_model(model: str) -> str:
    """
    Set the Gemini TTS model.
    
    Args:
        model: Gemini model to use ("flash" for 2.5-flash or "pro" for 2.5-pro)
    
    Returns:
        Confirmation message.
    """
    model_mapping = {
        "flash": "gemini-2.5-flash-preview-tts",
        "pro": "gemini-2.5-pro-preview-tts"
    }
    
    if model in model_mapping:
        full_model = model_mapping[model]
    elif model in model_mapping.values():
        full_model = model
    else:
        return "❌ Invalid Gemini model. Use 'flash' or 'pro'."
    
    success = settings_manager.update_setting('gemini_model', full_model)
    if success:
        return f"✅ Gemini model set to: {model} ({full_model})"
    else:
        return "❌ Failed to update Gemini model."

@mcp.tool()
async def set_gemini_prompt(prompt: str) -> str:
    """
    Set the Gemini TTS system prompt for voice style control.
    
    Args:
        prompt: System prompt to control voice style, emotion, and characteristics
    
    Returns:
        Confirmation message.
    """
    if not prompt or len(prompt.strip()) < 3:
        return "❌ System prompt must be at least 3 characters long."
    
    success = settings_manager.update_setting('gemini_system_prompt', prompt.strip())
    if success:
        return f"✅ Gemini system prompt set to: {prompt[:50]}{'...' if len(prompt) > 50 else ''}"
    else:
        return "❌ Failed to update Gemini system prompt."

@mcp.tool()
async def quick_setup_gemini() -> str:
    """
    Quick setup for Gemini AI Studio TTS with local Whisper STT.
    
    Returns:
        Setup confirmation message.
    """
    try:
        settings_manager.update_setting('tts_provider', 'gemini')
        settings_manager.update_setting('tts_voice', 'Zephyr')
        settings_manager.update_setting('gemini_model', 'gemini-2.5-flash-preview-tts')
        settings_manager.update_setting('stt_provider', 'local')
        settings_manager.update_setting('prefer_local', True)
        
        return "✅ QUICK SETUP: Gemini TTS + Local Whisper STT configured"
        
    except Exception as e:
        return f"❌ Failed to setup Gemini configuration: {str(e)}"