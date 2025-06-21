"""
Core functionality for voice-mcp.

This module contains the main functions used by the voice-mcp script,
extracted to allow for easier testing and reuse.
"""

import asyncio
import logging
import os
import tempfile
import gc
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from pydub import AudioSegment
from openai import AsyncOpenAI
import httpx

logger = logging.getLogger("voice-mcp")


def get_debug_filename(prefix: str, extension: str) -> str:
    """Generate debug filename with timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # milliseconds
    return f"{timestamp}-{prefix}.{extension}"


def save_debug_file(data: bytes, prefix: str, extension: str, debug_dir: Path, debug: bool = False) -> Optional[str]:
    """Save debug file if debug mode is enabled"""
    if not debug:
        return None
    
    try:
        filename = get_debug_filename(prefix, extension)
        filepath = debug_dir / filename
        
        with open(filepath, 'wb') as f:
            f.write(data)
        
        logger.debug(f"Debug file saved: {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Failed to save debug file: {e}")
        return None


def get_openai_clients(api_key: str, stt_base_url: str, tts_base_url: str) -> dict:
    """Initialize OpenAI clients for STT and TTS with connection pooling"""
    # Configure timeouts and connection pooling
    http_client_config = {
        'timeout': httpx.Timeout(30.0, connect=5.0),
        'limits': httpx.Limits(max_keepalive_connections=5, max_connections=10),
    }
    
    return {
        'stt': AsyncOpenAI(
            api_key=api_key,
            base_url=stt_base_url,
            http_client=httpx.AsyncClient(**http_client_config)
        ),
        'tts': AsyncOpenAI(
            api_key=api_key,
            base_url=tts_base_url,
            http_client=httpx.AsyncClient(**http_client_config)
        )
    }


async def text_to_speech_gemini(
    text: str,
    tts_model: str,
    tts_voice: str,
    debug: bool = False,
    debug_dir: Optional[Path] = None,
    save_audio: bool = False,
    audio_dir: Optional[Path] = None,
    instructions: Optional[str] = None
) -> tuple[bool, Optional[dict]]:
    """Convert text to speech using Gemini TTS and play it.
    
    Returns:
        tuple: (success: bool, metrics: dict) where metrics contains 'generation' and 'playback' times
    """
    import time
    
    logger.info(f"Gemini TTS: Converting text to speech: '{text[:100]}{'...' if len(text) > 100 else ''}'")
    if debug:
        logger.debug(f"Gemini TTS full text: {text}")
        logger.debug(f"Gemini TTS config - Model: {tts_model}, Voice: {tts_voice}")
    
    metrics = {}
    
    try:
        # Import and create Gemini TTS provider
        from voice_mcp.providers import GeminiTTSProvider
        gemini_provider = GeminiTTSProvider()
        
        # Track generation time
        generation_start = time.perf_counter()
        
        # Generate speech using Gemini
        audio_file_path = await gemini_provider.generate_speech(
            text=text,
            voice=tts_voice,
            model=tts_model,
            system_prompt=instructions  # Use instructions as system prompt for Gemini
        )
        
        metrics['generation'] = time.perf_counter() - generation_start
        logger.debug(f"Gemini TTS generated audio file: {audio_file_path}")
        
        # Read the generated audio file
        with open(audio_file_path, 'rb') as f:
            response_content = f.read()
        
        # Save debug file if enabled
        if debug and debug_dir:
            debug_path = save_debug_file(response_content, "gemini-tts-output", "wav", debug_dir, debug)
            if debug_path:
                logger.info(f"Gemini TTS debug audio saved to: {debug_path}")
        
        # Save audio file if audio saving is enabled
        if save_audio and audio_dir:
            audio_path = save_debug_file(response_content, "gemini-tts", "wav", audio_dir, True)
            if audio_path:
                logger.info(f"Gemini TTS audio saved to: {audio_path}")
        
        # Play audio
        playback_start = time.perf_counter()
        
        try:
            # Load WAV audio directly
            logger.debug("Loading Gemini WAV audio...")
            audio = AudioSegment.from_wav(audio_file_path)
            logger.debug(f"Audio loaded - Duration: {len(audio)}ms, Channels: {audio.channels}, Frame rate: {audio.frame_rate}")
            
            # Convert to numpy array
            logger.debug("Converting to numpy array...")
            samples = np.array(audio.get_array_of_samples())
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))
                logger.debug("Reshaped for stereo")
            
            # Convert to float32 for sounddevice
            samples = samples.astype(np.float32) / 32767.0
            logger.debug(f"Audio converted to float32, shape: {samples.shape}")
            
            # Try to ensure sounddevice doesn't interfere with stdout/stderr
            try:
                import sounddevice as sd
                import sys
                
                # Save current stdio state
                original_stdin = sys.stdin
                original_stdout = sys.stdout
                original_stderr = sys.stderr
                
                try:
                    # Force initialization before playing
                    sd.default.samplerate = audio.frame_rate
                    sd.default.channels = audio.channels
                    
                    # Add 100ms of silence at the beginning to prevent clipping
                    silence_duration = 0.1  # seconds
                    silence_samples = int(audio.frame_rate * silence_duration)
                    # Match the shape of the samples array exactly
                    if samples.ndim == 1:
                        silence = np.zeros(silence_samples, dtype=np.float32)
                        samples_with_buffer = np.concatenate([silence, samples])
                    else:
                        silence = np.zeros((silence_samples, samples.shape[1]), dtype=np.float32)
                        samples_with_buffer = np.vstack([silence, samples])
                    
                    sd.play(samples_with_buffer, audio.frame_rate)
                    sd.wait()
                    
                    logger.info("✓ Gemini TTS played successfully")
                    metrics['playback'] = time.perf_counter() - playback_start
                    
                    # Clean up the temporary file
                    os.unlink(audio_file_path)
                    return True, metrics
                finally:
                    # Restore stdio if it was changed
                    if sys.stdin != original_stdin:
                        sys.stdin = original_stdin
                    if sys.stdout != original_stdout:
                        sys.stdout = original_stdout
                    if sys.stderr != original_stderr:
                        sys.stderr = original_stderr
            except Exception as sd_error:
                logger.error(f"Gemini TTS Sounddevice playback failed: {sd_error}")
                
                # Fallback to file-based playback methods
                logger.info("Attempting alternative playback methods...")
                
                # Try using PyDub's playback (requires simpleaudio or pyaudio)
                try:
                    from pydub.playback import play as pydub_play
                    logger.debug("Using PyDub playback...")
                    pydub_play(audio)
                    logger.info("✓ Gemini TTS played successfully with PyDub")
                    metrics['playback'] = time.perf_counter() - playback_start
                    os.unlink(audio_file_path)
                    return True, metrics
                except Exception as pydub_error:
                    logger.error(f"PyDub playback failed: {pydub_error}")
                
                # Last resort: save to user's home directory for manual playback
                try:
                    fallback_path = Path.home() / f"voice-mcp-gemini-{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                    import shutil
                    shutil.copy(audio_file_path, fallback_path)
                    logger.warning(f"Gemini audio saved to {fallback_path} for manual playback")
                    os.unlink(audio_file_path)
                    metrics['playback'] = time.perf_counter() - playback_start
                    return False, metrics
                except Exception as save_error:
                    logger.error(f"Failed to save Gemini audio file: {save_error}")
                    os.unlink(audio_file_path)
                    metrics['playback'] = time.perf_counter() - playback_start
                    return False, metrics
            
        except Exception as e:
            logger.error(f"Error playing Gemini audio: {e}")
            logger.error(f"Audio format - Channels: {audio.channels if 'audio' in locals() else 'unknown'}, Frame rate: {audio.frame_rate if 'audio' in locals() else 'unknown'}")
            logger.error(f"Samples shape: {samples.shape if 'samples' in locals() else 'unknown'}")
            
            # Clean up the temporary file
            if audio_file_path and os.path.exists(audio_file_path):
                os.unlink(audio_file_path)
            metrics['playback'] = time.perf_counter() - playback_start
            return False, metrics
                    
    except Exception as e:
        logger.error(f"Gemini TTS failed: {e}")
        logger.error(f"Gemini TTS config when error occurred - Model: {tts_model}, Voice: {tts_voice}")
        return False, metrics


async def text_to_speech(
    text: str,
    openai_clients: dict,
    tts_model: str,
    tts_voice: str,
    tts_base_url: str,
    debug: bool = False,
    debug_dir: Optional[Path] = None,
    save_audio: bool = False,
    audio_dir: Optional[Path] = None,
    client_key: str = 'tts',
    instructions: Optional[str] = None,
    provider: Optional[str] = None
) -> tuple[bool, Optional[dict]]:
    """Convert text to speech and play it.
    
    Returns:
        tuple: (success: bool, metrics: dict) where metrics contains 'generation' and 'playback' times
    """
    import time
    
    # Route to Gemini TTS if using Gemini provider
    logger.info(f"TTS routing check - provider: {provider}, client_key: {client_key}")
    if provider == 'gemini' or client_key == 'gemini':
        logger.info("✅ Routing to Gemini TTS provider")
        return await text_to_speech_gemini(
            text=text,
            tts_model=tts_model,
            tts_voice=tts_voice,
            debug=debug,
            debug_dir=debug_dir,
            save_audio=save_audio,
            audio_dir=audio_dir,
            instructions=instructions
        )
    
    logger.info(f"TTS: Converting text to speech: '{text[:100]}{'...' if len(text) > 100 else ''}'")
    if debug:
        logger.debug(f"TTS full text: {text}")
        logger.debug(f"TTS config - Model: {tts_model}, Voice: {tts_voice}, Base URL: {tts_base_url}")
    
    metrics = {}
    
    try:
        # Use MP3 format for bandwidth efficiency
        audio_format = "mp3"
        
        logger.debug("Making TTS API request...")
        # Build request parameters
        request_params = {
            "model": tts_model,
            "input": text,
            "voice": tts_voice,
            "response_format": audio_format
        }
        
        # Add instructions if provided and model supports it
        if instructions and tts_model == "gpt-4o-mini-tts":
            request_params["instructions"] = instructions
            logger.debug(f"TTS instructions: {instructions}")
        
        # Track generation time
        generation_start = time.perf_counter()
        
        # Use context manager to ensure response is properly closed
        async with openai_clients[client_key].audio.speech.with_streaming_response.create(
            **request_params
        ) as response:
            # Read the entire response content
            response_content = await response.read()
            
        metrics['generation'] = time.perf_counter() - generation_start
        logger.debug(f"TTS API response received, content length: {len(response_content)} bytes")
        
        # Save debug file if enabled
        if debug and debug_dir:
            debug_path = save_debug_file(response_content, "tts-output", audio_format, debug_dir, debug)
            if debug_path:
                logger.info(f"TTS debug audio saved to: {debug_path}")
        
        # Save audio file if audio saving is enabled
        if save_audio and audio_dir:
            audio_path = save_debug_file(response_content, "tts", audio_format, audio_dir, True)
            if audio_path:
                logger.info(f"TTS audio saved to: {audio_path}")
        
        # Play audio
        playback_start = time.perf_counter()
        
        with tempfile.NamedTemporaryFile(suffix=f'.{audio_format}', delete=False) as tmp_file:
            tmp_file.write(response_content)
            tmp_file.flush()
            
            logger.debug(f"Audio written to temp file: {tmp_file.name}")
            
            try:
                # Load MP3 and convert to numpy array for playback
                logger.debug("Loading MP3 audio...")
                audio = AudioSegment.from_mp3(tmp_file.name)
                logger.debug(f"Audio loaded - Duration: {len(audio)}ms, Channels: {audio.channels}, Frame rate: {audio.frame_rate}")
                
                # Convert to numpy array
                logger.debug("Converting to numpy array...")
                samples = np.array(audio.get_array_of_samples())
                if audio.channels == 2:
                    samples = samples.reshape((-1, 2))
                    logger.debug("Reshaped for stereo")
                
                # Convert to float32 for sounddevice
                samples = samples.astype(np.float32) / 32767.0
                logger.debug(f"Audio converted to float32, shape: {samples.shape}")
                
                # Check audio devices
                if debug:
                    try:
                        import sounddevice as sd
                        devices = sd.query_devices()
                        default_output = sd.default.device[1]
                        logger.debug(f"Default output device: {default_output} - {devices[default_output]['name'] if default_output is not None else 'None'}")
                    except Exception as dev_e:
                        logger.error(f"Error querying audio devices: {dev_e}")
                
                logger.debug(f"Playing audio with sounddevice at {audio.frame_rate}Hz...")
                
                # Try to ensure sounddevice doesn't interfere with stdout/stderr
                try:
                    import sounddevice as sd
                    import sys
                    
                    # Save current stdio state
                    original_stdin = sys.stdin
                    original_stdout = sys.stdout
                    original_stderr = sys.stderr
                    
                    try:
                        # Force initialization before playing
                        sd.default.samplerate = audio.frame_rate
                        sd.default.channels = audio.channels
                        
                        # Add 100ms of silence at the beginning to prevent clipping
                        silence_duration = 0.1  # seconds
                        silence_samples = int(audio.frame_rate * silence_duration)
                        # Match the shape of the samples array exactly
                        if samples.ndim == 1:
                            silence = np.zeros(silence_samples, dtype=np.float32)
                            samples_with_buffer = np.concatenate([silence, samples])
                        else:
                            silence = np.zeros((silence_samples, samples.shape[1]), dtype=np.float32)
                            samples_with_buffer = np.vstack([silence, samples])
                        
                        sd.play(samples_with_buffer, audio.frame_rate)
                        sd.wait()
                        
                        logger.info("✓ TTS played successfully")
                        os.unlink(tmp_file.name)
                        metrics['playback'] = time.perf_counter() - playback_start
                        return True, metrics
                    finally:
                        # Restore stdio if it was changed
                        if sys.stdin != original_stdin:
                            sys.stdin = original_stdin
                        if sys.stdout != original_stdout:
                            sys.stdout = original_stdout
                        if sys.stderr != original_stderr:
                            sys.stderr = original_stderr
                except Exception as sd_error:
                    logger.error(f"Sounddevice playback failed: {sd_error}")
                    
                    # Fallback to file-based playback methods
                    logger.info("Attempting alternative playback methods...")
                    
                    # Try using PyDub's playback (requires simpleaudio or pyaudio)
                    try:
                        from pydub.playback import play as pydub_play
                        logger.debug("Using PyDub playback...")
                        pydub_play(audio)
                        logger.info("✓ TTS played successfully with PyDub")
                        os.unlink(tmp_file.name)
                        metrics['playback'] = time.perf_counter() - playback_start
                        return True, metrics
                    except Exception as pydub_error:
                        logger.error(f"PyDub playback failed: {pydub_error}")
                    
                    # Last resort: save to user's home directory for manual playback
                    try:
                        fallback_path = Path.home() / f"voice-mcp-audio-{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
                        import shutil
                        shutil.copy(tmp_file.name, fallback_path)
                        logger.warning(f"Audio saved to {fallback_path} for manual playback")
                        os.unlink(tmp_file.name)
                        metrics['playback'] = time.perf_counter() - playback_start
                        return False, metrics
                    except Exception as save_error:
                        logger.error(f"Failed to save audio file: {save_error}")
                        os.unlink(tmp_file.name)
                        metrics['playback'] = time.perf_counter() - playback_start
                        return False, metrics
                
            except Exception as e:
                logger.error(f"Error playing audio: {e}")
                logger.error(f"Audio format - Channels: {audio.channels if 'audio' in locals() else 'unknown'}, Frame rate: {audio.frame_rate if 'audio' in locals() else 'unknown'}")
                logger.error(f"Samples shape: {samples.shape if 'samples' in locals() else 'unknown'}")
                
                # Try alternative playback method in debug mode
                if debug:
                    try:
                        logger.debug("Attempting alternative playback with system command...")
                        import subprocess
                        result = subprocess.run(['paplay', tmp_file.name], capture_output=True, timeout=10)
                        if result.returncode == 0:
                            logger.info("✓ Alternative playback successful")
                            os.unlink(tmp_file.name)
                            metrics['playback'] = time.perf_counter() - playback_start
                            return True, metrics
                        else:
                            logger.error(f"Alternative playback failed: {result.stderr.decode()}")
                    except Exception as alt_e:
                        logger.error(f"Alternative playback error: {alt_e}")
                
                os.unlink(tmp_file.name)
                metrics['playback'] = time.perf_counter() - playback_start
                return False, metrics
                        
    except Exception as e:
        logger.error(f"TTS failed: {e}")
        logger.error(f"TTS config when error occurred - Model: {tts_model}, Voice: {tts_voice}, Base URL: {tts_base_url}")
        if hasattr(e, 'response'):
            logger.error(f"HTTP status: {e.response.status_code if hasattr(e.response, 'status_code') else 'unknown'}")
            logger.error(f"Response text: {e.response.text if hasattr(e.response, 'text') else 'unknown'}")
        return False, metrics


def generate_chime(frequencies: list, duration: float = 0.1, sample_rate: int = 44100) -> np.ndarray:
    """Generate a chime sound with given frequencies.
    
    Args:
        frequencies: List of frequencies to play in sequence
        duration: Duration of each tone in seconds
        sample_rate: Sample rate for audio generation
        
    Returns:
        Numpy array of audio samples
    """
    samples_per_tone = int(sample_rate * duration)
    fade_samples = int(sample_rate * 0.01)  # 10ms fade
    
    all_samples = []
    
    for freq in frequencies:
        # Generate sine wave
        t = np.linspace(0, duration, samples_per_tone, False)
        tone = 0.3 * np.sin(2 * np.pi * freq * t)  # 0.3 amplitude for comfortable volume
        
        # Apply fade in/out to prevent clicks
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
        
        tone[:fade_samples] *= fade_in
        tone[-fade_samples:] *= fade_out
        
        all_samples.append(tone)
    
    # Concatenate all tones
    chime = np.concatenate(all_samples)
    
    # Convert to 16-bit integer
    chime_int16 = (chime * 32767).astype(np.int16)
    
    return chime_int16


async def play_chime_start(sample_rate: int = 44100) -> bool:
    """Play the recording start chime (ascending tones).
    
    Returns:
        True if chime played successfully, False otherwise
    """
    try:
        import sounddevice as sd
        chime = generate_chime([800, 1000], duration=0.1, sample_rate=sample_rate)
        sd.play(chime, sample_rate)
        sd.wait()
        return True
    except Exception as e:
        logger.debug(f"Could not play start chime: {e}")
        return False


async def play_chime_end(sample_rate: int = 44100) -> bool:
    """Play the recording end chime (descending tones).
    
    Returns:
        True if chime played successfully, False otherwise
    """
    try:
        import sounddevice as sd
        chime = generate_chime([1000, 800], duration=0.1, sample_rate=sample_rate)
        sd.play(chime, sample_rate)
        sd.wait()
        return True
    except Exception as e:
        logger.debug(f"Could not play end chime: {e}")
        return False


async def cleanup(openai_clients: dict):
    """Cleanup function to close HTTP clients and resources"""
    logger.info("Shutting down Voice MCP Server...")
    
    # Close OpenAI HTTP clients
    try:
        # Close all clients (including provider-specific ones)
        for client_name, client in openai_clients.items():
            if hasattr(client, '_client'):
                await client._client.aclose()
                logger.debug(f"Closed {client_name} HTTP client")
    except Exception as e:
        logger.error(f"Error closing HTTP clients: {e}")
    
    # Final garbage collection
    gc.collect()
    logger.info("Cleanup completed")