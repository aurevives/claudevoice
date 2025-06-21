# ClaudeVoice

> **Fork of [Voice Mode](https://github.com/mbailey/voicemode) optimized for Claude Code**

Enhanced voice conversation capabilities specifically designed for Claude Code users. This fork includes improved features like automatic silence detection and optimized conversation flows.

**🔧 This is a specialized fork - for the original project, visit [mbailey/voicemode](https://github.com/mbailey/voicemode)**

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

## 🎬 Demo

Watch Voice Mode in action:

[![Voice Mode Demo](https://img.youtube.com/vi/aXRNWvpnwVs/maxresdefault.jpg)](https://www.youtube.com/watch?v=aXRNWvpnwVs)

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
- **Optimized Conversation Flow**: Better integration with Claude Code's interaction patterns
- **Improved Timing**: Faster response times and more reliable audio processing

### 🔄 Compared to Original
This fork maintains full compatibility with the original Voice Mode while adding Claude Code-specific optimizations. All core features and configuration options remain the same.

## Development

### Fork from Source
```bash
git clone https://github.com/aurevives/claudevoice.git
cd claudevoice
pip install -e .
```

### Contributing
This fork focuses on Claude Code optimizations. For general Voice Mode features, contribute to the [upstream project](https://github.com/mbailey/voicemode).

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

## Links

### This Fork
- **GitHub**: [github.com/aurevives/claudevoice](https://github.com/aurevives/claudevoice)
- **Claude Code**: [claude.ai/code](https://claude.ai/code)

### Original Project
- **Website**: [getvoicemode.com](https://getvoicemode.com)
- **GitHub**: [github.com/mbailey/voicemode](https://github.com/mbailey/voicemode)
- **PyPI**: [pypi.org/project/voice-mcp](https://pypi.org/project/voice-mcp/)

### Community
- **Discord**: [Join Voice Mode community](https://discord.gg/gVHPPK5U)
- **Twitter/X**: [@getvoicemode](https://twitter.com/getvoicemode)

## License

MIT - Fork of [Voice Mode](https://github.com/mbailey/voicemode) (MIT License by [Failmode](https://failmode.com))
