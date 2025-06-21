"""
Settings management for Voice MCP Server.
Provides flexible configuration with granular control over individual parameters.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger("voice-mcp")

@dataclass
class VoiceSettings:
    """User voice settings with granular control."""
    # TTS Settings
    tts_provider: str = "openai"  # "openai" or "kokoro"
    tts_voice: str = "nova"       # Voice to use
    tts_model: str = "tts-1"      # TTS model
    
    # STT Settings  
    stt_provider: str = "openai"  # "openai" or "local"
    stt_model: str = "whisper-1"  # STT model
    
    # Conversation Settings
    silence_timeout: float = 2.5  # Seconds of silence before stopping recording
    listen_duration: float = 180.0  # Maximum listen duration (fallback)
    
    # Audio Settings
    audio_feedback: str = "chime"  # "chime", "voice", "both", "none"
    
    # Advanced Settings
    allow_emotions: bool = False   # Enable emotional TTS
    auto_start_kokoro: bool = False # Auto-start Kokoro when needed
    prefer_local: bool = True      # Prefer local services when available
    
    # Metadata
    last_updated: str = ""

class VoiceSettingsManager:
    """Manages voice settings with persistence."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".voice-mcp"
        self.settings_file = self.config_dir / "user_settings.json"
        self._ensure_config_dir()
        self._settings: Optional[VoiceSettings] = None
    
    def _ensure_config_dir(self):
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(exist_ok=True)
    
    def load_settings(self) -> VoiceSettings:
        """Load user settings from disk."""
        if self._settings:
            return self._settings
            
        if not self.settings_file.exists():
            # Create default settings
            self._settings = VoiceSettings()
            self.save_settings()
            return self._settings
        
        try:
            with open(self.settings_file, 'r') as f:
                data = json.load(f)
            
            self._settings = VoiceSettings(**data)
            return self._settings
            
        except Exception as e:
            logger.error(f"Failed to load settings: {e}, using defaults")
            self._settings = VoiceSettings()
            return self._settings
    
    def save_settings(self):
        """Save current settings to disk."""
        if not self._settings:
            return
            
        try:
            self._settings.last_updated = datetime.now().isoformat()
            
            with open(self.settings_file, 'w') as f:
                json.dump(asdict(self._settings), f, indent=2)
                
            logger.info("Settings saved successfully")
                
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
    
    def update_setting(self, key: str, value: Any) -> bool:
        """Update a single setting."""
        settings = self.load_settings()
        
        if not hasattr(settings, key):
            return False
            
        setattr(settings, key, value)
        self._settings = settings
        self.save_settings()
        self.apply_to_environment()
        return True
    
    def get_setting(self, key: str) -> Any:
        """Get a single setting value."""
        settings = self.load_settings()
        return getattr(settings, key, None)
    
    def apply_to_environment(self):
        """Apply current settings to environment variables."""
        settings = self.load_settings()
        
        # TTS Configuration
        if settings.tts_provider == "kokoro":
            os.environ['TTS_BASE_URL'] = "http://localhost:8880/v1"
            os.environ['TTS_VOICE'] = settings.tts_voice
        elif settings.tts_provider == "openai":
            # Unset local URL to use OpenAI
            if 'TTS_BASE_URL' in os.environ:
                del os.environ['TTS_BASE_URL']
            os.environ['TTS_VOICE'] = settings.tts_voice
        
        os.environ['TTS_MODEL'] = settings.tts_model
        
        # STT Configuration
        if settings.stt_provider == "local":
            os.environ['STT_BASE_URL'] = "http://localhost:2022/v1"
        elif settings.stt_provider == "openai":
            # Unset local URL to use OpenAI
            if 'STT_BASE_URL' in os.environ:
                del os.environ['STT_BASE_URL']
        
        os.environ['STT_MODEL'] = settings.stt_model
        
        # Other settings
        os.environ['VOICE_MCP_SILENCE_TIMEOUT'] = str(settings.silence_timeout)
        os.environ['VOICE_MCP_AUDIO_FEEDBACK'] = settings.audio_feedback
        os.environ['VOICE_ALLOW_EMOTIONS'] = str(settings.allow_emotions).lower()
        os.environ['VOICE_MCP_AUTO_START_KOKORO'] = str(settings.auto_start_kokoro).lower()
        os.environ['VOICE_MCP_PREFER_LOCAL'] = str(settings.prefer_local).lower()
        
        logger.info(f"Applied settings to environment: TTS={settings.tts_provider}, STT={settings.stt_provider}, Silence={settings.silence_timeout}s")

# Global instance
settings_manager = VoiceSettingsManager()

# Auto-apply settings on import
settings_manager.apply_to_environment()