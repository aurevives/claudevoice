"""
Gemini TTS Provider for voice-mcp.

Integrates Google Gemini 2.5 Flash/Pro TTS models with custom prompt support.
"""

import logging
import os
import tempfile
import base64
import mimetypes
import struct
from typing import Optional, Dict, Any, AsyncIterator
from pathlib import Path

from google import genai
from google.genai import types

logger = logging.getLogger("voice-mcp")


class GeminiTTSProvider:
    """Gemini TTS provider using Google AI Studio API."""
    
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
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
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=full_text)],
                ),
            ]
            
            # Configure generation
            config = types.GenerateContentConfig(
                temperature=1,
                response_modalities=["audio"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
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