"""Resources for saved audio files."""

import os
from pathlib import Path
from typing import Optional
from voice_mcp.server_new import mcp
from voice_mcp.config import SAVE_AUDIO, AUDIO_DIR, logger

@mcp.resource("audio://files")
async def list_audio_files(uri: str) -> Optional[str]:
    """List saved audio files if audio saving is enabled.
    
    Returns a list of audio files in the audio directory with their
    creation times and sizes.
    """
    if not SAVE_AUDIO:
        return "Audio saving is not enabled. Set VOICE_MCP_SAVE_AUDIO=1 to enable."
    
    if not os.path.exists(AUDIO_DIR):
        return "No audio files found - directory does not exist."
    
    audio_files = []
    for file in sorted(Path(AUDIO_DIR).glob("*.wav")):
        stat = file.stat()
        size_kb = stat.st_size / 1024
        audio_files.append(f"- {file.name} ({size_kb:.1f} KB)")
    
    if not audio_files:
        return "No audio files found."
    
    return f"Saved audio files in {AUDIO_DIR}:\n" + "\n".join(audio_files)

@mcp.resource("audio://file/{filename}")
async def get_audio_file(uri: str) -> Optional[str]:
    """Get metadata about a specific audio file.
    
    Args:
        uri: Resource URI in format audio://file/{filename}
        
    Returns:
        File metadata including size and creation time.
    """
    if not SAVE_AUDIO:
        return "Audio saving is not enabled. Set VOICE_MCP_SAVE_AUDIO=1 to enable."
    
    # Extract filename from URI
    parts = uri.split("/")
    if len(parts) < 4:
        return "Invalid URI format. Expected: audio://file/{filename}"
    
    filename = parts[3]
    file_path = os.path.join(AUDIO_DIR, filename)
    
    if not os.path.exists(file_path):
        return f"Audio file not found: {filename}"
    
    stat = os.stat(file_path)
    size_kb = stat.st_size / 1024
    
    return f"""Audio file: {filename}
Size: {size_kb:.1f} KB
Created: {stat.st_ctime}
Path: {file_path}"""