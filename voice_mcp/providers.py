"""
Provider registry for voice-mcp.

This module manages the configuration and selection of voice service providers,
supporting both cloud and local STT/TTS services with transparent fallback.
"""

import logging
from typing import Dict, Optional, List, Any
import httpx
import asyncio

logger = logging.getLogger("voice-mcp")


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