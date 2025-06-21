# ClaudeVoice

> **Fork of [Voice Mode](https://github.com/mbailey/voicemode) optimized for Claude Code**

Enhanced voice conversation capabilities specifically designed for Claude Code users. This fork includes improved features like automatic silence detection and optimized conversation flows.

## 🖥️ Compatibility

**Runs on:** Linux • macOS • Windows (WSL) | **Python:** 3.10+ | **Tested:** Ubuntu 24.04 LTS, Fedora 42

## ✨ Features

- **🎙️ Natural voice conversations** with Claude Code - ask questions and hear responses
- **🔇 Smart silence detection** - automatically stops listening when you finish speaking (no more waiting!)
- **🔄 Multiple transports** - local microphone or LiveKit room-based communication  
- **🗣️ OpenAI-compatible** - works with any STT/TTS service (local or cloud)
- **⚡ Optimized for Claude Code** - enhanced conversation flows and improved user experience
- **🔧 MCP Integration** - designed specifically for Claude Code's MCP architecture

## 🎯 Simple Requirements

**All you need to get started:**

1. **🔑 OpenAI API Key** (or compatible service) - for speech-to-text and text-to-speech
2. **🎤 Computer with microphone and speakers** OR **☁️ LiveKit server** ([LiveKit Cloud](https://docs.livekit.io/home/cloud/) or [self-hosted](https://github.com/livekit/livekit))

## Quick Start

```bash
# Install ClaudeVoice MCP
claude mcp add claudevoice --env OPENAI_API_KEY=your-openai-key -- uvx --from git+https://github.com/aurevives/claudevoice claudevoice

# Start using voice with Claude Code
claude
# Then use the converse tool in your conversation!
```


## Example Usage with Claude Code

Once configured, start natural voice conversations:

- *"Let's have a voice conversation"*
- *"Ask me something using voice"*
- *"Tell me a joke and wait for my response"*

**Key improvement:** Smart silence detection means you don't have to wait for timeouts - the conversation flows naturally when you stop speaking!

## Installation for Claude Code

### Prerequisites
- Python >= 3.10
- OpenAI API Key (or compatible service)
- Claude Code CLI

### Installation Command

```bash
# Install from this fork
claude mcp add claudevoice --env OPENAI_API_KEY=your-openai-key -- uvx --from git+https://github.com/aurevives/claudevoice claudevoice

# Alternative: set environment variable first
export OPENAI_API_KEY=your-openai-key
claude mcp add claudevoice -- uvx --from git+https://github.com/aurevives/claudevoice claudevoice
```

**⚠️ Note:** This fork is specifically designed for Claude Code. For other MCP clients, use the [original Voice Mode](https://github.com/mbailey/voicemode).

## What's Different in This Fork

### 🚀 Enhanced Features
- **Smart Silence Detection**: Automatically detects when you stop speaking and ends recording
- **Granular Settings System**: Easy-to-use MCP tools for configuration without environment variables
- **Multiple TTS Providers**: OpenAI, Kokoro (local), and Gemini AI Studio (2025)
- **Gemini Custom Prompts**: Control voice style with natural language ("Speak cheerfully", "Sound professional")
- **Flexible Provider Choice**: Mix and match TTS/STT providers (OpenAI TTS + Local Whisper, etc.)
- **Configurable Silence Timeout**: Adjust how long to wait before stopping recording (2s, 5s, 10s, etc.)
- **Persistent Settings**: Your preferences are saved and restored automatically

### 🔧 Settings Management
Instead of manually setting environment variables, use these MCP tools:
- `get_voice_settings`: View current configuration
- `set_tts_provider`: Choose "openai", "kokoro", or "gemini" for text-to-speech
- `set_stt_provider`: Choose "openai" or "local" for speech-to-text  
- `set_silence_timeout`: Configure silence detection (e.g., 2.5 seconds)
- `set_tts_voice`: Change voice (nova, alloy, af_sky, Zephyr, etc.)
- `set_gemini_model`: Choose Gemini model ("flash" or "pro")
- `set_gemini_prompt`: Customize Gemini voice style with natural language
- `quick_setup_local`: Switch to 100% local processing
- `quick_setup_cloud`: Switch to 100% cloud processing  
- `quick_setup_hybrid`: Mix local STT with cloud TTS
- `quick_setup_gemini`: Use Gemini TTS + local Whisper

### 🔄 How It Works
1. **One-time setup**: Set your API keys as environment variables:
   ```bash
   export OPENAI_API_KEY="your-openai-key"
   export GEMINI_API_KEY="your-gemini-key"
   ```
2. **Easy switching**: Use MCP tools to choose providers and settings
3. **Automatic persistence**: Settings are saved to `~/.voice-mcp/user_settings.json`
4. **Smart fallback**: Automatically uses available services

### 🎨 Gemini TTS Examples
```
# Set creative voice style
set_gemini_prompt("Speak with enthusiasm and creativity, like a storyteller")

# Professional presentation style  
set_gemini_prompt("Speak clearly and professionally, suitable for business presentations")

# Casual conversation style
set_gemini_prompt("Speak naturally and conversationally, like talking to a friend")

# Choose Flash (faster) or Pro (higher quality) model
set_gemini_model("flash")  # or "pro"
```


## Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `converse` | Have a voice conversation - speak and optionally listen | `message`, `wait_for_response` (default: true), `listen_duration` (default: 10s), `transport` (auto/local/livekit) |
| `listen_for_speech` | Listen for speech and convert to text | `duration` (default: 5s) |
| `check_room_status` | Check LiveKit room status and participants | None |
| `check_audio_devices` | List available audio input/output devices | None |
| `start_kokoro` | Start the Kokoro TTS service | `models_dir` (optional, defaults to ~/Models/kokoro) |
| `stop_kokoro` | Stop the Kokoro TTS service | None |
| `kokoro_status` | Check the status of Kokoro TTS service | None |

**Note:** The `converse` tool is the primary interface for voice interactions, combining speaking and listening in a natural flow.

## Configuration

**📖 See [docs/configuration.md](docs/configuration.md) for complete setup instructions for all MCP hosts**

**📁 Ready-to-use config files in [config-examples/](config-examples/)**

### Quick Setup

The only required configuration is your OpenAI API key:

```bash
export OPENAI_API_KEY="your-key"
```

### Optional Settings

```bash
# Custom STT/TTS services (OpenAI-compatible)
export STT_BASE_URL="http://localhost:2022/v1"  # Local Whisper
export TTS_BASE_URL="http://localhost:8880/v1"  # Local TTS
export TTS_VOICE="alloy"                        # Voice selection

# LiveKit (for room-based communication)
# See docs/livekit/ for setup guide
export LIVEKIT_URL="wss://your-app.livekit.cloud"
export LIVEKIT_API_KEY="your-api-key"
export LIVEKIT_API_SECRET="your-api-secret"

# Debug mode
export VOICE_MCP_DEBUG="true"

# Save all audio (TTS output and STT input)
export VOICE_MCP_SAVE_AUDIO="true"
```

## Local STT/TTS Services

For privacy-focused or offline usage, Voice Mode supports local speech services:

- **[Whisper.cpp](docs/whisper.cpp.md)** - Local speech-to-text with OpenAI-compatible API
- **[Kokoro](docs/kokoro.md)** - Local text-to-speech with multiple voice options

These services provide the same API interface as OpenAI, allowing seamless switching between cloud and local processing.

### OpenAI API Compatibility Benefits

By strictly adhering to OpenAI's API standard, Voice Mode enables powerful deployment flexibility:

- **🔀 Transparent Routing**: Users can implement their own API proxies or gateways outside of Voice Mode to route requests to different providers based on custom logic (cost, latency, availability, etc.)
- **🎯 Model Selection**: Deploy routing layers that select optimal models per request without modifying Voice Mode configuration
- **💰 Cost Optimization**: Build intelligent routers that balance between expensive cloud APIs and free local models
- **🔧 No Lock-in**: Switch providers by simply changing the `BASE_URL` - no code changes required

Example: Simply set `OPENAI_BASE_URL` to point to your custom router:
```bash
export OPENAI_BASE_URL="https://router.example.com/v1"
export OPENAI_API_KEY="your-key"
# Voice Mode now uses your router for all OpenAI API calls
```

The OpenAI SDK handles this automatically - no Voice Mode configuration needed!

## Architecture

```
┌─────────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   Claude/LLM        │     │  LiveKit Server  │     │  Voice Frontend     │
│   (MCP Client)      │◄────►│  (Optional)     │◄───►│  (Optional)         │
└─────────────────────┘     └──────────────────┘     └─────────────────────┘
         │                            │
         │                            │
         ▼                            ▼
┌─────────────────────┐     ┌──────────────────┐
│  Voice MCP Server   │     │   Audio Services │
│  • converse         │     │  • OpenAI APIs   │
│  • listen_for_speech│◄───►│  • Local Whisper │
│  • check_room_status│     │  • Local TTS     │
│  • check_audio_devices    └──────────────────┘
└─────────────────────┘
```

## Troubleshooting

### Common Issues

- **No microphone access**: Check system permissions for terminal/application
- **UV not found**: Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **OpenAI API error**: Verify your `OPENAI_API_KEY` is set correctly
- **No audio output**: Check system audio settings and available devices

### Debug Mode

Enable detailed logging and audio file saving:

```bash
export VOICE_MCP_DEBUG=true
```

Debug audio files are saved to: `~/voice-mcp_recordings/`

### Audio Saving

To save all audio files (both TTS output and STT input):

```bash
export VOICE_MCP_SAVE_AUDIO=true
```

Audio files are saved to: `~/voice-mcp_audio/` with timestamps in the filename.


## License

MIT - Fork of [Voice Mode](https://github.com/mbailey/voicemode) (MIT License by [Failmode](https://failmode.com))
